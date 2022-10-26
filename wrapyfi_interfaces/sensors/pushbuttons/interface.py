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

        self.activate_communication("control_button", mode="publish")
        self.activate_communication("triggered_button", mode="listen")
        self.activate_communication("triggered_round", mode="listen")

    @MiddlewareCommunicator.register("NativeObject", PUSHBUTTON_DEFAULT_COMMUNICATOR,
                                     "PushButton", "/hri_sorter_game/buttonLightSwitch",
                                     carrier="", should_wait=False)
    def control_button(self, signal, interval=1):
        try:
            self.arduino.write(bytes(signal.get("signal", "0"), 'utf-8'))
            time.sleep(interval)
            sensor = self.arduino.readline().decode("utf-8")
            buttons = json.loads(sensor)
        except:
            buttons = False
        return buttons,

    @MiddlewareCommunicator.register("NativeObject", PUSHBUTTON_DEFAULT_COMMUNICATOR,
                                     "PushButton", "/hri_sorter_game/buttonTrigger",
                                     carrier="", should_wait=False)
    def triggered_button(self):
        return False,

    @MiddlewareCommunicator.register("NativeObject", PUSHBUTTON_DEFAULT_COMMUNICATOR,
                                     "PushButton", "/hri_sorter_game/roundTrigger",
                                     carrier="mcast", should_wait=False)
    def triggered_round(self):
        return False,

    @staticmethod
    def update_round(switch_round):
        if switch_round.get("signal", "none") == "exit":
            exit(0)

    def runModule(self):
        while True:
            try:
                switch_round, = self.triggered_round()
                if switch_round and isinstance(switch_round, dict):
                    self.update_round(switch_round)
                self.control_button({"signal": "0"})
                button_cmd, = self.triggered_button()
                if button_cmd and isinstance(button_cmd, dict):
                    self.control_button(button_cmd)
            except:
                break

    def __del__(self):
        self.arduino.close()

