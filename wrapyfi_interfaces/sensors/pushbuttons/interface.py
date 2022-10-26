import os
import time

import json
import serial

from wrapyfi.connect.wrapper import MiddlewareCommunicator, DEFAULT_COMMUNICATOR

PUSHBUTTON_DEFAULT_COMMUNICATOR = os.environ.get("PUSHBUTTON_DEFAULT_COMMUNICATOR", DEFAULT_COMMUNICATOR)
PUSHBUTTON_DEFAULT_COMMUNICATOR = os.environ.get("PUSHBUTTON_DEFAULT_MWARE", PUSHBUTTON_DEFAULT_COMMUNICATOR)


class PushButton(MiddlewareCommunicator):
    def __init__(self, ser_device="/dev/ttyACM0", ser_rate=115200):
        super(MiddlewareCommunicator, self).__init__()
        self.ser_device = ser_device
        self.ser_rate = ser_rate

        self.arduino = serial.Serial(port=ser_device, baudrate=ser_rate, timeout=.1)

        self.activate_communication(self.update_button_light, mode="publish")
        self.activate_communication(self.receive_button_command, mode="listen")
        self.activate_communication(self.receive_message, mode="listen")

    @MiddlewareCommunicator.register("NativeObject", PUSHBUTTON_DEFAULT_COMMUNICATOR,
                                     "PushButton", "/push_button/button_light",
                                     carrier="", should_wait=False)
    def update_button_light(self, signal, interval=1):
        try:
            self.arduino.write(bytes(signal.get("signal", "0"), 'utf-8'))
            time.sleep(interval)
            sensor = self.arduino.readline().decode("utf-8")
            buttons = json.loads(sensor)
        except:
            buttons = False
        return buttons,

    @MiddlewareCommunicator.register("NativeObject", PUSHBUTTON_DEFAULT_COMMUNICATOR,
                                     "PushButton", "/push_button/command",
                                     carrier="", should_wait=False)
    def receive_button_command(self):
        return None,

    @MiddlewareCommunicator.register("NativeObject", PUSHBUTTON_DEFAULT_COMMUNICATOR,
                                     "PushButton", "/push_button/message",
                                     carrier="mcast", should_wait=False)
    def receive_message(self):
        return None,

    @staticmethod
    def check_exit(message):
        if message.get("signal", "none") == "exit":
            exit(0)

    def getPeriod(self):
        return 1

    def updateModule(self):
        button_msg, = self.receive_message()
        if button_msg is not None and isinstance(button_msg, dict):
            self.check_exit(button_msg)
        self.update_button_light({"signal": "0"})
        button_cmd, = self.receive_button_command()
        if button_cmd is not None and isinstance(button_cmd, dict):
            self.update_button_light(button_cmd)
        return True

    def runModule(self):
        while True:
            try:
                self.updateModule()
                time.sleep(self.getPeriod())
            except:
                break

    def __del__(self):
        self.arduino.close()

# TODO (fabawi): main