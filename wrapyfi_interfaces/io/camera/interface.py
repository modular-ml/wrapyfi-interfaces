# TODO (fabawi): fix soon. Not working at the moment
import logging
import argparse
import time

import os
import cv2
import numpy as np

from wrapyfi.connect.wrapper import MiddlewareCommunicator, DEFAULT_COMMUNICATOR

CAMERA_DEFAULT_COMMUNICATOR = os.environ.get("CAMERA_DEFAULT_COMMUNICATOR", DEFAULT_COMMUNICATOR)
CAMERA_DEFAULT_COMMUNICATOR = os.environ.get("CAMERA_DEFAULT_MWARE", CAMERA_DEFAULT_COMMUNICATOR)

CAMERA_RESOLUTION = (320, 240)

"""
Video/Image and Audio listener + publisher. This is an extension of cam_mic.py to stream videos and images from 
files as well. 
COMING SOON: Audio file reading support
Here we demonstrate 
1. Using the Image and AudioChunk messages
2. Single return wrapper functionality in conjunction with synchronous callbacks
3. The spawning of multiple processes specifying different functionality for listeners and publishers
Run:
    # Alternative 1
    # On machine 1 (or process 1): The audio stream publishing
    python3 audio_video.py --mode publish --stream audio --aud-source 0
    # On machine 2 (or process 2): The video stream publishing
    python3 audio_video.py --mode publish --stream video --img-source 0
    # On machine 3 (or process 3): The audio stream listening
    python3 audio_video.py --mode listen --stream audio
    # On machine 4 (or process 4): The video stream listening
    python3 audio_video.py --mode listen --stream video

    # Alternative 2 (concurrent audio and video publishing)
    # On machine 1 (or process 1): The audio/video stream publishing
    python3 audio_video.py --mode publish --stream audio video --img-source 0 --aud-source 0
    # On machine 2 (or process 2): The audio/video stream listening
    python3 audio_video.py --mode listen --stream audio video
"""


class VideoCapture(cv2.VideoCapture):
    def __init__(self, *args, fps=None, **kwargs):
        super().__init__(*args, **kwargs)


class MwareVideoCapture(MiddlewareCommunicator):
    CAP_PROP_FRAME_WIDTH = 320
    CAP_PROP_FRAME_HEIGHT = 240
    """
    Camera capturer with closer resemblance to cv2.VideoCapture rather than the naming conventions of Wrapyfi interfaces
    """

    def __init__(self, camera="/camera_reader/camera_feed", fps=30,
                 width=CAP_PROP_FRAME_WIDTH, height=CAP_PROP_FRAME_HEIGHT, *args, **kwargs):
        super(MiddlewareCommunicator, self).__init__()

        self.properties = {
            cv2.CAP_PROP_POS_FRAMES: "fpos",
            cv2.CAP_PROP_POS_MSEC: "fpos_msec",
            cv2.CAP_PROP_FPS: "fps",
            cv2.CAP_PROP_FRAME_COUNT: "fcount",
            cv2.CAP_PROP_FRAME_WIDTH: "width",
            cv2.CAP_PROP_FRAME_HEIGHT: "height"
        }
        MwareVideoCapture.CAP_PROP_FRAME_WIDTH = width
        MwareVideoCapture.CAP_PROP_FRAME_HEIGHT = height

        self.cam_props = {"camera_port": camera,
                          "fpos": 0,
                          "fps": fps,
                          "msec": 1 / fps,
                          "fpos_msec": 0,
                          "fcount": 0,
                          "width": self.CAP_PROP_FRAME_WIDTH,
                          "height": self.CAP_PROP_FRAME_HEIGHT}

        # control the listening properties from within the app
        if camera:
            self.activate_communication(self.receive_image, "listen")

        self.opened = True

    @MiddlewareCommunicator.register("Image", CAMERA_DEFAULT_COMMUNICATOR,
                                     "MwareVideoCapture", "$camera_port",
                                     carrier="", width="$width", height="$height", rgb=True)
    def receive_image(self, camera_port, width=CAP_PROP_FRAME_WIDTH, height=CAP_PROP_FRAME_HEIGHT, **kwargs):
        return None,

    def retrieve(self):
        try:
            frame_index = self.cam_props["fpos"]
            im, = self.receive_image(**self.cam_props)
            self.opened = True
            self.cam_props["fpos"] = frame_index + 1
            self.cam_props["fpos_msec"] = self.cam_props["fpos_msec"] + (frame_index + 1) * self.cam_props["msec"]
            return True, im
        except:
            self.opened = False
            return False, None

    def grab(self):
        return self.retrieve()[0]

    def read(self):
        return self.retrieve()

    def isOpened(self):
        return self.opened

    def release(self):
        pass

    def set(self, propId, value):
        self.cam_props[self.properties[propId]] = value

    def get(self, propId):
        return self.cam_props[self.properties[propId]]

    def getPeriod(self):
        return self.cam_props["msec"]

    def runModule(self):

    def updateModule(self):


