import os
import sys
import time
import socket
import argparse

import numpy as np
import zmq
import msgpack as serializer

from wrapyfi.connect.wrapper import MiddlewareCommunicator, DEFAULT_COMMUNICATOR

PUPIL_CORE_DEFAULT_COMMUNICATOR = os.environ.get("WAVESHARE_IMU_DEFAULT_COMMUNICATOR", DEFAULT_COMMUNICATOR)
PUPIL_CORE_DEFAULT_COMMUNICATOR = os.environ.get("WAVESHARE_IMU_DEFAULT_MWARE", PUPIL_CORE_DEFAULT_COMMUNICATOR)


def check_capture_exists(ip_address, port):
    """check pupil capture instance exists"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if not sock.connect_ex((ip_address, port)):
            print("Found Pupil Capture")
        else:
            print("Cannot find Pupil Capture")
            sys.exit()


def setup_pupil_remote_connection(ip_address, port, pupil_remote=None, port_type=None, message_type=None):
    """Creates a zmq-REQ socket and connects it to Pupil Capture or Service
    to send and receive notifications.
    We also set up a PUB socket to send the annotations. This is necessary to write
    messages to the IPC Backbone other than notifications
    See https://docs.pupil-labs.com/developer/core/network-api/ for details.
    """
    # zmq-REQ socket
    if pupil_remote is None:
        ctx = zmq.Context.instance()
        pupil_remote = ctx.socket(zmq.REQ)
        pupil_remote.setsockopt(zmq.SNDTIMEO, 2000)
        pupil_remote.setsockopt(zmq.RCVTIMEO, 2000)
        pupil_remote.setsockopt(zmq.LINGER, 1000)
        pupil_remote.connect(f"tcp://{ip_address}:{port}")
    else:
        ctx = pupil_remote.context

    if port_type == "subscriber":
        try:
            pupil_remote.send_string('SUB_PORT')
            sub_port = pupil_remote.recv_string()
            sock = ctx.socket(zmq.SUB)
            sock.connect(f'tcp://{ip_address}:{sub_port}')
            sock.subscribe(message_type)
        except zmq.ZMQError:
            raise (Exception("Pupil Tracker not available"))
    elif port_type == "publisher":
        try:
            pupil_remote.send_string("PUB_PORT")
            pub_port = pupil_remote.recv_string()
            sock = zmq.Socket(ctx, zmq.PUB)
            sock.connect(f"tcp://{ip_address}:{pub_port}")
        except zmq.ZMQError:
            raise (Exception("Pupil Tracker not available"))
    else:
        sock = None

    return pupil_remote, sock


def request_pupil_time(pupil_remote):
    """Uses an existing Pupil Core software connection to request the remote time.
    Returns the current "pupil time" at the timepoint of reception.
    See https://docs.pupil-labs.com/core/terminology/#pupil-time for more information
    about "pupil time".
    """
    pupil_remote.send_string("t")
    pupil_time = pupil_remote.recv()
    return float(pupil_time)


def measure_clock_offset(pupil_remote, clock_function):
    """Calculates the offset between the Pupil Core software clock and a local clock.
    Requesting the remote pupil time takes time. This delay needs to be considered
    when calculating the clock offset. We measure the local time before (A) and
    after (B) the request and assume that the remote pupil time was measured at (A+B)/2,
    i.e. the midpoint between A and B.
    As a result, we have two measurements from two different clocks that were taken
    assumingly at the same point in time. The difference between them ("clock offset")
    allows us, given a new local clock measurement, to infer the corresponding time on
    the remote clock.
    """
    local_time_before = clock_function()
    pupil_time = request_pupil_time(pupil_remote)
    local_time_after = clock_function()

    local_time = (local_time_before + local_time_after) / 2.0
    clock_offset = pupil_time - local_time
    return clock_offset


def measure_clock_offset_stable(pupil_remote, clock_function, n_samples=10):
    """Returns the mean clock offset after multiple measurements to reduce the effect
    of varying network delay.
    Since the network connection to Pupil Capture/Service is not necessarily stable,
    one has to assume that the delays to send and receive commands are not symmetrical
    and might vary. To reduce the possible clock-offset estimation error, this function
    repeats the measurement multiple times and returns the mean clock offset.
    The variance of these measurements is expected to be higher for remote connections
    (two different computers) than for local connections (script and Core software
    running on the same computer). You can easily extend this function to perform
    further statistical analysis on your clock-offset measurements to examine the
    accuracy of the time sync.
    """
    assert n_samples > 0, "Requires at least one sample"
    offsets = [
        measure_clock_offset(pupil_remote, clock_function) for x in range(n_samples)
    ]
    return sum(offsets) / len(offsets)  # mean offset


def notify(pupil_remote, notification):
    """Sends ``notification`` to Pupil Remote"""
    topic = "notify." + notification["subject"]
    payload = serializer.dumps(notification, use_bin_type=True)
    pupil_remote.send_string(topic, flags=zmq.SNDMORE)
    pupil_remote.send(payload)
    return pupil_remote.recv_string()


def send_trigger(pub_socket, trigger):
    """Sends annotation via PUB port"""
    payload = serializer.dumps(trigger, use_bin_type=True)
    pub_socket.send_string(trigger["topic"], flags=zmq.SNDMORE)
    pub_socket.send(payload)


def new_trigger(label, duration, timestamp):
    """Creates a new trigger/annotation to send to Pupil Capture"""
    return {
        "topic": "annotation",
        "label": label,
        "timestamp": timestamp,
        "duration": duration,
    }


class Pupil(MiddlewareCommunicator):
    def __init__(self, tcp_ip="localhost", tcp_port=50020,
                 gaze_message_type="fixation", min_gaze_confidence=0.2,  # gaze_message_type="gaze.3d"
                 pose_annotation=("head_pose_imu", "head_pose_face", "head_pose_fused")):
        super(MiddlewareCommunicator, self).__init__()
        self.tcp_ip = tcp_ip
        self.tcp_port = tcp_port
        self.gaze_message_type = gaze_message_type
        self.min_gaze_confidence = min_gaze_confidence
        self.pose_annotation = pose_annotation

        self.pupil_remote = None

        self.local_clock = None
        self.stable_offset_mean = None

        self.prev_gaze = None

        # self.pub_socket = None
        # self.sub_socket_gaze = None

    def build(self):
        check_capture_exists(self.tcp_ip, self.tcp_port)

        self.pupil_remote, _ = setup_pupil_remote_connection(self.tcp_ip, self.tcp_port)
        if self.pose_annotation:
            _, self.pub_socket = setup_pupil_remote_connection(self.tcp_ip, self.tcp_port,
                                                               port_type="publisher")
            self.local_clock = time.perf_counter
            self.stable_offset_mean = measure_clock_offset_stable(
                self.pupil_remote, clock_function=self.local_clock, n_samples=10
            )
            pupil_time_actual = request_pupil_time(self.pupil_remote)
            local_time_actual = self.local_clock()
            pupil_time_calculated_locally = local_time_actual + self.stable_offset_mean
            print(f"Pupil time actual: {pupil_time_actual}")
            print(f"Local time actual: {local_time_actual}")
            print(f"Stable offset: {self.stable_offset_mean}")
            print(f"Pupil time (calculated locally): {pupil_time_calculated_locally}")

            notify(
                self.pupil_remote,
                {"subject": "start_plugin", "name": "Annotation_Capture", "args": {}},
            )
            for annotation in self.pose_annotation:
                self.activate_communication(getattr(self, f"acquire_{annotation}"), "listen")
                self.activate_communication(getattr(self, f"write_{annotation}"), "publish")

            self.activate_communication(getattr(self, "acquire_recording_message"), "listen")
            self.activate_communication(getattr(self, "write_recording_message"), "publish")

        if self.gaze_message_type:
            _, self.sub_socket_gaze = setup_pupil_remote_connection(self.tcp_ip, self.tcp_port,
                                                                    port_type="subscriber",
                                                                    message_type=self.gaze_message_type)
            self.activate_communication(getattr(self, "read_gaze"), "publish")

    @MiddlewareCommunicator.register("NativeObject", PUPIL_CORE_DEFAULT_COMMUNICATOR, "IMUPose", "/eye_tracker/IMUPose/head_pose_imu",
                                     carrier="mcast", should_wait=False)
    def receive_head_pose_imu(self):
        return None,

    @MiddlewareCommunicator.register("NativeObject", "yarp", "Pupil", "/eye_tracker/Pupil/head_pose_imu",
                                     carrier="", should_wait=False)
    def write_head_pose_imu(self, pitch, yaw, roll, **kwargs):
        # Ensure start_recording() was triggered before calling this function
        local_time = self.local_clock()
        duration = 0.0
        head_pose_message = new_trigger("head_pose_imu", duration, local_time + self.stable_offset_mean)
        head_pose_message["pitch"] = pitch
        head_pose_message["yaw"] = yaw
        head_pose_message["roll"] = roll
        send_trigger(self.pub_socket, head_pose_message)
        return head_pose_message,

    @MiddlewareCommunicator.register("NativeObject", PUPIL_CORE_DEFAULT_COMMUNICATOR, "FacePose", "/eye_tracker/FacePose/head_pose_face",
                                     carrier="mcast", should_wait=False)
    def receive_head_pose_face(self):
        return None,

    @MiddlewareCommunicator.register("NativeObject", PUPIL_CORE_DEFAULT_COMMUNICATOR, "Pupil", "/eye_tracker/Pupil/head_pose_face",
                                     carrier="", should_wait=False)
    def write_head_pose_face(self, pitch, yaw, roll, **kwargs):
        # Ensure start_recording() was triggered before calling this function
        local_time = self.local_clock()
        duration = 0.0
        head_pose_message = new_trigger("head_pose_face", duration, local_time + self.stable_offset_mean)
        head_pose_message["pitch"] = pitch
        head_pose_message["yaw"] = yaw
        head_pose_message["roll"] = roll
        send_trigger(self.pub_socket, head_pose_message)
        return head_pose_message,

    @MiddlewareCommunicator.register("NativeObject", PUPIL_CORE_DEFAULT_COMMUNICATOR, "GazeRecorder",
                                     "/eye_tracker/GazeRecorder/head_pose_fused",
                                     carrier="mcast", should_wait=False)
    def receive_head_pose_fused(self):
        return None,

    @MiddlewareCommunicator.register("NativeObject", PUPIL_CORE_DEFAULT_COMMUNICATOR, "Pupil", "/eye_tracker/Pupil/head_pose_fused",
                                     carrier="", should_wait=False)
    def write_head_pose_fused(self, pitch, yaw, roll, aggregation="mean", **kwargs):
        # Ensure start_recording() was triggered before calling this function
        local_time = self.local_clock()
        duration = 0.0
        head_pose_message = new_trigger("head_pose_fused", duration, local_time + self.stable_offset_mean)
        head_pose_message["pitch"] = pitch
        head_pose_message["yaw"] = yaw
        head_pose_message["roll"] = roll
        head_pose_message["aggregation"] = aggregation
        send_trigger(self.pub_socket, head_pose_message)
        return head_pose_message,

    @MiddlewareCommunicator.register("NativeObject", PUPIL_CORE_DEFAULT_COMMUNICATOR, "Pupil", "/eye_tracker/Pupil/fixation",
                                     carrier="", should_wait=False)
    def read_gaze(self):
        confidence = None
        try:
            _, payload = self.sub_socket_gaze.recv_multipart()
            message = serializer.loads(payload)

            gaze = message[b"norm_pos"]
            confidence = message[b"confidence"]

            # calculate yaw and pitch
            yaw = np.rad2deg(np.arctan2((gaze[0] - 0.5) * 2, 1))
            pitch = np.rad2deg(np.arctan2((gaze[1] - 0.5) * 2, 1))
            # yaw = np.rad2deg(message[b"base_data"][0][b"theta"])
            # pitch = np.rad2deg(message[b"base_data"][0][b"phi"])

            gaze_message = {
                "gaze": gaze,
                "confidence": confidence,
                "timestamp": message[b"timestamp"],
                "yaw": yaw,
                "pitch": pitch
            }
        except:
            gaze_message = None
        return (gaze_message, ) if confidence and confidence > self.min_gaze_confidence else (None,)

    @MiddlewareCommunicator.register("NativeObject", PUPIL_CORE_DEFAULT_COMMUNICATOR, "Pupil", "/eye_tracker/Pupil/recording_message",
                                     carrier="", should_wait=False)
    def write_recording_message(self, **kwargs):
        # Ensure start_recording() was triggered before calling this function
        local_time = self.local_clock()
        duration = 0.0
        recording_message = new_trigger("recording_message", duration, local_time + self.stable_offset_mean)
        if "topic" in kwargs:
            del kwargs["topic"]
        recording_message.update(**kwargs)
        send_trigger(self.pub_socket, recording_message)
        return recording_message,

    def start_calibration(self):
        print("Start calibration")
        self.pupil_remote.send_string("C")
        print(self.pupil_remote.recv_string())

    def end_calibration(self):
        print("End calibration")
        self.pupil_remote.send_string("c")
        print(self.pupil_remote.recv_string())

    def start_recording(self, session_name=""):
        print("Start recording")
        cmd = f"R {session_name}" if session_name else "R"
        self.pupil_remote.send_string(cmd)
        print(self.pupil_remote.recv_string())

    def end_recording(self):
        print("End recording")
        self.pupil_remote.send_string("r")
        print(self.pupil_remote.recv_string())

    @MiddlewareCommunicator.register("NativeObject", PUPIL_CORE_DEFAULT_COMMUNICATOR, "GazeRecorder",
                                     "/eye_tracker/GazeRecorder/recording_message",
                                     carrier="mcast", should_wait=False)
    def acquire_recording_message(self):
        return None,

    def getPeriod(self):
        return 0.01

    def updateModule(self):
        if hasattr(self, "sub_socket_gaze"):
            gaze, = self.read_gaze()
            if gaze is not None:
                self.prev_gaze = gaze
                print(gaze)
            else:
                print(self.prev_gaze)
        if hasattr(self, "pub_socket"):
            session, = self.acquire_recording_message()
            if session is not None:
                if session.get("begin_calibration", False):
                    self.start_calibration()
                if session.get("end_calibration", False):
                    self.end_calibration()
                if session.get("start_recording", False):
                    self.start_recording(session_name=session.get("recording_name", ""))
                if session.get("end_recording", False):
                    self.end_recording()
                if session.get("play_info", False):
                    self.write_recording_message(**session["play_info"])

            for annotation in self.pose_annotation:
                anno_return, = getattr(self, f"acquire_{annotation}")()
                if anno_return is not None:
                    head_pose, = getattr(self, f"write_{annotation}")(**anno_return)
                    if head_pose is not None:
                        print(head_pose)
        return True

    def runModule(self):
        if self.pupil_remote is None:
            self.build()
        while True:
            if hasattr(self, "pub_socket"):
                session, = self.acquire_recording_message()
                time.sleep(0.1)
                if session is not None:
                    if session.get("begin_recording", False):
                        self.start_recording(session_name=session.get("recording_name", ""))
                    if session.get("begin_calibration", False):
                        self.start_calibration()
                        break
            else:
                break
        while True:
            try:
                self.updateModule()
                time.sleep(self.getPeriod())
            except Exception as e:
                print(e)
                break
        if hasattr(self, "pub_socket"):
            self.end_recording()

    def __del__(self):
        if self.pupil_remote is not None:
            self.pupil_remote.close()
            self.pupil_remote.context.term()
        if hasattr(self, "sub_socket_gaze"):
            self.sub_socket_gaze.close()
        if hasattr(self, "pub_socket"):
            self.pub_socket.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--annotate", action="store_true", default=False,
                        help="Transmit annotation to pupil capture application. This automatically disable pupil reader")
    args = parser.parse_args()

    if args.annotate:
        pupil = Pupil(gaze_message_type="")
        pupil.runModule()
    else:
        pupil = Pupil(pose_annotation=())
        pupil.runModule()
