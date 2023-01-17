import os
import time
import argparse
from collections import deque
import logging

import cv2
import numpy as np
import rospy
import pepper_extra.srv

from wrapyfi.connect.wrapper import MiddlewareCommunicator
from wrapyfi_interfaces.utils.filters import mode_smoothing_filter

PEPPER_DEFAULT_COMMUNICATOR = os.environ.get("WRAPYFI_DEFAULT_COMMUNICATOR", "ros")
PEPPER_DEFAULT_COMMUNICATOR = os.environ.get("WRAPYFI_DEFAULT_MWARE", PEPPER_DEFAULT_COMMUNICATOR)
PEPPER_DEFAULT_COMMUNICATOR = os.environ.get("PEPPER_DEFAULT_COMMUNICATOR", PEPPER_DEFAULT_COMMUNICATOR)
PEPPER_DEFAULT_COMMUNICATOR = os.environ.get("PEPPER_DEFAULT_MWARE", PEPPER_DEFAULT_COMMUNICATOR)

"""
Pepper emotion interface

Here we demonstrate 
1. Using the Image messages
2. Run publishers and listeners
3. Utilizing Wrapyfi for creating a port listener only


Run:
    # For the list of keyboard controls, go to the comment [# the keyboard commands for controlling the robot]

"""

EMOTION_LOOKUP = {
    "Neutral": "neu",
    "Happy": "hap",
    "Sad": "sad",
    "Surprise": "sur",
    "Fear": "shy",
    "Disgust": "cun",
    "Anger": "ang",
    "Contempt": "evi"
}

EMOTION_LEDS_LOOKUP = {
    "neu": "white",
    "hap": "green",
    "sad": "blue",
    "sur": "yellow",
    "shy": "cyan",
    "cun": (1.0, 0.5, 0.0),
    "ang": "red",
    "evi": "magenta",
}