class Camera(MiddlewareCommunicator):
    def __init__(self, headless=False, get_cam_feed=True, cam_feed_port="/camera_reader/camera_feed",
                 cam_device=0, img_width=CAMERA_RESOLUTION[0], img_height=CAMERA_RESOLUTION[1], img_fps=30):
        super(MiddlewareCommunicator, self).__init__()

        self.headless = headless
        self.cam_feed_port = cam_feed_port

        self.cam_device = cam_device
        self.img_width = img_width
        self.img_height = img_height
        self.img_fps = img_fps

        self.vid_cap = cv2.VideoCapture(cam_device)
        if cam_feed_port:
            if get_cam_feed:
                self.activate_communication(self.read_image, "listen")
            else:
                self.activate_communication(self.read_image, "publish")

        self.last_img = None

    @MiddlewareCommunicator.register("Image", "Camera", "$cam_feed_port",
                                     carrier="$cam_feed_carrier", rgb=True, should_wait=True)
    def write_image(self, cam_feed_port="/cam_mic/cam_feed", cam_feed_carrier=""):
        if self.vid_cap.isOpened():
            # capture the video stream from the camera
            grabbed, img = self.vid_cap.read()

            if not grabbed:
                logging.warning("video not grabbed")
                img = np.random.random((self.img_width, self.img_height, 3)) * 255 if self.last_img is None \
                    else self.last_img
            else:
                self.last_img = img
                logging.info("video grabbed")
        else:
            logging.error("video capturer not opened")
            img = np.random.random((self.img_width, self.img_height, 3)) * 255
        return img,

    def getPeriod(self):
        return 1.0 / self.img_fps

    def updateModule(self):
        self.read_image()
        return True

    def capture_cam_mic(self):
        self.collect_cam()

    def __del__(self):
        if self.vid_cap:
            self.vid_cap.release()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="publish", choices={"publish", "listen"},
                        help="The transmission mode")
    parser.add_argument("--stream", nargs="+", default=["video", "audio"], choices={"video", "audio"},
                        help="The streamed sensor data")
    parser.add_argument("--img-port", type=str, default="/cam_mic/cam_feed",
                        help="The YARP port for publishing/receiving the image")
    parser.add_argument("--img-port-connect", type=str, default="/cam_mic/cam_feed:out",
                        help="The connection name for the output image port")
    parser.add_argument("--img-source", type=str, default="0",
                        help="The video capture device id (int camera id | str video path | str image path)")
    parser.add_argument("--img-width", type=int, default=320, help="The image width")
    parser.add_argument("--img-height", type=int, default=240, help="The image height")
    parser.add_argument("--img-fps", type=int, default=30, help="The video frames per second")
    parser.add_argument("--aud-port", type=str, default="/cam_mic/audio_feed",
                        help="The YARP port for publishing/receiving the audio")
    parser.add_argument("--aud-port-connect", type=str, default="/cam_mic/mic_feed:out",
                        help="The connection name for the output audio port")
    parser.add_argument("--aud-source", type=str, default="0", help="The audio capture device id (int microphone id)")
    parser.add_argument("--aud-rate", type=int, default=44100, help="The audio sampling rate")
    parser.add_argument("--aud-channels", type=int, default=1, help="The audio channels")
    parser.add_argument("--aud-chunk", type=int, default=10000, help="The transmitted audio chunk size")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        args.img_device = int(args.img_device)
    except:
        args.img_device = args.img_device

    cam_mic = Camera(img_width=args.img_width, img_height=args.img_height,
                     img_fps=args.img_fps)

    # update default params of functions because publisher and listener ports are set before function calls
    cam_mic.collect_cam = functools.partial(cam_mic.collect_cam,
                                            img_port=args.img_port, img_port_connect=args.img_port_connect)
    cam_mic.collect_mic = functools.partial(cam_mic.collect_mic,
                                            aud_port=args.aud_port, aud_port_connect=args.aud_port_connect)

    if args.mode == "publish":
        cam_mic.activate_communication(CamMic.collect_cam, mode="publish")
        cam_mic.activate_communication(CamMic.collect_mic, mode="publish")
        cam_mic.capture_cam_mic()
    if args.mode == "listen":
        cam_mic.activate_communication(CamMic.collect_cam, mode="listen")
        cam_mic.activate_communication(CamMic.collect_mic, mode="listen")

        while True:
            if "audio" in args.stream:
                aud, = cam_mic.collect_mic()
            else:
                aud = None
            if "video" in args.stream:
                img, = cam_mic.collect_cam()
            else:
                img = None
            if img is not None:
                cv2.imshow("Received Image", img)
                cv2.waitKey(1)
            if aud is not None:
                print(aud)
                sd.play(aud[0].flatten(), samplerate=aud[1])
                sd.wait(1)