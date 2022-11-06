import os
import time
import argparse

from wrapyfi.connect.wrapper import MiddlewareCommunicator, DEFAULT_COMMUNICATOR


class OrientationInterface(MiddlewareCommunicator):
    PORT_OUT = "/control_interface/head_eyes_orientation_out"
    MWARE_OUT = DEFAULT_COMMUNICATOR
    PORT_IN = "/control_interface/head_eyes_orientation_in"
    MWARE_IN = DEFAULT_COMMUNICATOR
    SHOULD_WAIT = False

    """
    Broadcast and receive orientation coordinates using middleware of choice.
    This template acts as a bridge between different middleware and/or ports (topics).
    """
    def __init__(self,
                 head_eyes_orientation_port_out=PORT_OUT,
                 mware_out=MWARE_OUT,
                 head_eyes_orientation_port_in=PORT_IN,
                 mware_in=MWARE_IN, should_wait=SHOULD_WAIT):
        super(OrientationInterface, self).__init__()

        self.SHOULD_WAIT = should_wait
        if head_eyes_orientation_port_out and mware_out:
            self.PORT_OUT = head_eyes_orientation_port_out
            self.MWARE_OUT = mware_out
            self.activate_communication("transmit_orientation", "publish")

        if head_eyes_orientation_port_in and mware_in:
            self.PORT_IN = head_eyes_orientation_port_in
            self.MWARE_IN = mware_in
            self.activate_communication("receive_orientation", "listen")

    def build(self):
        OrientationInterface.transmit_orientation.__defaults__ = (self.PORT_OUT, self.SHOULD_WAIT, self.MWARE_OUT)
        OrientationInterface.receive_orientation.__defaults__ = (self.PORT_IN, self.SHOULD_WAIT, self.MWARE_IN)

    @MiddlewareCommunicator.register("NativeObject", "$_mware",  "OrientationInterface",
                                     "$head_eyes_orientation_port", should_wait="$_should_wait")
    def transmit_orientation(self, head, eyes, head_speed, eyes_speed, reset_gaze,
                         head_eyes_orientation_port=PORT_OUT, _should_wait=SHOULD_WAIT, _mware=MWARE_OUT):
        return {"topic": head_eyes_orientation_port.split("/")[-1],
                "head": head,
                "eyes": eyes,
                "head_speed": head_speed,
                "eyes_speed": eyes_speed,
                "reset_gaze": reset_gaze,
                "timestamp": time.time()},

    @MiddlewareCommunicator.register("NativeObject", "$_mware",  "OrientationInterface",
                                        "$head_eyes_orientation_port", should_wait="$_should_wait")
    def receive_orientation(self, head_eyes_orientation_port=PORT_IN, _should_wait=SHOULD_WAIT, _mware=MWARE_IN,
                            **kwargs):
        return None,

    def getPeriod(self):
        return 0.01

    def updateModule(self):
        orientation_in, = self.receive_orientation(head_eyes_orientation_port=self.PORT_IN,
                                               _should_wait=self.SHOULD_WAIT,
                                               _mware=self.MWARE_IN)
        if orientation_in is not None:
            print(f"Received emotion: {orientation_in}")
            time.sleep(self.getPeriod())
            orientation_out = self.transmit_orientation(head=orientation_in["head"],
                                                        eyes=orientation_in["eyes"],
                                                        head_speed=orientation_in["head_speed"],
                                                        eyes_speed=orientation_in["eyes_speed"],
                                                        reset_gaze=orientation_in["reset_gaze"],
                                                        head_eyes_orientation_port=self.PORT_OUT,
                                                        _should_wait=self.SHOULD_WAIT,
                                                        _mware=self.MWARE_OUT)
            if orientation_out is not None:
                print(f"Sent emotion: {orientation_out}")
                time.sleep(self.getPeriod())

    def runModule(self):
        while True:
            try:
                self.updateModule()
            except:
                break

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--head_eye_port_out", type=str, default="",
                        help="Port (topic) to publish orientation coordinates")
    parser.add_argument("--mware_out", type=str, default=DEFAULT_COMMUNICATOR,
                        help="Middleware to publish head or eye orientation coordinates",
                        choices=MiddlewareCommunicator.get_communicators())
    parser.add_argument("--head_eye_port_in", type=str, default="",
                        help="Port (topic) to listen to orientation coordinates")
    parser.add_argument("--mware_in", type=str, default=DEFAULT_COMMUNICATOR,
                        help="Middleware to listen to head or eye orientation coordinates",
                        choices=MiddlewareCommunicator.get_communicators())
    parser.add_argument("--should_wait", action="store_true", help="Wait for at least one listener before publishing "
                                                                   "or a publisher before listening")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    fer = OrientationInterface(**vars(args))
    fer.runModule()
