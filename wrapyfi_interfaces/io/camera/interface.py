# TODO (fabawi): Parse correct arguments
import logging
import argparse
import time

import os
import cv2
import numpy as np

from wrapyfi.connect.wrapper import MiddlewareCommunicator, DEFAULT_COMMUNICATOR

CAMERA_DEFAULT_COMMUNICATOR = os.environ.get("CAMERA_DEFAULT_COMMUNICATOR", DEFAULT_COMMUNICATOR)
CAMERA_DEFAULT_COMMUNICATOR = os.environ.get("CAMERA_DEFAULT_MWARE", CAMERA_DEFAULT_COMMUNICATOR)

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


class _VideoCapture(cv2.VideoCapture):
    def __init__(self, *args, fps=None, **kwargs):
        super().__init__(*args, **kwargs)


class VideoCapture(MiddlewareCommunicator, _VideoCapture):
    CAP_PROP_FRAME_WIDTH = 320
    CAP_PROP_FRAME_HEIGHT = 240

    def __init__(self, cam_device, cam_feed_port="/camera_reader/camera_feed", cam_feed_carrier="",
                 headless=False,
                 img_width=CAP_PROP_FRAME_WIDTH, img_height=CAP_PROP_FRAME_HEIGHT, fps=30, **kwargs):
        MiddlewareCommunicator.__init__(self)
        if cam_device is not None:
            _VideoCapture.__init__(self, cam_device, **kwargs)
        else:
            _VideoCapture.__init__(self)

        self.headless = headless
        self.cam_feed_port = cam_feed_port
        self.cam_feed_carrier = cam_feed_carrier
        self.cam_device = cam_device

        if img_width is not None:
            self.img_width = img_width
            self.set(cv2.CAP_PROP_FRAME_WIDTH, img_width)
            VideoCapture.CAP_PROP_FRAME_WIDTH = img_width
        if img_height is not None:
            self.img_height = img_height
            self.set(cv2.CAP_PROP_FRAME_HEIGHT, img_height)
            VideoCapture.CAP_PROP_FRAME_HEIGHT = img_height

        self.fps = fps

        if cam_feed_port:
            self.activate_communication(self.acquire_image, "publish")

        self.last_img = None

    @MiddlewareCommunicator.register("Image", CAMERA_DEFAULT_COMMUNICATOR, "VideoCapture", "$cam_feed_port",
                                     carrier="$cam_feed_carrier", width="$img_width", height="$img_height",rgb=True,
                                     should_wait=True)
    def acquire_image(self, cam_feed_port="/cam_mic/cam_feed", cam_feed_carrier="",
                      img_width=CAP_PROP_FRAME_WIDTH, img_height=CAP_PROP_FRAME_HEIGHT, **kwargs):
        if self.isOpened():
            # capture the video stream from the camera
            grabbed, img = self.read()

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
        return 1.0 / self.fps

    def updateModule(self):
        img, = self.acquire_image(cam_feed_port=self.cam_feed_port, cam_feed_carrier=self.cam_feed_carrier,
                                  img_width=self.img_width, img_height=self.img_height)
        if not self.headless:
            cv2.imshow("VideoCapture", img)
            k = cv2.waitKey(33)
            if k == 27:  # Esc key to exit
                exit(0)
            elif k == -1:  # normally -1 returned,so don"t print it
                pass

        return True

    def runModule(self):
        while True:
            self.updateModule()
            # time.sleep(self.getPeriod())

    def __del__(self):
        self.release()


class VideoCaptureReceiver(VideoCapture):
    CAP_PROP_FRAME_WIDTH = 320
    CAP_PROP_FRAME_HEIGHT = 240
    """
    Camera capturer with closer resemblance to cv2.VideoCapture rather than the naming conventions of Wrapyfi interfaces
    """

    def __init__(self, cam_feed_port="/camera_reader/camera_feed", cam_feed_carrier="", headless=False,
                 img_width=CAP_PROP_FRAME_WIDTH, img_height=CAP_PROP_FRAME_HEIGHT, fps=30, **kwargs):
        VideoCapture.__init__(self, None, cam_feed_port="", cam_feed_carrier=cam_feed_carrier,
                              headless=headless, img_width=None, img_height=None,
                              fps=fps, **kwargs)

        self.cam_feed_port = cam_feed_port

        if img_width is not None:
            self.img_width = img_width
            VideoCaptureReceiver.CAP_PROP_FRAME_WIDTH = img_width
        if img_height is not None:
            self.img_height = img_height
            VideoCaptureReceiver.CAP_PROP_FRAME_HEIGHT = img_height

        self.properties = {
            cv2.CAP_PROP_POS_FRAMES: "fpos",
            cv2.CAP_PROP_POS_MSEC: "fpos_msec",
            cv2.CAP_PROP_FPS: "fps",
            cv2.CAP_PROP_FRAME_COUNT: "fcount",
            cv2.CAP_PROP_FRAME_WIDTH: "img_width",
            cv2.CAP_PROP_FRAME_HEIGHT: "img_height"
        }

        self.cam_props = {"cam_feed_port": cam_feed_port,
                          "cam_feed_carrier": cam_feed_carrier,
                          "fpos": 0,
                          "fps": fps,
                          "msec": 1 / fps,
                          "fpos_msec": 0,
                          "fcount": 0,
                          "img_width": self.CAP_PROP_FRAME_WIDTH,
                          "img_height": self.CAP_PROP_FRAME_HEIGHT}

        # control the listening properties from within the app
        if cam_feed_port:
            self.activate_communication(self.acquire_image, "listen")

        self.opened = True

    def retrieve(self):
        try:
            frame_index = self.cam_props["fpos"]
            im, = self.acquire_image(**self.cam_props)
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

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    vid_cap = VideoCaptureReceiver(img_width=640, img_height=480)
    vid_cap.runModule()
