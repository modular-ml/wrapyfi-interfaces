import logging
import os
import time
import argparse
import json
import functools
from collections import deque

import serial
from wrapyfi.connect.wrapper import MiddlewareCommunicator, DEFAULT_COMMUNICATOR
from wrapyfi_interfaces.utils.filters import highpass_filter

WAVESHARE_IMU_DEFAULT_COMMUNICATOR = os.environ.get("WAVESHARE_IMU_DEFAULT_COMMUNICATOR", DEFAULT_COMMUNICATOR)
WAVESHARE_IMU_DEFAULT_COMMUNICATOR = os.environ.get("WAVESHARE_IMU_DEFAULT_MWARE", WAVESHARE_IMU_DEFAULT_COMMUNICATOR)



class WaveshareIMU(MiddlewareCommunicator):

    MWARE = WAVESHARE_IMU_DEFAULT_COMMUNICATOR
    ORIENTATION_COORDINATES_PORT = "/control_interface/orientation_coordinates"
    BASELINE_MWARE = WAVESHARE_IMU_DEFAULT_COMMUNICATOR
    BASELINE_ORIENTATION_COORDINATES_PORT = "/control_interface/baseline_orientation_coordinates"
    # constants
    # YAW_QUEUE_SIZE = 10
    # YAW_SMOOTHING_WINDOW = 2
    YAW_DIFFERENCE_LOWER_THRESHOLD = 0.155
    CALIBRATION_REPEAT = 100

    def __init__(self, ser_device="/dev/ttyACM0", ser_rate=115200,
                 flip_pitch=False, flip_yaw=False, flip_roll=False,
                 disable_pitch=False, disable_yaw=False, disable_roll=False,
                 const_pitch_offset=0.0, const_yaw_offset=0.0, const_roll_offset=0.0,
                 orientation_coordinates_port=ORIENTATION_COORDINATES_PORT, mware=MWARE,
                 baseline_orientation_coordinates_port=BASELINE_ORIENTATION_COORDINATES_PORT,
                 baseline_mware=BASELINE_MWARE):
        super(MiddlewareCommunicator, self).__init__()

        self.MWARE = mware
        self.ORIENTATION_COORDINATES_PORT = orientation_coordinates_port
        self.BASELINE_MWARE = baseline_mware
        self.BASELINE_ORIENTATION_COORDINATES_PORT = baseline_orientation_coordinates_port

        self.ser_device = ser_device
        self.ser_rate = ser_rate

        self.flip_pitch = flip_pitch
        self.flip_yaw = flip_yaw
        self.flip_roll = flip_roll

        self.pitch_offset = 0.0
        self.yaw_offset = 0.0
        self.roll_offset = 0.0
        
        self.const_pitch_offset = const_pitch_offset
        self.const_yaw_offset = const_yaw_offset
        self.const_roll_offset = const_roll_offset
        
        self.disable_pitch = disable_pitch
        self.disable_yaw = disable_yaw
        self.disable_roll = disable_roll
        
        # yaw filtering
        # self.yaw_queue = deque(maxlen=self.YAW_QUEUE_SIZE)
        self.prev_yaw = {"yaw": 0.0, "orig_timestamp": 0.0}
        self.last_yaw = {"yaw": 0.0, "orig_timestamp": 0.0}

        self.counter = 0
        if ser_device and ser_rate:
            self.pico = serial.Serial(port=self.ser_device, baudrate=self.ser_rate, timeout=.1)
        else:
            self.pico = None
        if orientation_coordinates_port:
            self.activate_communication(self.read_orientation, "publish")
        if baseline_orientation_coordinates_port:
            self.activate_communication(self.read_baseline_orientation, "listen")
        else:
            self.activate_communication(self.read_baseline_orientation, "disable")

        self.build()

    def build(self):
        WaveshareIMU.read_orientation.__defaults__ = (self.ORIENTATION_COORDINATES_PORT, "threshold", self.MWARE)
        WaveshareIMU.read_baseline_orientation.__defaults__ = (self.BASELINE_ORIENTATION_COORDINATES_PORT, self.BASELINE_MWARE)

    @MiddlewareCommunicator.register("NativeObject", "$_mware", "WaveshareIMU",
                                     "$orientation_coordinates_port", should_wait=False)
    def read_orientation(self, orientation_coordinates_port=ORIENTATION_COORDINATES_PORT, yaw_smoothing="threshold", _mware=MWARE):
        try:
            sensor_data = self.pico.readline().decode("utf-8")
            sensor_data = sensor_data.replace("nan", "\"nan\"")
            imu_data = json.loads(sensor_data)
            
            if self.disable_pitch:
                imu_data["pitch"] = 0.0
            else:
                imu_data["pitch"] = -imu_data["pitch"] - self.pitch_offset - self.const_pitch_offset if self.flip_pitch else imu_data["pitch"] - self.pitch_offset - self.const_pitch_offset
            
            if self.disable_yaw:
                imu_data["yaw"] = 0.0
            else:
                imu_data["yaw"] = -imu_data["yaw"] - self.yaw_offset - self.const_yaw_offset if self.flip_pitch else imu_data["yaw"] - self.yaw_offset - self.const_yaw_offset
            
            if self.disable_roll:
                imu_data["roll"] = 0.0
            else:
                imu_data["roll"] = -imu_data["roll"] - self.roll_offset - self.const_roll_offset if self.flip_pitch else imu_data["roll"] - self.roll_offset - self.const_roll_offset
            
            imu_data.update(topic=orientation_coordinates_port.split("/")[-1],
                            world_index=self.counter,
                            order="xyz",
                            quaternion=False,
                            timestamp=time.time())
            # print("yaw differencing", imu_data["yaw"] - self.prev_yaw)
            if yaw_smoothing == "threshold" and not self.disable_yaw:
                if abs((imu_data["yaw"] - self.prev_yaw["yaw"]) /
                       (imu_data["orig_timestamp"] - self.prev_yaw["orig_timestamp"])) > self.YAW_DIFFERENCE_LOWER_THRESHOLD:
                    self.last_yaw["orig_timestamp"] = imu_data["orig_timestamp"]
                    self.last_yaw["yaw"] = imu_data["yaw"]

                self.prev_yaw["orig_timestamp"] = imu_data["orig_timestamp"]
                self.prev_yaw["yaw"] = imu_data["yaw"]

                imu_data["yaw"] = self.last_yaw["yaw"]
            # if yaw_smoothing == "highpass":
            #     self.yaw_queue.append(imu_data["yaw"])
            #     imu_data["yaw"] = highpass_filter(list(self.yaw_queue),
            #                                       lower_bound=self.YAW_DIFFERENCE_LOWER_THRESHOLD,
            #                                       window_length=self.YAW_SMOOTHING_WINDOW)
            self.counter += 1
        except:
            imu_data = None
        return imu_data,

    @MiddlewareCommunicator.register("NativeObject", "$_mware", "WaveshareIMU",
                                     "$orientation_coordinates_port", should_wait=False)
    def read_baseline_orientation(self, orientation_coordinates_port=BASELINE_ORIENTATION_COORDINATES_PORT, _mware=BASELINE_MWARE):
        return None,

    def calculate_baseline_offset(self):
        pitch_offsets, roll_offsets, yaw_offsets = [], [], []
        for _ in range(0, self.CALIBRATION_REPEAT):
            imu_data, = self.read_orientation(orientation_coordinates_port=self.ORIENTATION_COORDINATES_PORT, _mware=self.MWARE)
            baseline_data, = self.read_baseline_orientation(orientation_coordinates_port=self.BASELINE_ORIENTATION_COORDINATES_PORT, _mware=self.BASELINE_MWARE)

            if imu_data is not None:
                if baseline_data is not None:
                    logging.info(baseline_data)
                    pitch_offsets.append(imu_data["pitch"] - baseline_data["pitch"])
                    logging.info(f"PITCH OFFSETS:{pitch_offsets}")
                    roll_offsets.append(imu_data["roll"] - baseline_data["roll"])
                    yaw_offsets.append(imu_data["yaw"] - baseline_data["yaw"])
            time.sleep(self.getPeriod())
        try:
            self.pitch_offset = sum(pitch_offsets) / len(pitch_offsets)
        except ZeroDivisionError:
            self.pitch_offset = 0
            logging.warning("Pitch offset was not calculated correctly. Did you correctly set the baseline port?")
        try:
            self.roll_offset = sum(roll_offsets) / len(roll_offsets)
        except ZeroDivisionError:
            self.roll_offset = 0
            logging.warning("Roll offset was not calculated correctly. Did you correctly set the baseline port?")
        try:
            self.yaw_offset = sum(yaw_offsets) / len(yaw_offsets)
        except ZeroDivisionError:
            self.yaw_offset = 0
            logging.warning("Yaw offset was not calculated correctly. Did you correctly set the baseline port?")

        return None,

    def getPeriod(self):
        return 0.02  # ~ 30-50 FPS

    def updateModule(self):
        imu_data, = self.read_orientation(orientation_coordinates_port=self.ORIENTATION_COORDINATES_PORT, _mware=self.MWARE)
        # here we just want to drain the baseline reader if available
        baseline_data, = self.read_baseline_orientation(orientation_coordinates_port=self.BASELINE_ORIENTATION_COORDINATES_PORT, _mware=self.BASELINE_MWARE)

        if imu_data is not None:
            logging.info(imu_data)
        return True
    
    def runModule(self):
        # perform offset detection on start if external baseline coordinates provided
        if self.BASELINE_ORIENTATION_COORDINATES_PORT:
            self.calculate_baseline_offset()
        while True:
            try:
                self.updateModule()
                time.sleep(self.getPeriod())
            except:
                break

    def __del__(self):
        if self.pico is not None:
            self.pico.close()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ser_device", type=str, default="/dev/ttyACM0", help="Serial device to read from")
    parser.add_argument("--ser_rate", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--orientation_coordinates_port", type=str, default="",
                        help="The port (topic) name used for transmitting orientation coordinates")
    parser.add_argument("--baseline_orientation_coordinates_port", type=str, default="",
                        help="The port (topic) name used for acquiring baseline orientation coordinates from an external source to compute IMU offset")
    parser.add_argument("--flip_pitch", action="store_true", help="Flip the pitch coordinates on publishing")
    parser.add_argument("--flip_yaw", action="store_true", help="Flip the yaw coordinates on publishing")
    parser.add_argument("--flip_roll", action="store_true", help="Flip the roll coordinates on publishing")
    parser.add_argument("--const_pitch_offset", type=float, default=0.0, help="Constant pitch offset in degrees")
    parser.add_argument("--const_yaw_offset", type=float, default=0.0, help="Constant yaw offset in degrees")
    parser.add_argument("--const_roll_offset", type=float, default=0.0, help="Constant roll offset in degrees")
    parser.add_argument("--disable_pitch", action="store_true", help="Disable the pitch coordinates (set to 0.0) on publishing")
    parser.add_argument("--disable_yaw", action="store_true", help="Disable the yaw coordinates (set to 0.0) on publishing")
    parser.add_argument("--disable_roll", action="store_true", help="Disable the roll coordinates (set to 0.0) on publishing")
    parser.add_argument("--mware", type=str, default=WAVESHARE_IMU_DEFAULT_COMMUNICATOR,
                        help="The middleware used for communication. "
                             "This can be overriden by providing either of the following environment variables "
                             "{WRAPYFI_DEFAULT_COMMUNICATOR, WRAPYFI_DEFAULT_MWARE, "
                             "WAVESHARE_IMU_DEFAULT_COMMUNICATOR, WAVESHARE_IMU_DEFAULT_MWARE}. "
                             "Defaults to the Wrapyfi default communicator",
                        choices=MiddlewareCommunicator.get_communicators())
    parser.add_argument("--baseline_mware", type=str, default=WAVESHARE_IMU_DEFAULT_COMMUNICATOR,
                        help="The middleware used for acquiring baseline coordinates for calibrating IMU (computing offset from origin). "
                             "This can be overriden by providing either of the following environment variables "
                             "{WRAPYFI_DEFAULT_COMMUNICATOR, WRAPYFI_DEFAULT_MWARE, "
                             "WAVESHARE_IMU_DEFAULT_COMMUNICATOR, WAVESHARE_IMU_DEFAULT_MWARE}. "
                             "Defaults to the Wrapyfi default communicator",
                        choices=MiddlewareCommunicator.get_communicators())
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    imu = WaveshareIMU(**vars(args))
    imu.runModule()
