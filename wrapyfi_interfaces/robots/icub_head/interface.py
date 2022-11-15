import os
import time
import argparse
import logging
from collections import deque

import cv2
import numpy as np
import yarp

try:
    import pexpect
    HAVE_PEXPECT = True
except ImportError:
    HAVE_PEXPECT = False
    
from wrapyfi.connect.wrapper import MiddlewareCommunicator
from wrapyfi_interfaces.utils.transformations import cartesian_to_spherical
from wrapyfi_interfaces.utils.filters import mode_smoothing_filter


ICUB_DEFAULT_COMMUNICATOR = os.environ.get("WRAPYFI_DEFAULT_COMMUNICATOR", "yarp")
ICUB_DEFAULT_COMMUNICATOR = os.environ.get("WRAPYFI_DEFAULT_MWARE", ICUB_DEFAULT_COMMUNICATOR)
ICUB_DEFAULT_COMMUNICATOR = os.environ.get("ICUB_DEFAULT_COMMUNICATOR", ICUB_DEFAULT_COMMUNICATOR)
ICUB_DEFAULT_COMMUNICATOR = os.environ.get("ICUB_DEFAULT_MWARE", ICUB_DEFAULT_COMMUNICATOR)


"""
ICub head controller and camera viewer

Here we demonstrate 
1. Using the Image messages
2. Run publishers and listeners in concurrence with the yarp.RFModule
3. Utilizing Wrapyfi for creating a port listener only


Run:
    # For the list of keyboard controls, refer to the comments in acquire_... prefixed methods [# the keyboard commands for controlling the robot]
    
    # Alternative 1 (simulation)
    # Ensure that the `iCub_SIM` is running in a standalone terminal
    # Listener shows images and coordinates are published without Wrapyfi's utilities
    python3 icub_head.py --simulation --get_cam_feed --control_head --control_expressions
    
    # Alternative 2 (physical robot)
    # Listener shows images and coordinates are published without Wrapyfi's utilities
    python3 icub_head.py --get_cam_feed --control_head --control_expressions
    
"""

EMOTION_LOOKUP = {
    "Neutral": [("LIGHTS", "neu")],
    "Happy": [("LIGHTS", "hap")],
    "Sad": [("LIGHTS", "sad")],
    "Surprise": [("LIGHTS", "sur")],
    "Fear": [("raw", "L04"), ("raw", "R04"), ("raw", "M66")],  # change to array
    "Disgust": [("raw", "L01"), ("raw", "R01"), ("raw", "M66")],  # change to array
    "Anger": [("LIGHTS", "ang")],
    "Contempt": [("raw", "L01"), ("raw", "R09"), ("raw", "ME9")],  # change to array
    "Cunning": [("LIGHTS", "cun")],
    "Shy": [("LIGHTS", "shy")],
    "Evil": [("LIGHTS", "evi")]
}


