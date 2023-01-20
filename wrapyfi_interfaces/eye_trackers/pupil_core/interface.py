import os
import sys
import time
import socket
import argparse
import io
import PIL
import logging

import cv2
import numpy as np
import zmq
import msgpack as serializer

from wrapyfi.connect.wrapper import MiddlewareCommunicator, DEFAULT_COMMUNICATOR

PUPIL_CORE_DEFAULT_COMMUNICATOR = os.environ.get("PUPIL_CORE_DEFAULT_COMMUNICATOR", DEFAULT_COMMUNICATOR)
PUPIL_CORE_DEFAULT_COMMUNICATOR = os.environ.get("PUPIL_CORE_DEFAULT_MWARE", PUPIL_CORE_DEFAULT_COMMUNICATOR)


def check_capture_exists(ip_address, port):
    """check pupil capture instance exists"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if not sock.connect_ex((ip_address, port)):
            logging.info("Found Pupil Capture")
        else:
            logging.warning("Cannot find Pupil Capture")
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


class PupilCore(MiddlewareCommunicator):

    MWARE = PUPIL_CORE_DEFAULT_COMMUNICATOR
    ANNOTATIONS_PORT = "/pupil_core_controller/annotations"
    GAZE_COORDINATES_PORT = "/control_interface/gaze_coordinates"
    RECORDING_MESSAGE_PORT = "/pupil_core_controller/recording_message"
    CAM_WORLD_PORT = "/pupil_core_controller/world_video_feed"
    CAM_WORLD_FRAME_WIDTH = 1280
    CAM_WORLD_FRAME_HEIGHT = 720
    CAM_LEFT_PORT = "/pupil_core_controller/left_video_feed"
    CAM_LEFT_FRAME_WIDTH = 192
    CAM_LEFT_FRAME_HEIGHT = 192
    CAM_RIGHT_PORT = "/pupil_core_controller/right_video_feed"
    CAM_RIGHT_FRAME_WIDTH = 192
    CAM_RIGHT_FRAME_HEIGHT = 192
    ANNOTATION_KEYS = ("recording_message",)

    def __init__(self, tcp_ip="localhost", tcp_port=50020, headless=False,
                 recording_message_port=RECORDING_MESSAGE_PORT,
                 get_cam_world_feed=True, cam_world_port=CAM_WORLD_PORT,
                 cam_world_height=CAM_WORLD_FRAME_HEIGHT, cam_world_width=CAM_WORLD_FRAME_WIDTH,
                 get_cam_right_feed=False, cam_right_port=CAM_RIGHT_PORT,
                 cam_right_height=CAM_RIGHT_FRAME_HEIGHT, cam_right_width=CAM_RIGHT_FRAME_WIDTH,
                 get_cam_left_feed=False, cam_left_port=CAM_LEFT_PORT,
                 cam_left_height=CAM_LEFT_FRAME_HEIGHT, cam_left_width=CAM_LEFT_FRAME_WIDTH,
                 get_gaze_coordinates=True, gaze_coordinates_port=GAZE_COORDINATES_PORT,
                 gaze_message_type="fixation", min_gaze_confidence=0.2,  # gaze_message_type="gaze.3d"
                 annotation_keys=ANNOTATION_KEYS, annotations_port=ANNOTATIONS_PORT, mware=MWARE, **kwargs):

        super(MiddlewareCommunicator, self).__init__()

        self.MWARE = mware
        self.ANNOTATIONS_PORT = annotations_port
        self.GAZE_COORDINATES_PORT = gaze_coordinates_port
        self.RECORDING_MESSAGE_PORT = recording_message_port
        self.ANNOTATION_KEYS = annotation_keys
        self.CAM_WORLD_PORT = cam_world_port
        self.CAM_RIGHT_PORT = cam_right_port
        self.CAM_LEFT_PORT = cam_left_port
        self.CAM_WORLD_FRAME_WIDTH = cam_world_width
        self.CAM_WORLD_FRAME_HEIGHT = cam_world_height
        self.CAM_RIGHT_FRAME_WIDTH = cam_right_width
        self.CAM_RIGHT_FRAME_HEIGHT = cam_right_height
        self.CAM_LEFT_FRAME_WIDTH = cam_left_width
        self.CAM_LEFT_FRAME_HEIGHT = cam_left_height

        self.tcp_ip = tcp_ip
        self.tcp_port = tcp_port
        self.headless = headless
        self.get_gaze_coordinates = get_gaze_coordinates
        self.gaze_message_type = gaze_message_type
        self.min_gaze_confidence = min_gaze_confidence

        self.pupil_remote = None

        self.local_clock = None
        self.stable_offset_mean = None

        self.prev_gaze = None

        # self.pub_socket = None
        # self.sub_socket_gaze = None
        check_capture_exists(self.tcp_ip, self.tcp_port)

        if tcp_ip and tcp_port:
            self.pupil_remote, _ = setup_pupil_remote_connection(self.tcp_ip, self.tcp_port)
        else:
            self.pupil_remote = None
        if recording_message_port:
            self.activate_communication(self.acquire_recording_message, "listen")
        else:
            self.activate_communication(self.acquire_recording_message, "disable")
            self.activate_communication(self.update_recording_message, "disable")

        if annotations_port or annotation_keys:
            _, self.pub_socket = setup_pupil_remote_connection(self.tcp_ip, self.tcp_port,
                                                               port_type="publisher")
            self.local_clock = time.perf_counter
            self.stable_offset_mean = measure_clock_offset_stable(
                self.pupil_remote, clock_function=self.local_clock, n_samples=10
            )
            pupil_time_actual = request_pupil_time(self.pupil_remote)
            local_time_actual = self.local_clock()
            pupil_time_calculated_locally = local_time_actual + self.stable_offset_mean
            logging.info(f"Pupil time actual: {pupil_time_actual}")
            logging.info(f"Local time actual: {local_time_actual}")
            logging.info(f"Stable offset: {self.stable_offset_mean}")
            logging.info(f"Pupil time (calculated locally): {pupil_time_calculated_locally}")

            notify(
                self.pupil_remote,
                {"subject": "start_plugin", "name": "Annotation_Capture", "args": {}},
            )
            self.activate_communication(getattr(self, "acquire_annotations"), "listen")
        else:
            self.activate_communication(self.acquire_annotations, "disable")
            self.activate_communication(self.write_annotation, "disable")

        if get_gaze_coordinates and gaze_message_type:
            _, self.sub_socket_gaze = setup_pupil_remote_connection(self.tcp_ip, self.tcp_port,
                                                                    port_type="subscriber",
                                                                    message_type=self.gaze_message_type)
            if gaze_coordinates_port:
                self.activate_communication(self.read_gaze, "publish")
        else:
            self.activate_communication(self.read_gaze, "disable")

        if get_cam_world_feed:
            _, self.sub_socket_world_img = setup_pupil_remote_connection(self.tcp_ip, self.tcp_port,
                                                                         port_type="subscriber",
                                                                         message_type="frame.world")
            if cam_world_port:
                self.activate_communication(self.read_world_image, "publish")
        else:
            self.activate_communication(self.read_world_image, "disable")

        if get_cam_left_feed:
            _, self.sub_socket_right_img = setup_pupil_remote_connection(self.tcp_ip, self.tcp_port,
                                                                         port_type="subscriber",
                                                                         message_type="frame.eye.1")
            if cam_left_port:
                self.activate_communication(self.read_left_image, "publish")
        else:
            self.activate_communication(self.read_left_image, "disable")

        if get_cam_right_feed:
            _, self.sub_socket_left_img = setup_pupil_remote_connection(self.tcp_ip, self.tcp_port,
                                                                        port_type="subscriber",
                                                                        message_type="frame.eye.0")
            if cam_right_port:
                self.activate_communication(self.read_right_image, "publish")
        else:
            self.activate_communication(self.read_right_image, "disable")

        self.build()

    def build(self):
        return

    @MiddlewareCommunicator.register("Image", "$_mware", "PupilCore", "$cam_world_port",
                                     width="$img_width", height="$img_height", rgb="$_rgb")
    def read_world_image(self, cam_world_port, img_width=CAM_WORLD_FRAME_WIDTH, img_height=CAM_WORLD_FRAME_HEIGHT,
                         jpg=True, _rgb=True, _mware=MWARE):
        """
        Read images from the world camera of the Pupil Core.

        :param cam_world_port: str: Port to receive images from the world camera
        :param img_width: int: Width of the image
        :param img_height: int: Height of the image
        :param _rgb: bool: Whether the image is RGB or not
        :return: Images from the Pupil
        """
        try:
            _, _, payload = self.sub_socket_world_img.recv_multipart()
            if jpg:
                img_stream = io.BytesIO(payload)
                img = np.array(PIL.Image.open(img_stream))

            elif _rgb:
                img = np.fromstring(payload, dtype=np.uint8).reshape(img_height, img_width, 3)
            else:
                img = np.fromstring(payload, dtype=np.uint8).reshape(img_height, img_width)
            return img,
        except:
            if _rgb:
                return np.zeros((img_height, img_width, 3), dtype="uint8"),
            else:
                return np.zeros((img_height, img_width), dtype="uint8"),

    @MiddlewareCommunicator.register("Image", "$_mware", "PupilCore", "$cam_right_port",
                                     width="$img_width", height="$img_height", rgb=False)
    def read_right_image(self, cam_right_port, img_width=CAM_RIGHT_FRAME_WIDTH, img_height=CAM_WORLD_FRAME_HEIGHT,
                         jpg=True, _mware=MWARE):
        """
        Read images from the right eye camera of the Pupil Core.

        :param cam_right_port: str: Port to receive images from the right eye camera
        :param img_width: int: Width of the image
        :param img_height: int: Height of the image
        :return: Images from the Pupil
        """
        try:
            _, _, payload = self.sub_socket_right_img.recv_multipart()
            if jpg:
                img_stream = io.BytesIO(payload)
                img = np.array(PIL.Image.open(img_stream))
            else:
                img = np.fromstring(payload, dtype=np.uint8).reshape(img_height, img_width)
            return img,
        except:
            return np.zeros((img_height, img_width), dtype="uint8"),

    @MiddlewareCommunicator.register("Image", "$_mware", "PupilCore", "$cam_left_port",
                                     width="$img_width", height="$img_height", rgb=False)
    def read_left_image(self, cam_left_port, img_width=CAM_LEFT_FRAME_WIDTH, img_height=CAM_LEFT_FRAME_HEIGHT,
                        jpg=True, _mware=MWARE):
        """
        Read images from the left eye camera of the Pupil Core.

        :param cam_left_port: str: Port to receive images from the left eye camera
        :param img_width: int: Width of the image
        :param img_height: int: Height of the image
        :return: Images from the Pupil
        """
        try:
            _, _, payload = self.sub_socket_left_img.recv_multipart()
            if jpg:
                img_stream = io.BytesIO(payload)
                img = np.array(PIL.Image.open(img_stream))
            else:
                img = np.fromstring(payload, dtype=np.uint8).reshape(img_height, img_width)
            return img,
        except:
            return np.zeros((img_height, img_width), dtype="uint8"),

    @MiddlewareCommunicator.register("NativeObject", "$_mware", "PupilCore", "$gaze_coordinates_port",
                                     carrier="", should_wait=False)
    def read_gaze(self, gaze_coordinates_port=GAZE_COORDINATES_PORT, _mware=MWARE):
        confidence = None
        try:
            _, payload = self.sub_socket_gaze.recv_multipart()
            message = serializer.loads(payload)

            if self.gaze_message_type == "fixation":
                gaze = message["norm_pos"]
                confidence = message["confidence"]
                # calculate yaw and pitch
                yaw = np.rad2deg(np.arctan2((gaze[0] - 0.5) * 2, 1))
                pitch = np.rad2deg(np.arctan2((gaze[1] - 0.5) * 2, 1))
            else:
                gaze = message["base_data"]
                confidence = message["confidence"]
                yaw = np.rad2deg(gaze[0]["theta"])
                pitch = np.rad2deg(gaze[0]["phi"])

            gaze_message = {
                "topic": message["topic"],
                "gaze": gaze,
                "confidence": confidence,
                "orig_timestamp": message["timestamp"],
                "timestamp": time.time(),
                "yaw": yaw,
                "pitch": pitch,
                "order": "xyz",
                "quaternion": False,
            }
        except:
            gaze_message = None
        return (gaze_message, ) if confidence and confidence > self.min_gaze_confidence else (None,)

    @MiddlewareCommunicator.register("NativeObject", "$_mware", "PupilCore",
                                     "$annotations_port", should_wait=False)
    def acquire_annotations(self, annotations_port=ANNOTATIONS_PORT, _mware=MWARE):
        return None,

    @MiddlewareCommunicator.register("NativeObject", "$_mware", "PupilCore", "/pupil_core_controller/logs/annotation",
                                     carrier="", should_wait=False)
    def write_annotation(self, annotation_key, _mware=MWARE, **kwargs):
        # Ensure start_recording() was triggered before calling this function
        local_time = self.local_clock()
        duration = 0.0
        annotation_message = new_trigger(annotation_key, duration, local_time + self.stable_offset_mean)
        if "topic" in kwargs:
            del kwargs["topic"]
        annotation_message.update(**kwargs)
        send_trigger(self.pub_socket, annotation_message)
        return annotation_message,

    @MiddlewareCommunicator.register("NativeObject", "$_mware", "PupilCore",
                                     "$recording_message_port", should_wait=False)
    def acquire_recording_message(self, recording_message_port=RECORDING_MESSAGE_PORT, _mware=MWARE, **kwargs):
        return None,

    @MiddlewareCommunicator.register("NativeObject", "$_mware", "PupilCore",
                                     "/pupil_core_controller/logs/recording_message", should_wait=False)
    def update_recording_message(self, _mware=MWARE, **kwargs):

        if kwargs.get("begin_calibration", False):
            self.start_calibration()
        if kwargs.get("end_calibration", False):
            self.end_calibration()
        if kwargs.get("begin_recording", False):
            self.start_recording(session_name=kwargs.get("recording_name", ""))
        if kwargs.get("end_recording", False):
            self.end_recording()
        return {"topic": "logging_eye_coordinates",
                "timestamp": time.time(),
                "recording_message": kwargs,
                "command": f"recording message: {kwargs}"},

    def start_calibration(self):
        logging.info("Start calibration")
        self.pupil_remote.send_string("C")
        logging.info(self.pupil_remote.recv_string())

    def end_calibration(self):
        logging.info("End calibration")
        self.pupil_remote.send_string("c")
        logging.info(self.pupil_remote.recv_string())

    def start_recording(self, session_name=""):
        logging.info("Start recording")
        cmd = f"R {session_name}" if session_name else "R"
        self.pupil_remote.send_string(cmd)
        logging.info(self.pupil_remote.recv_string())

    def end_recording(self):
        logging.info("End recording")
        self.pupil_remote.send_string("r")
        logging.info(self.pupil_remote.recv_string())

    def getPeriod(self):
        return 0.01

    def updateModule(self):
        annotations = {}
        if hasattr(self, "sub_socket_world_img"):
            world_cam, = self.read_world_image(cam_world_port=self.CAM_WORLD_PORT,
                                               img_width=self.CAM_WORLD_FRAME_WIDTH,
                                               img_height=self.CAM_WORLD_FRAME_HEIGHT, _mware=self.MWARE)
            if not self.headless and world_cam is not None:
                cv2.imshow("PupilWorldCam", world_cam)
                cv2.waitKey(1)
        if hasattr(self, "sub_socket_left_img"):
            left_cam, = self.read_left_image(cam_left_port=self.CAM_LEFT_PORT,
                                               img_width=self.CAM_LEFT_FRAME_WIDTH,
                                               img_height=self.CAM_LEFT_FRAME_HEIGHT, _mware=self.MWARE)
            if not self.headless and left_cam is not None:
                cv2.imshow("PupilLeftCam", left_cam)
                cv2.waitKey(1)
        if hasattr(self, "sub_socket_left_img"):
            right_cam, = self.read_left_image(cam_left_port=self.CAM_LEFT_PORT,
                                               img_width=self.CAM_LEFT_FRAME_WIDTH,
                                               img_height=self.CAM_LEFT_FRAME_HEIGHT, _mware=self.MWARE)
            if not self.headless and right_cam is not None:
                cv2.imshow("PupilRightCam", right_cam)
                cv2.waitKey(1)

        if hasattr(self, "sub_socket_gaze"):
            gaze, = self.read_gaze(gaze_coordinates_port=self.GAZE_COORDINATES_PORT, _mware=self.MWARE)
            if gaze is not None:
                self.prev_gaze = gaze
                logging.info(gaze)
            else:
                logging.info(self.prev_gaze)
        # writing and publishing
        session, = self.acquire_recording_message(recording_message_port=self.RECORDING_MESSAGE_PORT, _mware=self.MWARE)

        if session is not None:
            recording_annotation, = self.update_recording_message(**session, _mware=self.MWARE)
            annotations.update(**recording_annotation.get("recording_message", {}))

        anno_return, = self.acquire_annotations(annotations_port=self.ANNOTATIONS_PORT, _mware=self.MWARE)
        transmitted_annotation = annotations.copy()
        anno_return = anno_return or {}
        anno_return.update(transmitted_annotation)

        for annotation_key in self.ANNOTATION_KEYS:
            anno_return.get(annotation_key, None)
            if anno_return is not None:
                self.write_annotation(annotation_key, _mware=self.MWARE, **anno_return)
                annotations.clear()
        return True

    def runModule(self):

        while True:
            try:
                self.updateModule()
                time.sleep(self.getPeriod())
            except Exception as e:
                logging.error(e)
                # break
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


class PupilCoreCommandLine(MiddlewareCommunicator):
    MWARE = PUPIL_CORE_DEFAULT_COMMUNICATOR
    RECORDING_MESSAGE_PORT = "/pupil_core_controller/recording_message"

    def __init__(self, recording_message_port=RECORDING_MESSAGE_PORT, mware=MWARE, **kwargs):
        super(MiddlewareCommunicator, self).__init__()
        self.MWARE = mware
        self.RECORDING_MESSAGE_PORT = recording_message_port

        self.activate_communication(getattr(self, "transmit_recording_message"), "publish")

        self.build()

    def build(self):
        return

    def runModule(self):
        while True:
            command = input("Insert command (R: record; r: stop rec.; C: calibrate; c: stop cal.): ")
            if command == "R":  # begin recording
                self.transmit_recording_message(message={"begin_recording": True})
            elif command == "r":  # end recording
                self.transmit_recording_message(message={"end_recording": True})
            elif command == "C":  # begin calibration
                self.transmit_recording_message(message={"begin_calibration": True})
            elif command == "c":  # end calibration
                self.transmit_recording_message(message={"end_calibration": True})

    @MiddlewareCommunicator.register("NativeObject", "$_mware", "PupilCoreCommandLine",
                                     "$recording_message_port", should_wait=False)
    def transmit_recording_message(self, message, recording_message_port=RECORDING_MESSAGE_PORT, _mware=MWARE):
        return message,



def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--set_recording_message", action="store_true", default=False,
                        help="Type recording commands into terminal and ignores all other commands skipping "
                             "initialization of interface. This should be run in parallel with interface ")
    parser.add_argument("--tcp_ip", type=str, default="localhost", help="The Pupil Core TCP IP")
    parser.add_argument("--tcp_port", type=int, default=50020, help="The Pupil Core TCP connection port")
    parser.add_argument("--headless", action="store_true", help="Disable CV2 GUI")
    parser.add_argument("--get_cam_world_feed", action="store_true",
                        help="Get the camera feeds from the Pupil world camera")
    parser.add_argument("--cam_world_port", type=str, default="",
                        help="The port (topic) name used for publishing (republishing) Pupil world camera images")
    parser.add_argument("--get_cam_left_feed", action="store_true",
                        help="Get the camera feeds from the Pupil left eye camera")
    parser.add_argument("--cam_left_port", type=str, default="",
                        help="The port (topic) name used for publishing (republishing) Pupil left eye camera images")
    parser.add_argument("--get_cam_right_feed", action="store_true",
                        help="Get the camera feeds from the Pupil right eye camera")
    parser.add_argument("--cam_right_port", type=str, default="",
                        help="The port (topic) name used for publishing (republishing) Pupil right eye camera images")
    parser.add_argument("--recording_message_port", type=str, default="",
                        help="The port (topic) name used for receiving recording command messages")
    parser.add_argument("--get_gaze_coordinates", action="store_true", help="Get the gaze coordinates from the Pupil")
    parser.add_argument("--gaze_coordinates_port", type=str, default="",
                        help="The port (topic) name used for transmitting the acquired gaze coordinates")
    parser.add_argument("--gaze_message_type", type=str, default="fixation", choices=("fixation", "gaze.3d"),
                        help="The gaze message name to acquire directly from the Pupil")
    parser.add_argument("--min_gaze_confidence", type=float, default=0.2,
                        help="Minimum gaze confidence to accept before publishing coordinates. Max is 1, min is 0")
    parser.add_argument("--annotations_port", type=str, default="",
                        help="The port (topic) name used for receiving the annotations which are then transmitted to the Pupil")
    parser.add_argument('--annotation_keys', nargs='*', default=('recording_message'),
                        help='List of key names which should be passed to the Pupil from the ones published to the '
                             'annotations port. Adding \'recording_message\' to the list transmits the keys '
                             'passed to the recording port as well.')
    parser.add_argument("--mware", type=str, default=PUPIL_CORE_DEFAULT_COMMUNICATOR,
                        help="The middleware used for communication. "
                             "This can be overriden by providing either of the following environment variables "
                             "{WRAPYFI_DEFAULT_COMMUNICATOR, WRAPYFI_DEFAULT_MWARE, "
                             "WAVESHARE_IMU_DEFAULT_COMMUNICATOR, WAVESHARE_IMU_DEFAULT_MWARE}. "
                             "Defaults to the Wrapyfi default communicator",
                        choices=MiddlewareCommunicator.get_communicators())
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.set_recording_message:
        pupil = PupilCoreCommandLine(**vars(args))
    else:
        pupil = PupilCore(**vars(args))
    pupil.runModule()
