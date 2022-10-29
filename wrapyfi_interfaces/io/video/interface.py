# TODO (fabawi): Parse correct arguments
import logging
import argparse
import time
from queue import Queue
from threading import Thread

import os
import cv2
import numpy as np

from wrapyfi.connect.wrapper import MiddlewareCommunicator, DEFAULT_COMMUNICATOR
from wrapyfi_interfaces.utils import str_or_int

CAMERA_DEFAULT_COMMUNICATOR = os.environ.get("CAMERA_DEFAULT_COMMUNICATOR", DEFAULT_COMMUNICATOR)
CAMERA_DEFAULT_COMMUNICATOR = os.environ.get("CAMERA_DEFAULT_MWARE", CAMERA_DEFAULT_COMMUNICATOR)

"""
Video/Image and Camera listener + publisher. This is an extension of mic.py to stream videos and images from 
files as well. 
Here we demonstrate 
1. Using the Image messages
2. Single return wrapper functionality in conjunction with synchronous callbacks
3. The spawning of multiple processes specifying different functionality for listeners and publishers
Run:
    # On machine 1 (or process 1): The video stream publishing
    python3 interface.py --cap_source 0
    # On machine 2 ... N (or process 2 ... N): The video stream listening
    python3 interface.py
"""


class _VideoCapture(cv2.VideoCapture):
    def __init__(self, *args, fps=None, **kwargs):
        super().__init__(*args, **kwargs)