class ICub(MiddlewareCommunicator, yarp.RFModule):
    MWARE = ICUB_DEFAULT_COMMUNICATOR
    CAP_PROP_FRAME_WIDTH = 320
    CAP_PROP_FRAME_HEIGHT = 240
    HEAD_EYE_COORDINATES_PORT = "/control_interface/head_eye_coordinates"
    GAZE_PLANE_COORDINATES_PORT = "/control_interface/gaze_plane_coordinates"
    FACIAL_EXPRESSIONS_PORT = "/control_interface/facial_expressions"
    # constants
    FACIAL_EXPRESSIONS_QUEUE_SIZE = 50
    FACIAL_EXPRESSION_SMOOTHING_WINDOW = 6

    def __init__(self, simulation=False, headless=False, get_cam_feed=True,
                 img_width=CAP_PROP_FRAME_WIDTH, img_height=CAP_PROP_FRAME_HEIGHT,
                 control_head=True,
                 set_head_eye_coordinates=True, head_eye_coordinates_port=HEAD_EYE_COORDINATES_PORT,
                 ikingaze=False,
                 gaze_plane_coordinates_port=GAZE_PLANE_COORDINATES_PORT,
                 control_expressions=False,
                 set_facial_expressions=True, facial_expressions_port=FACIAL_EXPRESSIONS_PORT,
                 mware=MWARE):
        self.__name__ = "iCubController"
        MiddlewareCommunicator.__init__(self)
        yarp.RFModule.__init__(self)

        self.MWARE = mware
        self.FACIAL_EXPRESSIONS_PORT = facial_expressions_port
        self.GAZE_PLANE_COORDINATES_PORT = gaze_plane_coordinates_port
        self.HEAD_EYE_COORDINATES_PORT = head_eye_coordinates_port

        self.headless = headless
        self.ikingaze = ikingaze

        # prepare a property object   
        props = yarp.Property()
        props.put("device", "remote_controlboard")
        props.put("local", "/client/head")

        if simulation:
            props.put("remote", "/icubSim/head")
            self.cam_props = {"cam_world_port": "/icubSim/cam",
                              "cam_left_port": "/icubSim/cam/left",
                              "cam_right_port": "/icubSim/cam/right"}
            emotion_cmd = f"yarp rpc /icubSim/face/emotions/in"
        else:
            props.put("remote", "/icub/head")
            self.cam_props = {"cam_world_port": "/icub/cam/left",
                              "cam_left_port": "/icub/cam/left",
                              "cam_right_port": "/icub/cam/right"}
            emotion_cmd = f"yarp rpc /icub/face/emotions/in"

        if img_width is not None:
            self.img_width = img_width
            self.CAP_PROP_FRAME_WIDTH = img_width
            self.cam_props["img_width"] = img_width

        if img_height is not None:
            self.img_height = img_height
            self.CAP_PROP_FRAME_HEIGHT = img_height
            self.cam_props["img_height"] = img_height

        if control_expressions:
            if HAVE_PEXPECT:
                # control emotional expressions using RPC
                self.client = pexpect.spawn(emotion_cmd)
            else:
                logging.error("pexpect must be installed to control the emotion interface")
                self.activate_communication(self.update_facial_expressions, "disable")

            self.last_expression = ["", ""]  # (emotion part on the robot's face , emotional expression category)
            self.expressions_queue = deque(maxlen=self.FACIAL_EXPRESSIONS_QUEUE_SIZE)
        else:
            self.activate_communication(self.update_facial_expressions, "disable")
                
        self._curr_eyes = [0, 0, 0]
        self._curr_head = [0, 0, 0]
        
        if control_head:
            if ikingaze:
                self._gaze_encs = yarp.Vector(3, 0.0)
                props_gaze = yarp.Property()
                props_gaze.clear()
                props_gaze.put("device", "gazecontrollerclient")
                props_gaze.put("remote", "/iKinGazeCtrl")
                props_gaze.put("local", "/client/gaze")
                #
                self._gaze_driver = yarp.PolyDriver(props_gaze)

                self._igaze = self._gaze_driver.viewIGazeControl()
                self._igaze.setStabilizationMode(True)

                # set movement speed
                # self.update_speed_gaze(head_speed=0.8, eyes_speed=0.5)
                
            else:
                # create remote driver
                self._head_driver = yarp.PolyDriver(props)

                # query motor control interfaces
                self._ipos = self._head_driver.viewIPositionControl()
                self._ienc = self._head_driver.viewIEncoders()

                # retrieve number of joints
                self._num_jnts = self._ipos.getAxes()

                logging.info(f"controlling {self._num_jnts} joints")

                # read encoders
                self._encs = yarp.Vector(self._num_jnts)
                self._ienc.getEncoders(self._encs.data())

                # set movement speed
                # self.update_speed_gaze(head_speed=(10.0, 10.0, 20.0), eyes_speed=(10.0, 10.0, 20.0))

        else:
            self.activate_communication(self.reset_gaze, "disable")
            self.activate_communication(self.update_gaze_speed, "disable")
            self.activate_communication(self.control_gaze, "disable")
            self.activate_communication(self.wait_for_gaze, "disable")
            self.activate_communication(self.control_gaze_at_plane, "disable")
            
        if get_cam_feed:
            # control the listening properties from within the app
            self.activate_communication(self.receive_images, "listen")
        if facial_expressions_port:
            if set_facial_expressions:
                self.activate_communication(self.acquire_facial_expressions, "publish")
            else:
                self.activate_communication(self.acquire_facial_expressions, "listen")
        if head_eye_coordinates_port:
            if set_head_eye_coordinates:
                self.activate_communication(self.acquire_head_eye_coordinates, "publish")
            else:
                self.activate_communication(self.acquire_head_eye_coordinates, "listen")
        if gaze_plane_coordinates_port:
            self.activate_communication(self.control_gaze_at_plane, "listen")

        self.build()

    def build(self):
        """
        Updates the default method arguments according to constructor arguments. This method is called by the module constructor.
        It is not necessary to call it manually.
        """
        ICub.acquire_head_eye_coordinates.__defaults__ = (self.HEAD_EYE_COORDINATES_PORT, None, self.MWARE)
        ICub.receive_gaze_plane_coordinates.__defaults__ = (self.GAZE_PLANE_COORDINATES_PORT, self.MWARE)
        ICub.wait_for_gaze.__defaults__ = (True, self.MWARE)
        ICub.reset_gaze.__defaults__ = (self.MWARE,)
        ICub.update_gaze_speed.__defaults__ = ((10.0, 10.0, 20.0), (20.0, 20.0, 20.0), self.MWARE)
        ICub.control_gaze.__defaults__ = ((0, 0, 0), (0, 0, 0), self.MWARE)
        ICub.control_gaze_at_plane.__defaults__ = ((0, 0,), (0.3, 0.3), True, True, self.MWARE)
        ICub.acquire_facial_expressions.__defaults__ = (self.FACIAL_EXPRESSIONS_PORT, None, self.MWARE)
        ICub.update_facial_expressions.__defaults__ = (False, None, self.MWARE)
        ICub.receive_images.__defaults__ = (self.CAP_PROP_FRAME_WIDTH, self.CAP_PROP_FRAME_HEIGHT, True)



    @MiddlewareCommunicator.register("NativeObject", "$_mware",
                                     "ICub", "$head_eye_coordinates_port",
                                     should_wait=False)
    def acquire_head_eye_coordinates(self, head_eye_coordinates_port=HEAD_EYE_COORDINATES_PORT, cv2_key=None,
                                     _mware=MWARE):
        """
        Acquire head and eye coordinates for controlling the iCub.
        :param head_eye_coordinates_port: str: Port to receive head and eye coordinates
        :param cv2_key: int: Key pressed by the user
        :return: dict: Head and eye coordinates
        """

        if cv2_key is None:
            # TODO (fabawi): listen to stdin for keypress
            logging.error("controlling orientation in headless mode not yet supported")
            return None,
        else:
            if cv2_key == 27:  # Esc key to exit
                exit(0)
            elif cv2_key == -1:  # normally -1 returned,so don"t print it
                pass
            # the keyboard commands for controlling the robot
            elif cv2_key == 82:  # Up key
                self._curr_head[0] += 1
                logging.info("head pitch up")
            elif cv2_key == 84:  # Down key
                self._curr_head[0] -= 1
                logging.info("head pitch down")
            elif cv2_key == 83:  # Right key
                self._curr_head[2] -= 1
                logging.info("head yaw left")
            elif cv2_key == 81:  # Left key
                self._curr_head[2] += 1
                logging.info("head yaw right")
            elif cv2_key == 97:  # A key
                self._curr_head[1] -= 1
                logging.info("head roll right")
            elif cv2_key == 100:  # D key
                self._curr_head[1] += 1
                logging.info("head roll left")
            elif cv2_key == 119:  # W key
                self._curr_eyes[0] += 1
                logging.info("eye pitch up")
            elif cv2_key == 115:  # S key
                self._curr_eyes[0] -= 1
                logging.info("eye pitch down")
            elif cv2_key == 122:  # Z key
                self._curr_eyes[1] -= 1
                logging.info("eye yaw left")
            elif cv2_key == 99:  # C key
                self._curr_eyes[1] += 1
                logging.info("eye yaw right")
            elif cv2_key == 114:  # R key: reset the orientation
                self._curr_eyes = [0, 0, 0]
                self._curr_head = [0, 0, 0]
                self.reset_gaze()
                logging.info("resetting the orientation")
            else:
                logging.info(cv2_key)  # else print its value

            return {"topic": head_eye_coordinates_port.split("/")[-1],
                    "timestamp": time.time(),
                    "head": self._curr_head,
                    "eyes": self._curr_eyes},

    @MiddlewareCommunicator.register("NativeObject", "$_mware",
                                     "ICub", "$gaze_plane_coordinates_port",
                                     should_wait=False)
    def receive_gaze_plane_coordinates(self, gaze_plane_coordinates_port=GAZE_PLANE_COORDINATES_PORT, _mware=MWARE):
        """
        Receive gaze plane (normalized x,y) coordinates for controlling the iCub.
        :param gaze_plane_coordinates_port: str: Port to receive gaze plane coordinates
        :return: dict: Gaze plane coordinates
        """
        return None,

    @MiddlewareCommunicator.register("NativeObject", "$_mware",
                                     "ICub", "/icub_controller/logs/wait_for_gaze",
                                     should_wait=False)
    def wait_for_gaze(self, reset=True, _mware=MWARE):
        """
        Wait for the gaze actuation to complete.
        :param reset: bool: Whether to reset the gaze location (centre)
        :param _mware: str: Middleware to use
        :return: dict: Gaze waiting log for a given time step
        """
        if self.ikingaze:
            # self._igaze.clearNeckPitch()
            # self._igaze.clearNeckRoll()
            # self._igaze.clearNeckYaw()
            # self._igaze.clearEyes()
            if reset:
                self._igaze.lookAtAbsAngles(self._gaze_encs)
            self._igaze.waitMotionDone(timeout=2.0)
        else:
            if reset:
                self._ipos.positionMove(self._encs.data())
                while not self._ipos.checkMotionDone():
                    pass
        return {"topic": "logging_wait_for_gaze",
                "timestamp": time.time(),
                "command": f"waiting for gaze completed with reset={reset}"},

    @MiddlewareCommunicator.register("NativeObject", "$_mware",
                                     "ICub", "/icub_controller/logs/reset_gaze",
                                     should_wait=False)
    def reset_gaze(self, _mware=MWARE):
        """
        Reset the eyes to their original position.
        :param _mware: str: Middleware to use
        :return: dict: Gaze reset log for a given time step
        """
        self.wait_for_gaze(reset=True)
        return {"topic": "logging_reset_gaze",
            "timestamp": time.time(),
            "command": f"reset gaze"},
        
    @MiddlewareCommunicator.register("NativeObject", "$mware",
                                     "ICub", "/icub_controller/logs/head_eye_speed",
                                     should_wait=False)
    def update_gaze_speed(self, head_speed=(10.0, 10.0, 20.0), eyes_speed=(20.0, 20.0, 20.0), _mware=MWARE):
        """
        Control the iCub head and eye speeds.
        :param head_speed: tuple(float->pitch[deg/s], float->yaw[deg/s], float->roll[deg/s]) or float->speed[0,1]:
                            Head orientation speed or float for neck speed (norm) when using iKinGaze
        :param eyes_speed: tuple(float->pitch[deg/s], float->yaw[deg/s], float->vergence[deg/sec]) or float->speed[0,1]:
                            Eyes orientation speed or float for eyes speed (norm) when using iKinGaze
        :param _mware: str: Middleware to use
        :return: dict: Orientation speed log for a given time step
        """
        if self.ikingaze:
            if isinstance(head_speed, tuple):
                head_speed = head_speed[0]
                logging.warning("iKinGaze only supports one speed for the neck, using the first value")
            if isinstance(eyes_speed, tuple):
                eyes_speed = eyes_speed[0]
                logging.warning("iKinGaze only supports one speed for the eyes, using the first value")
            self._igaze.setNeckTrajTime(head_speed)
            self._igaze.setEyesTrajTime(eyes_speed)
        else:
            self._ipos.setRefSpeed(0, head_speed[0])
            self._ipos.setRefSpeed(1, head_speed[1])
            self._ipos.setRefSpeed(2, head_speed[2])
            self._ipos.setRefSpeed(3, eyes_speed[0])
            self._ipos.setRefSpeed(4, eyes_speed[1])
            self._ipos.setRefSpeed(5, eyes_speed[2])
        
        return {"topic": "logging_head_eye_speed",
                "timestamp": time.time(), 
                "command": f"head set to {head_speed} and eyes set to {eyes_speed}"},
    
    @MiddlewareCommunicator.register("NativeObject", "$_mware",
                                     "ICub", "/icub_controller/logs/head_eye_coordinates",
                                     should_wait=False)
    def control_gaze(self, head=(0, 0, 0), eyes=(0, 0, 0), _mware=MWARE):
        """
        Control the iCub head or eyes.
        :param head: tuple(float->pitch[deg], float->yaw[deg], float->roll[deg]): Head orientation coordinates
        :param eyes: tuple(float->pitch[deg], float->yaw[deg], float->vergence[0,1]): Eyes orientation coordinates
        :param _mware: str: Middleware to use
        :return: dict: Orientation coordinates log for a given time step
        """
        # wait for the action to complete
        # self.wait_for_gaze(reset=False)

        # initialize a new tmp vector identical to encs
        self.init_pos = yarp.Vector(self._num_jnts, self._encs.data())

        # head control
        self.init_pos.set(0, self.init_pos.get(0) + head[0])  # tilt/pitch
        self.init_pos.set(1, self.init_pos.get(1) + head[1])  # swing/roll
        self.init_pos.set(2, self.init_pos.get(2) + head[2])  # pan/yaw
        # eye control
        self.init_pos.set(3, self.init_pos.get(3) + eyes[0])  # eye tilt
        self.init_pos.set(4, self.init_pos.get(4) + eyes[1])  # eye pan
        self.init_pos.set(5, self.init_pos.get(5) + eyes[2]) # the divergence between the eyes (to align, set to 0)

        self._ipos.positionMove(self.init_pos.data())
        self._curr_head = list(head)
        self._curr_eyes = list(eyes)

        return {"topic": "logging_head_eye_coordinates",
                "timestamp": time.time(), 
                "command": f"head set to {head} and eyes set to {eyes}"},

    @MiddlewareCommunicator.register("NativeObject", "$_mware",
                                     "ICub", "/icub_controller/logs/gaze_plane_coordinates",
                                     should_wait=False)
    def control_gaze_at_plane(self, xy=(0, 0,), limiting_consts_xy=(0.3, 0.3), control_eyes=True, control_head=True,
                              _mware=MWARE):
        """
        Gaze at specific point in a normalized plane in front of the iCub.
        :param xy: tuple(float->x[-1,1],float->y[-1,1]): Position limited to the range of -1 (bottom left) and 1 (top right)
        :param limiting_consts_xy: tuple(float->x[0,1],float->y[0,1]): Limiting constants for the x and y coordinates
        :param control_eyes: bool: Whether to control the eyes of the robot directly
        :param control_head: bool: Whether to control the head of the robot directly
        :return: dict: Gaze coordinates log for a given time step
        """
        # wait for the action to complete
        # self.wait_for_gaze(reset=False)

        xy = np.array(xy) * np.array(limiting_consts_xy)  # limit viewing region
        ptr = cartesian_to_spherical((1, xy[0], -xy[1]))
        # initialize a new tmp vector identical to encs
        ptr_degrees = (np.rad2deg(ptr[0]), np.rad2deg(ptr[1]))

        if control_eyes and control_head:
            if not self.ikingaze:
                logging.error("Set ikingaze=True in order to move eyes and head simultaneously")
                return
            self.init_pos_ikin = yarp.Vector(3, self._gaze_encs.data())
            self.init_pos_ikin.set(0, ptr_degrees[0])
            self.init_pos_ikin.set(1, ptr_degrees[1])
            self.init_pos_ikin.set(2, 0.0)
            self._igaze.lookAtAbsAngles(self.init_pos_ikin)

        elif control_head:
            self.control_gaze(head=(ptr_degrees[1], 0, ptr_degrees[0]))
        elif control_eyes:
            self.control_gaze(eyes=(ptr_degrees[1], ptr_degrees[0], 0))

        return {"topic": "logging_gaze_plane_coordinates",
                "timestamp": time.time(),
                "command": f"moving gaze toward {ptr_degrees} with head={control_head} and eyes={control_eyes}"},

    @MiddlewareCommunicator.register("NativeObject", "$_mware",
                                     "ICub", "$facial_expressions_port",
                                     should_wait=False)
    def acquire_facial_expressions(self, facial_expressions_port=FACIAL_EXPRESSIONS_PORT, cv2_key=None,
                                   _mware=MWARE):
        """
        Acquire facial expressions from the iCub.
        :param facial_expressions_port: str: Port to acquire facial expressions from
        :param cv2_key: int: Key to press to set the facial expression
        :return: dict: Facial expressions log for a given time step
        """
        emotion = None
        if cv2_key is None:
            # TODO (fabawi): listen to stdin for keypress
            logging.error("controlling expressions in headless mode not yet supported")
            return None,
        else:
            if cv2_key == 27:  # Esc key to exit
                exit(0)
            elif cv2_key == -1:  # normally -1 returned,so don"t print it
                pass
            elif cv2_key == 48:  # 0 key: Neutral emotion
                emotion = "Neutral"
                logging.info("expressing neutrality")
            elif cv2_key == 49:  # 1 key: Happy emotion
                emotion = "Happy"
                logging.info("expressing happiness")
            elif cv2_key == 50:  # 2 key: Sad emotion
                emotion = "Sad"
                logging.info("expressing sadness")
            elif cv2_key == 51:  # 3 key: Surprise emotion
                emotion = "Surprise"
                logging.info("expressing surprise")
            elif cv2_key == 52:  # 4 key: Fear emotion
                emotion = "Fear"
                logging.info("expressing fear")
            elif cv2_key == 53:  # 5 key: Disgust emotion
                emotion = "Disgust"
                logging.info("expressing disgust")
            elif cv2_key == 54:  # 6 key: Anger emotion
                emotion = "Anger"
                logging.info("expressing anger")
            elif cv2_key == 55:  # 7 key: Contempt emotion
                emotion = "Contempt"
                logging.info("expressing contempt")
            elif cv2_key == 56:  # 8 key: Cunning emotion
                emotion = "Cunning"
                logging.info("expressing cunningness")
            elif cv2_key == 57:  # 9 key: Shy emotion
                emotion = "Shy"
                logging.info("expressing shyness")
            else:
                logging.info(cv2_key)  # else print its value
                return None,
            return {"topic": facial_expressions_port.split("/")[-1],
                    "timestamp": time.time(),
                    "emotion_category": emotion},
    
    @MiddlewareCommunicator.register("NativeObject", "$_mware",
                                     "ICub", "/icub_controller/logs/facial_expressions",
                                     should_wait=False)
    def update_facial_expressions(self, expression, part=False, smoothing="mode", _mware=MWARE):
        """
        Control facial expressions of the iCub.
        :param expression: str: Expression to be controlled
        :param expression: str or tuple(str->part, str->emotion) or list[str] or list[tuple(str->part, str->emotion)]:
                            Expression/s abbreviation or matching lookup table entry.
                            If a list is provided, the actions are executed in sequence
        :param part: str: Abbreviation describing parts to control (refer to iCub documentation) ( mou, eli, leb, reb, all, raw, LIGHTS)
        :param smoothing: str: Name of smoothing filter to avoid abrupt changes in emotional expressions
        :return: Emotion log for a given time step
        """
        if expression is None:
            return None,

        if isinstance(expression, (list, tuple)):
            expression = expression[-1]

        if smoothing == "mode":
            self.expressions_queue.append(expression)
            transmitted_expression = mode_smoothing_filter(list(self.expressions_queue),
                                                      window_length=self.FACIAL_EXPRESSION_SMOOTHING_WINDOW)
        else:
            transmitted_expression = expression

        expressions_lookup = EMOTION_LOOKUP.get(transmitted_expression, transmitted_expression)
        if isinstance(expressions_lookup, str):
            expressions_lookup = [(part if part else "all", expressions_lookup)]

        if self.last_expression[0] == (part if part else "all") and self.last_expression[1] == transmitted_expression:
            expressions_lookup = []

        for (part_lookup, expression_lookup) in expressions_lookup:
            if part_lookup == "LIGHTS":
                self.client.sendline(f"set leb {expression_lookup}")
                self.client.expect(">>")
                self.client.sendline(f"set reb {expression_lookup}")
                self.client.expect(">>")
                self.client.sendline(f"set mou {expression_lookup}")
                self.client.expect(">>")
            else:
                self.client.sendline(f"set {part_lookup} {expression_lookup}")
                self.client.expect(">>")

        self.last_expression[0] = part
        self.last_expression[1] = transmitted_expression

        return {"topic": "logging_facial_expressions",
                "timestamp": time.time(), 
                "command": f"emotion set to {part} {expression} with smoothing={smoothing}"},

    @MiddlewareCommunicator.register("Image", "yarp", "ICub", "$cam_world_port",
                                     width="$img_width", height="$img_height", rgb="$_rgb")
    @MiddlewareCommunicator.register("Image", "yarp", "ICub", "$cam_left_port",
                                     width="$img_width", height="$img_height", rgb="$_rgb")
    @MiddlewareCommunicator.register("Image", "yarp", "ICub", "$cam_right_port",
                                     width="$img_width", height="$img_height", rgb="$_rgb")
    def receive_images(self, cam_world_port, cam_left_port, cam_right_port,
                       img_width=CAP_PROP_FRAME_WIDTH, img_height=CAP_PROP_FRAME_HEIGHT, _rgb=True):
        """
        Receive images from the iCub.
        :param cam_world_port: str: Port to receive images from the world camera
        :param cam_left_port: str: Port to receive images from the left camera
        :param cam_right_port: str: Port to receive images from the right camera
        :param img_width: int: Width of the image
        :param img_height: int: Height of the image
        :param _rgb: bool: Whether the image is RGB or not
        :return: Images from the iCub
        """
        external_cam, left_cam, right_cam = None, None, None
        return external_cam, left_cam, right_cam

    def getPeriod(self):
        """
        Get the period of the module.
        :return: float: Period of the module
        """
        return 0.01

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
            cv2.imshow("ICubCam", np.concatenate((left_cam, external_cam, right_cam), axis=1))
            k = cv2.waitKey(30)
        else:
            k = None

        switch_emotion, = self.acquire_facial_expressions(facial_expressions_port=self.FACIAL_EXPRESSIONS_PORT,
                                                          cv2_key=k, _mware=self.MWARE)
        if switch_emotion is not None and isinstance(switch_emotion, dict):
            self.update_facial_expressions(switch_emotion.get("emotion_category", None),
                                           part=switch_emotion.get("part", False), _mware=self.MWARE)

        move_robot, = self.acquire_head_eye_coordinates(head_eye_coordinates_port=self.HEAD_EYE_COORDINATES_PORT,
                                                        cv2_key=k, _mware=self.MWARE)
        if move_robot is not None and isinstance(move_robot, dict):
            self.update_gaze_speed(head_speed=move_robot.get("head_speed", (10.0, 10.0, 20.0)),
                                eyes_speed=move_robot.get("eyes_speed", (10.0, 10.0, 20.0)), _mware=self.MWARE)
            if move_robot.get("reset_gaze", False):
                self.reset_gaze()
            self.control_gaze(head=move_robot.get("head", (0, 0, 0)), eyes=move_robot.get("eyes", (0, 0, 0)),
                              _mware=self.MWARE)

        move_robot, = self.receive_gaze_plane_coordinates(gaze_plane_coordinates_port=self.GAZE_PLANE_COORDINATES_PORT,
                                                          _mware=self.MWARE)
        if move_robot is not None and isinstance(move_robot, dict):
            self.update_gaze_speed(head_speed=move_robot.get("head_speed", (10.0, 10.0, 20.0) if not self.ikingaze else 0.8),
                                   eyes_speed=move_robot.get("eyes_speed", (10.0, 10.0, 20.0) if not self.ikingaze else 0.5),
                                   _mware=self.MWARE)
            if move_robot.get("reset_gaze", False):
                self.reset_gaze()
            self.control_gaze_at_plane(xy=move_robot.get("xy", (0, 0)),
                                        limiting_consts_xy=move_robot.get("limiting_consts_xy", (0.3, 0.3)),
                                        control_head=move_robot.get("control_head", False if not self.ikingaze else True),
                                        control_eyes=move_robot.get("control_eyes", True), _mware=self.MWARE),

        return True


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulation", action="store_true", help="Run in simulation")
    parser.add_argument("--headless", action="store_true", help="Disable CV2 GUI")
    parser.add_argument("--ikingaze", action="store_true", help="Enable iKinGazeCtrl")
    parser.add_argument("--get_cam_feed", action="store_true", help="Get the camera feeds from the robot")
    parser.add_argument("--control_head", action="store_true", help="Control the head and eyes")
    parser.add_argument("--set_head_eye_coordinates", action="store_true",
                        help="Publish head+eye coordinates set using keyboard commands")
    parser.add_argument("--head_eye_coordinates_port", type=str, default="",
                        help="The port (topic) name used for receiving and transmitting head and eye orientation "
                             "Setting the port name without --set_head_eye_coordinates will only receive the coordinates")
    parser.add_argument("--gaze_plane_coordinates_port", type=str, default="",
                        help="The port (topic) name used for receiving plane coordinates in 2D for robot to look at")
    parser.add_argument("--control_expressions", action="store_true", help="Control the facial expressions")
    parser.add_argument("--set_facial_expressions", action="store_true",
                        help="Publish facial expressions set using keyboard commands")
    parser.add_argument("--facial_expressions_port", type=str, default="",
                        help="The port (topic) name used for receiving and transmitting facial expressions. "
                             "Setting the port name without --set_facial_expressions will only receive the facial expressions")
    parser.add_argument("--mware", type=str, default=ICUB_DEFAULT_COMMUNICATOR,
                        help="The middleware used for communication. "
                             "This can be overriden by providing either of the following environment variables "
                             "{WRAPYFI_DEFAULT_COMMUNICATOR, WRAPYFI_DEFAULT_MWARE, "
                             "ICUB_DEFAULT_COMMUNICATOR, ICUB_DEFAULT_MWARE}. Defaults to 'yarp'",
                        choices=MiddlewareCommunicator.get_communicators())
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    assert not (args.headless and (args.set_facial_expressions or args.set_head_eye_coordinates)), \
        "setters require a CV2 window for capturing keystrokes. Disable --set-... for running in headless mode"
    # TODO (fabawi): add RPC support for controlling the robot and not just facial expressions. Make it optional
    controller = ICub(**vars(args))
    controller.runModule()
