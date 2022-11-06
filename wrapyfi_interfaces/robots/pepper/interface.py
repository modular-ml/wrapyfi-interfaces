import os
import time
import argparse
import logging
from collections import deque

import cv2
import numpy as np

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


class Pepper(MiddlewareCommunicator):
    MWARE = PEPPER_DEFAULT_COMMUNICATOR
    CAP_PROP_FRAME_WIDTH = 640
    CAP_PROP_FRAME_HEIGHT = 480
    FACIAL_EXPRESSIONS_PORT = "/control_interface/facial_expressions"
    # constants
    FACIAL_EXPRESSIONS_QUEUE_SIZE = 50
    FACIAL_EXPRESSION_SMOOTHING_WINDOW = 6

    def __init__(self, simulation=False, headless=False, get_cam_feed=True,
                 img_width=CAP_PROP_FRAME_WIDTH, img_height=CAP_PROP_FRAME_HEIGHT,
                 control_expressions=False,
                 set_facial_expressions=True, facial_expressions_port=FACIAL_EXPRESSIONS_PORT,
                 mware=MWARE):
        self.__name__ = "Pepper"
        MiddlewareCommunicator.__init__(self)

        self.MWARE = mware
        self.FACIAL_EXPRESSIONS_PORT = facial_expressions_port

        self.headless = headless

        if simulation:
            # TODO: PLACE CAM PROPS IN DICT
            self.cam_props = {"cam_world_port": "/Sim/cam",
                              "cam_left_port": "/Sim/cam/left",
                              "cam_right_port": "/Sim/cam/right"}
        else:
            self.cam_props = {"cam_world_port": "/Robot/cam/left",
                              "cam_left_port": "/Robot/cam/left",
                              "cam_right_port": "/Robot/cam/right"}

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
            # TODO: DECLARE VARS FOR CONTROLLING EXPRESSIONS
            self.last_expression = ["", ""]  # (emotion part on the robot's face , emotional expression category)
            self.expressions_queue = deque(maxlen=self.FACIAL_EXPRESSIONS_QUEUE_SIZE)
        else:
            self.activate_communication(self.update_facial_expressions, "disable")

        if get_cam_feed:
            # control the listening properties from within the app
            self.activate_communication(self.receive_images, "listen")
        if facial_expressions_port:
            if set_facial_expressions:
                self.activate_communication(self.acquire_facial_expressions, "publish")
            else:
                self.activate_communication(self.acquire_facial_expressions, "listen")
        self.build()

    def build(self):
        Pepper.acquire_facial_expressions.__defaults__ = (self.FACIAL_EXPRESSIONS_PORT, None, self.MWARE)
        Pepper.update_facial_expressions.__defaults__ = ("LIGHTS", None, self.MWARE)
        Pepper.receive_images.__defaults__ = (self.CAP_PROP_FRAME_WIDTH, self.CAP_PROP_FRAME_HEIGHT, True)

    @MiddlewareCommunicator.register("NativeObject", "$_mware",
                                     "Pepper", "$facial_expressions_port",
                                     should_wait=False)
    def acquire_facial_expressions(self, facial_expressions_port=FACIAL_EXPRESSIONS_PORT, cv2_key=None,
                                   _mware=MWARE):
        emotion = None
        if cv2_key is None:
            logging.error("controlling expressions in headless mode not yet supported")
            return None,
        else:
            if cv2_key == 27:  # Esc key to exit
                exit(0)
            elif cv2_key == -1:  # normally -1 returned,so don"t print it
                pass
            # TODO: REPLACE emotion WITH STRING UNDERSTOOD BY PEPPER
            elif cv2_key == 49:  # 1 key: sad emotion
                emotion = "sad"
                logging.info("expressing sadness")
            elif cv2_key == 50:  # 2 key: angry emotion
                emotion = "ang"
                logging.info("expressing anger")
            elif cv2_key == 51:  # 3 key: happy emotion
                emotion = "hap"
                logging.info("expressing happiness")
            elif cv2_key == 52:  # 4 key: neutral emotion
                emotion = "neu"
                logging.info("expressing neutrality")
            elif cv2_key == 53:  # 5 key: surprise emotion
                emotion = "sur"
                logging.info("expressing surprise")
            elif cv2_key == 54:  # 6 key: shy emotion
                emotion = "shy"
                logging.info("expressing shyness")
            elif cv2_key == 55:  # 7 key: evil emotion
                emotion = "evi"
                logging.info("expressing evilness")
            elif cv2_key == 56:  # 8 key: cunning emotion
                emotion = "cun"
                logging.info("expressing cunningness")
            else:
                logging.info(cv2_key)  # else print its value
                return None,
            return {"topic": facial_expressions_port.split("/")[-1],
                    "timestamp": time.time(),
                    "emotion_category": emotion},

    @MiddlewareCommunicator.register("NativeObject", "$_mware",
                                     "Pepper", "/pepper_controller/logs/facial_expressions",
                                     should_wait=False)
    def update_facial_expressions(self, expression, part="LIGHTS", smoothing="mode", _mware=MWARE):
        """
        Control facial expressions of the Pepper
        :param expression: Expression abbreviation
        :param part: Abbreviation describing parts to control
        :param smoothing: Name of smoothing filter to avoid abrupt changes in emotional expressions
        :return: None
        """
        if expression is None:
            return None,
        if isinstance(expression, (list, tuple)):
            expression = expression[-1]
        expression = EMOTION_LOOKUP.get(expression, expression)

        if smoothing == "mode":
            self.expressions_queue.append(expression)
            transmitted_expression = mode_smoothing_filter(list(self.expressions_queue),
                                                           window_length=self.FACIAL_EXPRESSION_SMOOTHING_WINDOW)
        else:
            transmitted_expression = expression

        if self.last_expression[0] == part and self.last_expression[1] == transmitted_expression:
            pass
        elif part == "LIGHTS":  # or whatever part you want to control
            # TODO: CONTROLLING THE ROBOT FACIAL EXPRESSION HAPPENS HERE
            pass
        else:
            # TODO: CONTROLLING THE ROBOT FACIAL EXPRESSION HAPPENS HERE
            pass

        self.last_expression[0] = part
        self.last_expression[1] = transmitted_expression

        return {"topic": "logging_facial_expressions",
                "timestamp": time.time(),
                "command": f"emotion set to {part} {expression} with smoothing={smoothing}"},

    @MiddlewareCommunicator.register("Image", "ros", "Pepper", "$cam_world_port",
                                     width="$img_width", height="$img_height", _rgb="$rgb")
    @MiddlewareCommunicator.register("Image", "ros", "Pepper", "$cam_left_port",
                                     width="$img_width", height="$img_height", _rgb="$rgb")
    @MiddlewareCommunicator.register("Image", "ros", "Pepper", "$cam_right_port",
                                     width="$img_width", height="$img_height", _rgb="$rgb")
    def receive_images(self, cam_world_port, cam_left_port, cam_right_port,
                       img_width=CAP_PROP_FRAME_WIDTH, img_height=CAP_PROP_FRAME_HEIGHT, _rgb=True):
        external_cam, left_cam, right_cam = None, None, None
        return external_cam, left_cam, right_cam

    def getPeriod(self):
        return 0.03

    def updateModule(self):
        # print(self.getPeriod())
        external_cam, left_cam, right_cam = self.receive_images(**self.cam_props)
        if external_cam is None:
            external_cam = np.zeros((self.img_height, self.img_width, 1), dtype="uint8")
            left_cam = np.zeros((self.img_height, self.img_width, 1), dtype="uint8")
            right_cam = np.zeros((self.img_height, self.img_width, 1), dtype="uint8")
        else:
            external_cam = cv2.cvtColor(external_cam, cv2.COLOR_BGR2RGB)
            left_cam = cv2.cvtColor(left_cam, cv2.COLOR_BGR2RGB)
            right_cam = cv2.cvtColor(right_cam, cv2.COLOR_BGR2RGB)
        if not self.headless:
            cv2.imshow("PepperCam", np.concatenate((left_cam, external_cam, right_cam), axis=1))
            k = cv2.waitKey(30)
        else:
            k = None

        switch_emotion, = self.acquire_facial_expressions(facial_expressions_port=self.FACIAL_EXPRESSIONS_PORT,
                                                          cv2_key=k, _mware=self.MWARE)
        if switch_emotion is not None and isinstance(switch_emotion, dict):
            self.update_facial_expressions(switch_emotion.get("emotion_category", None),
                                           part=switch_emotion.get("part", "LIGHTS"), _mware=self.MWARE)

        return True

    def runModule(self):
        while True:
            self.updateModule()
            time.sleep(self.getPeriod())

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulation", action="store_true", help="Run in simulation")
    parser.add_argument("--headless", action="store_true", help="Disable CV2 GUI")
    parser.add_argument("--get_cam_feed", action="store_true", help="Get the camera feeds from the robot")
    parser.add_argument("--control_expressions", action="store_true", help="Control the facial expressions")
    parser.add_argument("--set_facial_expressions", action="store_true",
                        help="Publish facial expressions set using keyboard commands")
    parser.add_argument("--facial_expressions_port", type=str, default="",
                        help="The port (topic) name used for receiving and transmitting facial expressions. "
                             "Setting the port name without --set_facial_expressions will only receive the facial expressions")
    parser.add_argument("--mware", type=str, default=PEPPER_DEFAULT_COMMUNICATOR,
                        help="The middleware used for communication. "
                             "This can be overriden by providing either of the following environment variables "
                             "{WRAPYFI_DEFAULT_COMMUNICATOR, WRAPYFI_DEFAULT_MWARE, "
                             "PEPPER_DEFAULT_COMMUNICATOR, PEPPER_DEFAULT_MWARE}. Defaults to 'ros'",
                        choices=MiddlewareCommunicator.get_communicators())
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    assert not (args.headless and (args.set_facial_expressions or args.set_head_eye_coordinates)), \
        "setters require a CV2 window for capturing keystrokes. Disable --set-... for running in headless mode"
    controller = Pepper(**vars(args))
    controller.runModule()