class Pepper(MiddlewareCommunicator):

    MWARE = PEPPER_DEFAULT_COMMUNICATOR
    CAP_PROP_FRAME_WIDTH = 640
    CAP_PROP_FRAME_HEIGHT = 480
    LOOP_RATE = 30
    FACIAL_EXPRESSIONS_PORT = "/control_interface/facial_expressions"
    FACIAL_EXPRESSIONS_QUEUE_SIZE = 50
    FACIAL_EXPRESSION_SMOOTHING_WINDOW = 6
    LED_SERVICE = "/pepper/leds/set_rgb"
    SPEECH_TEXT_PORT = "/control_interface/speech_text"
    SPEAKER_SERVICE = "/pepper/speech/say"

    def __init__(self, headless=False, get_cam_feed=True,
                 img_width=CAP_PROP_FRAME_WIDTH, img_height=CAP_PROP_FRAME_HEIGHT,
                 control_expressions=False,
                 set_facial_expressions=True, facial_expressions_port=FACIAL_EXPRESSIONS_PORT,
                 control_speech=False, speech_text_port=SPEECH_TEXT_PORT,
                 mware=MWARE):

        self.__name__ = "Pepper"
        super().__init__()

        self.MWARE = mware
        self.FACIAL_EXPRESSIONS_PORT = facial_expressions_port
        self.SPEECH_TEXT_PORT = speech_text_port
        self.headless = headless
        self.cam_props = {"cam_front_port": "/pepper/camera/front/camera/image_raw"}

        if img_width is not None:
            self.img_width = img_width
            self.CAP_PROP_FRAME_WIDTH = img_width
            self.cam_props["img_width"] = img_width

        if img_height is not None:
            self.img_height = img_height
            self.CAP_PROP_FRAME_HEIGHT = img_height
            self.cam_props["img_height"] = img_height

        if control_expressions:
            # control emotional expressions
            self.last_expression = ["", ""]  # (emotion part on the robot's face , emotional expression category)
            self.expressions_queue = deque(maxlen=self.FACIAL_EXPRESSIONS_QUEUE_SIZE)
            logging.info("Waiting for Pepper LED services...")
            rospy.wait_for_service(self.LED_SERVICE)
            self.srv_set_rgbled = rospy.ServiceProxy(self.LED_SERVICE, pepper_extra.srv.LEDsSetRGB)
            self.update_leds("neu")
            logging.info("Pepper services found")
        else:
            self.activate_communication(self.update_facial_expressions, "disable")

        if control_speech:
            logging.info("Waiting for Pepper speaker services...")
            rospy.wait_for_service(self.SPEAKER_SERVICE)
            self.srv_set_speakertext = rospy.ServiceProxy(self.SPEAKER_SERVICE, pepper_extra.srv.SpeechSay)
            self.update_speaker("Hello, Im pepper")
            logging.info("Pepper speaker services found")
        else:
            self.activate_communication(self.update_speech_text, "disable")

        if get_cam_feed:
            # control the listening properties from within the app
            self.activate_communication(self.receive_images, "listen")
        if facial_expressions_port:
            if set_facial_expressions:
                self.activate_communication(self.acquire_facial_expressions, "publish")
            else:
                self.activate_communication(self.acquire_facial_expressions, "listen")
        if speech_text_port:
            self.activate_communication(self.receive_speech_text, "listen")

        self.build()

    def build(self):
        Pepper.receive_speech_text.__defaults__ = (self.SPEECH_TEXT_PORT, self.MWARE)
        Pepper.update_speech_text.__defaults__ = ("", self.MWARE)
        Pepper.acquire_facial_expressions.__defaults__ = (self.FACIAL_EXPRESSIONS_PORT, None, self.MWARE)
        Pepper.update_facial_expressions.__defaults__ = ("LIGHTS", None, self.MWARE)
        Pepper.receive_images.__defaults__ = (self.CAP_PROP_FRAME_WIDTH, self.CAP_PROP_FRAME_HEIGHT, True)

    @MiddlewareCommunicator.register("NativeObject", "$_mware", "Pepper", "$facial_expressions_port", should_wait=False)
    def acquire_facial_expressions(self, facial_expressions_port=FACIAL_EXPRESSIONS_PORT, cv2_key=None, _mware=MWARE):
        emotion = None
        if cv2_key is None:
            logging.info("Error: Controlling expressions in headless mode not yet supported")
            return None,
        else:
            if cv2_key == 27:  # Esc key to exit
                exit(0)
            elif cv2_key == -1:  # normally -1 returned,so don't logging.info it
                pass
            elif cv2_key == 49:  # 1 key: sad emotion
                emotion = "sad"
                logging.info("Keyed input emotion: sadness")
            elif cv2_key == 50:  # 2 key: angry emotion
                emotion = "ang"
                logging.info("Keyed input emotion: anger")
            elif cv2_key == 51:  # 3 key: happy emotion
                emotion = "hap"
                logging.info("Keyed input emotion: happiness")
            elif cv2_key == 52:  # 4 key: neutral emotion
                emotion = "neu"
                logging.info("Keyed input emotion: neutrality")
            elif cv2_key == 53:  # 5 key: surprise emotion
                emotion = "sur"
                logging.info("Keyed input emotion: surprise")
            elif cv2_key == 54:  # 6 key: shy emotion
                emotion = "shy"
                logging.info("Keyed input emotion: shyness")
            elif cv2_key == 55:  # 7 key: evil emotion
                emotion = "evi"
                logging.info("Keyed input emotion: evilness")
            elif cv2_key == 56:  # 8 key: cunning emotion
                emotion = "cun"
                logging.info("Keyed input emotion: cunningness")
            else:
                return None,
            return {"topic": facial_expressions_port.split("/")[-1],
                    "timestamp": time.time(),
                    "emotion_category": emotion},

    @MiddlewareCommunicator.register("NativeObject", "$_mware", "Pepper", "/pepper_controller/logs/facial_expressions", should_wait=False)
    def update_facial_expressions(self, expression, part="LIGHTS", smoothing="mode", _mware=MWARE):

        if expression is None:
            return None,
        if isinstance(expression, (list, tuple)):
            expression = expression[-1]
        expression = EMOTION_LOOKUP.get(expression, expression)

        if smoothing == "mode":
            self.expressions_queue.append(expression)
            transmitted_expression = mode_smoothing_filter(list(self.expressions_queue), default="neu", window_length=self.FACIAL_EXPRESSION_SMOOTHING_WINDOW)
        else:
            transmitted_expression = expression

        if self.last_expression[0] == part and self.last_expression[1] == transmitted_expression:
            pass
        elif part == "LIGHTS":  # or whatever part you want to control
            self.update_leds(transmitted_expression)

        self.last_expression[0] = part
        self.last_expression[1] = transmitted_expression

        return {"topic": "logging_facial_expressions",
                "timestamp": time.time(),
                "command": f"emotion set to {part} {expression} with smoothing={smoothing}"},

    def update_leds(self, emotion):
        logging.info(f"Showing emotion {emotion}")
        color = EMOTION_LEDS_LOOKUP[emotion]
        r, g, b = color if isinstance(color, tuple) else (0.0, 0.0, 0.0)
        self.srv_set_rgbled('AllLeds', color if isinstance(color, str) else '', r, g, b, 0.5, False)

    @MiddlewareCommunicator.register("NativeObject", "$_mware", "Pepper", "$speech_text_port", should_wait=False)
    def receive_speech_text(self, speech_text_port=SPEECH_TEXT_PORT, _mware=MWARE):
        return None,

    @MiddlewareCommunicator.register("NativeObject", "$_mware", "Pepper", "/pepper_controller/logs/speech_text", should_wait=False)
    def update_speech_text(self, speech_text, _mware=MWARE):
        if isinstance(speech_text, dict):
            try:
                speech_text = speech_text["speech_text"]
            except KeyError:
                speech_text = speech_text["text"]

            self.update_speaker(speech_text)

            return {"topic": "logging_speech_text",
                    "timestamp": time.time(),
                    "command": f"speech set to {speech_text}"},

        else:
            return None,

    def update_speaker(self, speech):
        logging.info(f"Saying {speech}")
        self.srv_set_speakertext(speech, False)

    @MiddlewareCommunicator.register("Image", "ros", "Pepper", "$cam_front_port", width="$img_width", height="$img_height", rgb="$_rgb")
    def receive_images(self, cam_front_port, img_width=CAP_PROP_FRAME_WIDTH, img_height=CAP_PROP_FRAME_HEIGHT, _rgb=True):
        return None,

    def updateModule(self):
        front_cam, = self.receive_images(**self.cam_props)
        if front_cam is None:
            front_cam = np.zeros((self.img_height, self.img_width, 1), dtype="uint8")

        if not self.headless:
            cv2.imshow("PepperCam", front_cam)
            k = cv2.pollKey()
        else:
            k = None

        switch_emotion, = self.acquire_facial_expressions(facial_expressions_port=self.FACIAL_EXPRESSIONS_PORT, cv2_key=k, _mware=self.MWARE)
        if switch_emotion is not None and isinstance(switch_emotion, dict):
            self.update_facial_expressions(switch_emotion.get("emotion_category", None), part=switch_emotion.get("part", "LIGHTS"), _mware=self.MWARE)

        speech_text, = self.receive_speech_text(speech_text_port=self.SPEECH_TEXT_PORT, _mware=self.MWARE)
        if speech_text is not None:
            self.update_speech_text(speech_text, _mware=self.MWARE)

        return True

    def runModule(self):
        period = 1 / self.LOOP_RATE
        while True:
            self.updateModule()
            time.sleep(period)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true", help="Disable CV2 GUI")
    parser.add_argument("--get_cam_feed", action="store_true", help="Get the camera feeds from the robot")
    parser.add_argument("--control_expressions", action="store_true", help="Control the facial expressions")
    parser.add_argument("--set_facial_expressions", action="store_true",
                        help="Publish facial expressions set using keyboard commands")
    parser.add_argument("--facial_expressions_port", type=str, default="/control_interface/facial_expressions",
                        help="The port (topic) name used for receiving and transmitting facial expressions. "
                             "Setting the port name without --set_facial_expressions will only receive the facial expressions")
    parser.add_argument("--control_speech", action="store_true", help="Control the Pepper speakerphone")
    parser.add_argument("--speech_text_port", type=str, default="/control_interface/speech_text",
                        help="The port (topic) name used for receiving text to be spoken by the Pepper")
    parser.add_argument("--mware", type=str, default=PEPPER_DEFAULT_COMMUNICATOR,
                        help="The middleware used for communication. "
                             "This can be overriden by providing either of the following environment variables "
                             "{WRAPYFI_DEFAULT_COMMUNICATOR, WRAPYFI_DEFAULT_MWARE, "
                             "PEPPER_DEFAULT_COMMUNICATOR, PEPPER_DEFAULT_MWARE}. Defaults to 'ros'",
                        choices=MiddlewareCommunicator.get_communicators())
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    assert not (args.headless and args.set_facial_expressions), "Setters require a CV2 window for capturing keystrokes. Disable --set_* for running in headless mode"
    controller = Pepper(**vars(args))
    controller.runModule()