class VideoCapture(MiddlewareCommunicator, _VideoCapture):
    """
        Video capturer with closer resemblance to cv2.VideoCapture rather than the naming conventions of
        Wrapyfi interfaces. To invoke Wrapyfi functionality (publishing to a port), set the cap_feed_port and trigger
        the runModule() (automatically invoked in standalone mode), or call the acquire_image() method with all necessary
        arguments. when invoking the acquire_image method directly, make sure to pass all port (topic) arguments.
        Calling retrieve() and read() automatically invokes acquire_image with constructor arguments (e.g. image_width)
        automatically passed
    """
    CAP_PROP_FRAME_WIDTH = 320
    CAP_PROP_FRAME_HEIGHT = 240
    SHOULD_WAIT = False

    def __init__(self, cap_source, cap_feed_port="/video_reader/video_feed", cap_feed_carrier="",
                 headless=False, should_wait=False, multithreading=True, queue_size=10, force_resize=False,
                 img_width=CAP_PROP_FRAME_WIDTH, img_height=CAP_PROP_FRAME_HEIGHT, fps=30, **kwargs):
        MiddlewareCommunicator.__init__(self)

        VideoCapture.SHOULD_WAIT = should_wait
        self.multithreading = multithreading
        self.force_resize = force_resize

        if cap_source:
            cap_source = str_or_int(cap_source)
            _VideoCapture.__init__(self, cap_source, **kwargs)

        else:
            _VideoCapture.__init__(self, **kwargs)

        if img_width:
            self.img_width = img_width
            self.set(cv2.CAP_PROP_FRAME_WIDTH, img_width)
            VideoCapture.CAP_PROP_FRAME_WIDTH = img_width
        if img_height:
            self.img_height = img_height
            self.set(cv2.CAP_PROP_FRAME_HEIGHT, img_height)
            VideoCapture.CAP_PROP_FRAME_HEIGHT = img_height
        if fps:
            self.fps = fps
            try:
                self.set(cv2.CAP_PROP_FPS, fps)
                pass
            except cv2.error:
                logging.error("cannot set fps")
        else:
            self.fps = 1

        self.headless = headless
        self.cap_feed_port = cap_feed_port
        self.cap_feed_carrier = cap_feed_carrier
        self.cap_source = cap_source

        if cap_feed_port:
            self.activate_communication(self.acquire_image, "publish")

        self.last_img = None

        if multithreading:
            self.queue = Queue(maxsize=queue_size)
            self.thread = Thread(target=self.update, args=())
            self.thread.daemon = True
            self.thread.start()

    def update(self, **kwargs):
        while True:
            if not self.isOpened():
                break

            if not self.queue.full():
                grabbed, img = super().read(**kwargs)

                if not grabbed:
                    self.release(force=False)

                self.queue.put(img)
            else:
                time.sleep(0.1)

        self.release(force=False)

    @MiddlewareCommunicator.register("Image", CAMERA_DEFAULT_COMMUNICATOR, "VideoCapture", "$cap_feed_port",
                                     carrier="$cap_feed_carrier", width="$img_width", height="$img_height",rgb=True,
                                     should_wait="$should_wait")
    def acquire_image(self, cap_feed_port="/video_reader/video_feed", cap_feed_carrier="",
                      img_width=CAP_PROP_FRAME_WIDTH, img_height=CAP_PROP_FRAME_HEIGHT, should_wait=SHOULD_WAIT, **kwargs):
        if self.isOpened():
            if kwargs.get("_internal_call", False):
                grabbed = kwargs.get("_grabbed", None)
                img = kwargs.get("_img", None)
            else:
                # capture the video stream from the camera/video
                grabbed, img = self.read(_internal_call=True)

            if not grabbed:
                logging.warning("video not grabbed")
                img = np.zeros((img_height, img_width, 3)) * 255 if self.last_img is None \
                    else self.last_img
            else:
                if img is not None:
                    if self.force_resize:
                        img = cv2.resize(img, (img_width, img_height), interpolation=cv2.INTER_AREA)
                    self.last_img = img
                else:
                    img = np.zeros((img_height, img_width, 3)) * 255
        else:
            logging.error("video capturer not opened")
            img = np.zeros((img_width, img_height, 3)) * 255
        return img,

    def read(self, **kwargs):
        if kwargs.get("_internal_call", False):
            del kwargs["_internal_call"]
            if self.multithreading:
                grabbed, img = True, self.queue.get()
            else:
                grabbed, img = super().read(**kwargs)
            return grabbed, img
        else:
            if self.multithreading:
                grabbed, img = True, self.queue.get()
            else:
                grabbed, img = super().read(**kwargs)
            if grabbed:
                img, = self.acquire_image(cap_feed_port=self.cap_feed_port, cap_feed_carrier=self.cap_feed_carrier,
                                   img_width=self.img_width, img_height=self.img_height,
                                   _internal_call=True, _grabbed=grabbed, _img=img)
            return grabbed, img

    def retrieve(self, **kwargs):
        if kwargs.get("_internal_call", False):
            grabbed, img = super().retrieve(**kwargs)
            return grabbed, img
        else:
            grabbed, img = super().retrieve(**kwargs)
            img, = self.acquire_image(cap_feed_port=self.cap_feed_port, cap_feed_carrier=self.cap_feed_carrier,
                                      img_width=self.img_width, img_height=self.img_height,
                                      _internal_call=True, _grabbed=grabbed, _img=img)
            return grabbed, img

    def getPeriod(self):
        return 1.0 / self.fps

    def updateModule(self):
        _, img = self.read()
        if not self.headless:
            if img is not None:
                cv2.imshow("VideoCapture", img)
                k = cv2.waitKey(int(self.getPeriod()*1000))
                if k == 27:  # Esc key to exit
                    exit(0)
                elif k == -1:  # normally -1 returned,so don"t print it
                    pass

        return True

    def runModule(self):
        while True:
            self.updateModule()
            # time.sleep(self.getPeriod())

    def has_next(self, max_tries=10):
        tries = 0
        while self.queue.qsize() == 0 and tries < max_tries and self.isOpened():
            time.sleep(0.05)
            tries += 1
        return self.queue.qsize() > 0

    def __del__(self):
        self.release()

    def release(self, force=True):
        if self.multithreading:
            if force:
                self.thread.join()
                super().release()
            else:
                if self.has_next():
                    return False
                else:
                    super().release()
                    self.thread.join()
        else:
            super().release()


