import os
import time
import argparse
import json
import functools

import serial
from wrapyfi.connect.wrapper import MiddlewareCommunicator, DEFAULT_COMMUNICATOR


WAVESHARE_IMU_DEFAULT_COMMUNICATOR = os.environ.get("WAVESHARE_IMU_DEFAULT_COMMUNICATOR", DEFAULT_COMMUNICATOR)
WAVESHARE_IMU_DEFAULT_COMMUNICATOR = os.environ.get("WAVESHARE_IMU_DEFAULT_MWARE", WAVESHARE_IMU_DEFAULT_COMMUNICATOR)


class WaveshareIMU(MiddlewareCommunicator):
    MWARE = WAVESHARE_IMU_DEFAULT_COMMUNICATOR
    HEAD_EYE_COORDINATES_PORT = "/control_interface/head_eye_coordinates"

    def __init__(self, ser_device="/dev/ttyACM0", ser_rate=115200,
                 head_eye_coordinates_port=HEAD_EYE_COORDINATES_PORT,
                 mware=MWARE):
        super(MiddlewareCommunicator, self).__init__()

        self.MWARE = mware
        self.HEAD_EYE_COORDINATES_PORT = head_eye_coordinates_port

        self.ser_device = ser_device
        self.ser_rate = ser_rate

        self.counter = 0
        if ser_device and ser_rate:
            self.pico = serial.Serial(port=self.ser_device, baudrate=self.ser_rate, timeout=.1)
        else:
            self.pico = None
        if self.HEAD_EYE_COORDINATES_PORT:
            self.activate_communication(self.read_orientation, "publish")

        self.build()

    def build(self):
        WaveshareIMU.read_orientation.__defaults__ = (self.HEAD_EYE_COORDINATES_PORT, self.MWARE)

    @MiddlewareCommunicator.register("NativeObject", "$_mware", "WaveshareIMU",
                                     "$head_eye_coordinates_port", should_wait=False)
    def read_orientation(self, head_eye_coordinates_port=HEAD_EYE_COORDINATES_PORT, _mware=MWARE):
        try:
            sensor_data = self.pico.readline().decode("utf-8")
            imu_data = json.loads(sensor_data)
            imu_data.update(topic=head_eye_coordinates_port.split("/")[-1],
                            world_index=self.counter,
                            timestamp=time.time())
            self.counter += 1
        except:
            imu_data = None
        return imu_data,

    def getPeriod(self):
        return 0.01

    def updateModule(self):
        imu_data, = self.read_orientation(head_eye_coordinates_port=self.HEAD_EYE_COORDINATES_PORT, _mware=self.MWARE)
        if imu_data is not None and isinstance(imu_data, dict):
            print(imu_data)
        else:
            print(imu_data)
        return True

    def runModule(self):
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
    parser.add_argument("--head_eye_coordinates_port", type=str, default="",
                        help="The port (topic) name used for transmitting head and eye orientation coordinates")
    parser.add_argument("--mware", type=str, default=WAVESHARE_IMU_DEFAULT_COMMUNICATOR,
                        help="The middleware used for communication. "
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
