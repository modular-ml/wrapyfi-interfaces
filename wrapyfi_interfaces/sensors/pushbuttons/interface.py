import os
import time

import threading
import json
import serial

from wrapyfi.connect.wrapper import MiddlewareCommunicator, DEFAULT_COMMUNICATOR

PUSHBUTTON_DEFAULT_COMMUNICATOR = os.environ.get("PUSHBUTTON_DEFAULT_COMMUNICATOR", DEFAULT_COMMUNICATOR)
PUSHBUTTON_DEFAULT_COMMUNICATOR = os.environ.get("PUSHBUTTON_DEFAULT_MWARE", PUSHBUTTON_DEFAULT_COMMUNICATOR)


class PushButton(MiddlewareCommunicator):
    def __init__(self, ser_device="/dev/ttyACM0", ser_rate=115200, btn_source=0):
        super(MiddlewareCommunicator, self).__init__()
        
        self.lock = threading.Lock()
        
        self.ser_device = ser_device
        self.ser_rate = ser_rate

        self.arduino = serial.Serial(port=ser_device, baudrate=ser_rate, timeout=.1)

        self.activate_communication(self.update_button_light, mode="publish")
        self.activate_communication(self.receive_button_command, mode="listen")
        self.activate_communication(self.receive_message, mode="listen")
        
        self.button_mappings = {
            "led_smart": "LED1" if btn_source == 0 else "LED2",
            "on_smart": 49 if btn_source == 0 else 51,
            "off_smart": 48 if btn_source == 0 else 50,
            "led_random": "LED1" if btn_source == 1 else "LED2",
            "on_random": 49 if btn_source == 1 else 51,
            "off_random": 48 if btn_source == 1 else 50,
            0: "off",
            1: "on"
        }
        
        self.last_button = {"signal": None,
                            "time": time.time()}

    @MiddlewareCommunicator.register("NativeObject", PUSHBUTTON_DEFAULT_COMMUNICATOR,
                                     "PushButton", "/push_button/button_light",
                                     carrier="", should_wait=False)
    def update_button_light(self, signal, interval=1):
        try:
            self.arduino.write(bytes(signal.get("signal", "0"), 'utf-8'))
            time.sleep(interval)
            sensor = self.arduino.readline().decode("utf-8")
            buttons = json.loads(sensor)
            buttons.update(**{"timestamp": time.time())
        except:
            buttons = False
        return buttons,

    @MiddlewareCommunicator.register("NativeObject", PUSHBUTTON_DEFAULT_COMMUNICATOR,
                                     "PushButton", "/push_button/command",
                                     carrier="", should_wait=False)
    def acquire_button_press(self, signal):
        signal = self.button_mappings.get(signal, 0)  # random number indicating a return request from button
        with self.lock:
            self.last_button.update(**{"signal": str(signal),
                                       "timestamp": time.time()})
        return self.last_button,
    
    def wait_for_button(self):
        while True:
            time.sleep(3)
            btn_resp, = self.update_button_light(self.last_button)
            if btn_resp and isinstance(btn_resp, dict):
                if btn_resp.get(self.button_mappings["led_smart"], 1000) == 0:
                    with self.lock:
                        self.last_button.update(**{"trigger": "smart",
                                                   "signal": str(self.button_mappings["led_smart"]),
                                                   "time": time.time()})
                    break
                if btn_resp.get(self.button_mappings["led_random"], 1000) == 0:
                    with self.lock:
                        self.last_button.update(**{"trigger": "random",
                                                   "signal": str(self.button_mappings["led_random"]),
                                                   "time": time.time()})
                    break
    

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
        button_cmd, = self.read_button_press()
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
