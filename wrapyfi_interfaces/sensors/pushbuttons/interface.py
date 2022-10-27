import os
import time
import threading
import json

import cv2
import serial

from wrapyfi.connect.wrapper import MiddlewareCommunicator, DEFAULT_COMMUNICATOR

PUSHBUTTON_DEFAULT_COMMUNICATOR = os.environ.get("PUSHBUTTON_DEFAULT_COMMUNICATOR", DEFAULT_COMMUNICATOR)
PUSHBUTTON_DEFAULT_COMMUNICATOR = os.environ.get("PUSHBUTTON_DEFAULT_MWARE", PUSHBUTTON_DEFAULT_COMMUNICATOR)

WINDOW_RESOLUTION = (320, 240)


class PushButton(MiddlewareCommunicator):
    def __init__(self, ser_device="/dev/ttyACM0", ser_rate=115200, btn_source=0, headless=False,
                 set_btn_press=True, btn_press_port="/push_button/command",
                 set_btn_light=True, btn_light_port="/push_button/button_light"):
        super(MiddlewareCommunicator, self).__init__()
        
        self.lock = threading.Lock()
        
        self.ser_device = ser_device
        self.ser_rate = ser_rate
        self.headless = headless
        
        if ser_device:
            self.arduino = serial.Serial(port=ser_device, baudrate=ser_rate, timeout=.1)
            if set_btn_light and btn_light_port:
                self.activate_communication(self.update_button_light, mode="publish")
            elif btn_light_port:
                self.activate_communication(self.update_button_light, mode="listen")
            
        else:
            if btn_light_port:
                    self.activate_communication(self.update_button_light, mode="disable")
            else:
                self.activate_communication(self.update_button_light, mode="disable")
        
        
        if set_btn_press and btn_press_port:
                self.activate_communication(self.acquire_button_press, mode="publish")
        elif btn_press_port:
            self.activate_communication(self.acquire_button_press, mode="listen")
        
        # self.activate_communication(self.receive_message, mode="listen")
        
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
    def update_button_light(self, light, interval=1, ):
        try:
            self.arduino.write(bytes(light.get("signal", "0"), "utf-8"))
            time.sleep(interval)
            sensor = self.arduino.readline().decode("utf-8")
            buttons = json.loads(sensor)
            buttons.update(**{"timestamp": time.time())
        except:
            buttons = None
        return buttons,

    @MiddlewareCommunicator.register("NativeObject", PUSHBUTTON_DEFAULT_COMMUNICATOR,
                                     "PushButton", "/push_button/command",
                                     carrier="", should_wait=False)
    def acquire_button_press(self, signal=None, cv2_key=None):
        if signal=None and cv2_key is None:
            # TODO (fabawi): listen to stdin for keypress
            logging.error("controlling button in headless mode not yet supported")
            return None,
        elif signal is None:
            if cv2_key == 27:  # Esc key to exit
                exit(0)
            elif cv2_key == -1:  # normally -1 returned,so don"t print it
                pass
            elif cv2_key == 49:  # 1 key: sad emotion
                signal = "smart on"
                logging.info("switching smart button ON")
            elif cv2_key == 50:  # 2 key: angry emotion
                signal = "smart off"
                logging.info("switching smart button OFF")
            elif cv2_key == 51:  # 1 key: sad emotion
                signal = "sad"
                logging.info("switching random button ON")
            elif cv2_key == 52:  # 2 key: angry emotion
                signal = "smart"
                logging.info("switching random button OFF")
            else:
                logging.info(cv2_key)  # else print its value
                return None,
        signal = self.button_mappings.get(signal, 0)  # random number indicating a return request from button
        with self.lock:
            self.last_button.update(**{"signal": str(signal),
                                       "timestamp": time.time()})
        return self.last_button,
                              
    @MiddlewareCommunicator.register("NativeObject", PUSHBUTTON_DEFAULT_COMMUNICATOR,
                                     "PushButton", "/push_button/logs/wait_for_button",
                                     carrier="", should_wait=False)
    def wait_for_button(self):
        while True:
            time.sleep(3)
            btn_resp, = self.update_button_light(self.last_button)
            if btn_resp and isinstance(btn_resp, dict):
                if btn_resp.get(self.button_mappings["led_smart"], 1000) == 0:
                    trigger="smart"
                    with self.lock:
                        self.last_button.update(**{"trigger": trigger,
                                                   "signal": str(self.button_mappings["led_smart"]),
                                                   "timestamp": time.time()})
                    break
                if btn_resp.get(self.button_mappings["led_random"], 1000) == 0:
                    trigger="random"
                    with self.lock:
                        self.last_button.update(**{"trigger": trigger,
                                                   "signal": str(self.button_mappings["led_random"]),
                                                   "timestamp": time.time()})
                    break
        return {"topic": "logging_wait_for_button",
                "timestamp": self.last_button["timestamp"],
                "command": f"waiting for button response completed with button trigger={trigger}"},

    

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
        if not self.headless:
            instruction_window = np.zeros((WINDOW_RESOLUTION[1], WINDOW_RESOLUTION[0], 1), dtype="uint8")
            font = cv2.FONT_HERSHEY_SIMPLEX
            text = "Press 1 to switch ON the SMART button and 2 to switch OFF. Press 3 to switch ON the RANDOM button and 4 to switch OFF"

            # get boundary of this text
            textsize = cv2.getTextSize(text, font, 1, 2)[0]

            # get coords based on boundary
            textX = (img.shape[1] - textsize[0]) / 2
            textY = (img.shape[0] + textsize[1]) / 2

            # add text centered on image
            cv2.putText(img, text, (textX, textY ), font, 1, (255, 255, 255), 2)
            cv2.imshow("PushButton", instruction_window)
        else:
            k=None
        button_cmd, = self.acquire_button_press(cv2_key=k)
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
        if hasattr(self, "arduino"):
            self.arduino.close()

# TODO (fabawi): main