class VideoCaptureReceiver(VideoCapture):
    CAP_PROP_FRAME_WIDTH = 320
    CAP_PROP_FRAME_HEIGHT = 240

    def __init__(self, cap_feed_port="/video_reader/video_feed", cap_feed_carrier="",
                 headless=False, should_wait=False, multithreading=False,
                 img_width=CAP_PROP_FRAME_WIDTH, img_height=CAP_PROP_FRAME_HEIGHT, fps=30, **kwargs):
        VideoCapture.__init__(self, cap_feed_port="", cap_feed_carrier=cap_feed_carrier,
                              headless=headless, should_wait=should_wait, img_width=False, img_height=False,
                              fps=False, multithreading=False, **kwargs)

        self.cap_feed_port = cap_feed_port

        if img_width:
            self.img_width = img_width
            VideoCaptureReceiver.CAP_PROP_FRAME_WIDTH = img_width
        if img_height:
            self.img_height = img_height
            VideoCaptureReceiver.CAP_PROP_FRAME_HEIGHT = img_height

        self.fps = fps

        self.properties = {
            cv2.CAP_PROP_POS_FRAMES: "fpos",
            cv2.CAP_PROP_POS_MSEC: "fpos_msec",
            cv2.CAP_PROP_FPS: "fps",
            cv2.CAP_PROP_FRAME_COUNT: "fcount",
            cv2.CAP_PROP_FRAME_WIDTH: "img_width",
            cv2.CAP_PROP_FRAME_HEIGHT: "img_height"
        }

        self.cap_props = {"cap_feed_port": cap_feed_port,
                          "cap_feed_carrier": cap_feed_carrier,
                          "fpos": 0,
                          "fps": fps,
                          "msec": 1 / fps,
                          "fpos_msec": 0,
                          "fcount": 0,
                          "img_width": self.CAP_PROP_FRAME_WIDTH,
                          "img_height": self.CAP_PROP_FRAME_HEIGHT}

        # control the listening properties from within the app
        if cap_feed_port:
            self.activate_communication(self.acquire_image, "listen")

        self.opened = True

    def retrieve(self, **kwargs):
        try:
            frame_index = self.cap_props["fpos"]
            im, = self.acquire_image(**self.cap_props)
            self.opened = True
            self.cap_props["fpos"] = frame_index + 1
            self.cap_props["fpos_msec"] = self.cap_props["fpos_msec"] + (frame_index + 1) * self.cap_props["msec"]
            return True, im
        except:
            self.opened = False
            return False, None

    def grab(self, **kwargs):
        return self.retrieve()[0]

    def read(self, **kwargs):
        return self.retrieve()

    def isOpened(self):
        return self.opened

    def release(self, **kwargs):
        pass

    def set(self, propId, value):
        self.cap_props[self.properties[propId]] = value

    def get(self, propId):
        return self.cap_props[self.properties[propId]]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true", help="Disable CV2 GUI")
    parser.add_argument("--should_wait", action="store_true", help="Wait for at least one listener before publishing")
    parser.add_argument("--multithreading", action="store_true", help="Enable multithreading for publishing capturer")
    parser.add_argument("--queue_size", type=int, default=10, help="Queue size for multithreading")
    parser.add_argument("--force_resize", action="store_true", help="Force resizing video width and height on publishing")
    parser.add_argument("--cap_feed_port", type=str, default="/video_reader/video_feed",
                        help="The middleware port for publishing/receiving the image")
    parser.add_argument("--cap_feed_carrier", type=str, default="",
                        help="The carrier e.g., TCP or UDP for transmitting images. This is middleware dependent:"
                             "yarp - udp, tcp, mcast; ros - udp, tcp; zeromq - tcp")
    parser.add_argument("--cap_source", type=str, default="",
                        help="The video capture source id (int camera id | str video path | str image path)")
    parser.add_argument("--img_width", type=int, default=1280, help="The image width")
    parser.add_argument("--img_height", type=int, default=720, help="The image height")
    parser.add_argument("--fps", type=int, default=30, help="The video frames per second")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.cap_source:
        vid_cap = VideoCapture(**vars(args))
    else:
        vid_cap = VideoCaptureReceiver(**vars(args))
    vid_cap.runModule()
