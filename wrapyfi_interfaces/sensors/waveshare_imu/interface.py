import os
import time

import json
import serial

from wrapyfi.connect.wrapper import MiddlewareCommunicator, DEFAULT_COMMUNICATOR

WAVESHARE_IMU_DEFAULT_COMMUNICATOR = os.environ.get("WAVESHARE_IMU_DEFAULT_COMMUNICATOR", DEFAULT_COMMUNICATOR)
WAVESHARE_IMU_DEFAULT_COMMUNICATOR = os.environ.get("WAVESHARE_IMU_DEFAULT_MWARE", WAVESHARE_IMU_DEFAULT_COMMUNICATOR)

# TODO (fabawi): the ICM-20498 calibration script  https://github.com/WickedLukas/ICM20948/blob/master/ICM20948.cpp
# TODO (fabawi): madgwick filter (post-proc)  https://github.com/WickedLukas/MadgwickAHRS/blob/master/MadgwickAHRS.cpp
# TODO (fabawi): try out https://github.com/mad-lab-fau/imucal for gyroscope calibration
# TODO (fabawi): otherwise, convert this (https://github.com/makerportal/mpu92-calibration) calibrator to work with
#  ICM-20498 through serial instead of i2c since
#   1. we cannot run this code on our pico
#   2. need to run this on a different imu than the one proposed in the tutorial


class IMUPose(MiddlewareCommunicator):
    def __init__(self, ser_device="/dev/ttyACM0", ser_rate=115200):
        super(MiddlewareCommunicator, self).__init__()
        self.ser_device = ser_device
        self.ser_rate = ser_rate
        self.counter = 0
        self.pico = None

    def build(self):
        self.pico = serial.Serial(port=self.ser_device, baudrate=self.ser_rate, timeout=.1)

        self.activate_communication(getattr(self, "read_pose"), "publish")

    @MiddlewareCommunicator.register("NativeObject", WAVESHARE_IMU_DEFAULT_COMMUNICATOR, "IMUPose", "/eye_tracker/IMUPose/head_pose_imu",
                                     carrier="mcast", should_wait=False)
    def read_pose(self):
        try:
            sensor_data = self.pico.readline().decode("utf-8")
            imu_data = json.loads(sensor_data)
            imu_data.update(topic="imu_orientation", world_index=self.counter, imu_timestamp=time.time())
            self.counter += 1
        except:
            imu_data = None
        return imu_data,

    def getPeriod(self):
        return 0.01

    def updateModule(self):
        imu_data, = self.read_pose()
        if imu_data is not None and isinstance(imu_data, dict):
            print(imu_data)
        else:
            print(imu_data)
        return True

    def runModule(self):
        if self.pico is None:
            self.build()
        while True:
            try:
                self.updateModule()
                time.sleep(self.getPeriod())
            except:
                break

    def __del__(self):
        if self.pico is not None:
            self.pico.close()


if __name__ == "__main__":
    imu = IMUPose(ser_device="/dev/ttyACM0")
    imu.runModule()
