import os
import time
import argparse

from wrapyfi.connect.wrapper import MiddlewareCommunicator, DEFAULT_COMMUNICATOR


class FacialExpressionsInterface(MiddlewareCommunicator):
    PORT_OUT = "/control_interface/facial_expressions_out"
    MWARE_OUT = DEFAULT_COMMUNICATOR
    PORT_IN = "/control_interface/facial_expressions_in"
    MWARE_IN = DEFAULT_COMMUNICATOR
    SHOULD_WAIT = False

    """
    Broadcast and receive emotion data using middleware of choice.
    This template acts as a bridge between different middleware and/or ports (topics).
    """
    def __init__(self,
                 facial_expressions_port_out=PORT_OUT,
                 mware_out=MWARE_OUT,
                 facial_expressions_port_in=PORT_IN,
                 mware_in=MWARE_IN, should_wait=SHOULD_WAIT):
        super(FacialExpressionsInterface, self).__init__()

        self.SHOULD_WAIT = should_wait
        if facial_expressions_port_out and mware_out:
            self.PORT_OUT = facial_expressions_port_out
            self.MWARE_OUT = mware_out
            self.activate_communication("transmit_emotion", "publish")

        if facial_expressions_port_in and mware_in:
            self.PORT_IN = facial_expressions_port_in
            self.MWARE_IN = mware_in
            self.activate_communication("receive_emotion", "listen")

    def build(self):
        FacialExpressionsInterface.transmit_emotion.__defaults__ = (self.PORT_OUT, self.SHOULD_WAIT, self.MWARE_OUT)
        FacialExpressionsInterface.receive_emotion.__defaults__ = (self.PORT_IN, self.SHOULD_WAIT, self.MWARE_IN)

    @MiddlewareCommunicator.register("NativeObject", "$_mware",  "FacialExpressionsInterface",
                                     "$facial_expressions_port", should_wait="$should_wait")
    def transmit_emotion(self, emotion_category, emotion_continuous, emotion_index,
                         facial_expressions_port=PORT_OUT, should_wait=SHOULD_WAIT, _mware=MWARE_OUT):
        return {"topic": facial_expressions_port.split("/")[-1],
                "emotion_category": emotion_category,
                "emotion_continuous": emotion_continuous,
                "emotion_index": emotion_index,
                "timestamp": time.time()},

    @MiddlewareCommunicator.register("NativeObject", "$_mware",  "FacialExpressionsInterface",
                                        "$facial_expressions_port", should_wait="$should_wait")
    def receive_emotion(self, facial_expressions_port=PORT_IN, should_wait=SHOULD_WAIT, _mware=MWARE_IN, **kwargs):
        return None,

    def getPeriod(self):
        return 0.01

    def updateModule(self):
        emotion_in, = self.receive_emotion(facial_expressions_port=self.PORT_IN,
                                           should_wait=self.SHOULD_WAIT,
                                           _mware=self.MWARE_IN)
        if emotion_in is not None:
            print(f"Received emotion: {emotion_in}")
            time.sleep(self.getPeriod())
            emotion_out = self.transmit_emotion(emotion_category=emotion_in["emotion_category"],
                                                emotion_continuous=emotion_in["emotion_continuous"],
                                                emotion_index=emotion_in["emotion_index"],
                                                facial_expressions_port=self.PORT_OUT,
                                                should_wait=self.SHOULD_WAIT,
                                                _mware=self.MWARE_OUT)
            if emotion_out is not None:
                print(f"Sent emotion: {emotion_out}")
                time.sleep(self.getPeriod())

    def runModule(self):
        while True:
            try:
                self.updateModule()
            except:
                break

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--facial_expressions_port_out", type=str, default="",
                        help="Port (topic) to publish facial expressions")
    parser.add_argument("--mware_out", type=str, default=DEFAULT_COMMUNICATOR,
                        help="Middleware to publish facial expressions",
                        choices=MiddlewareCommunicator.get_communicators())
    parser.add_argument("--facial_expressions_port_in", type=str, default="",
                        help="Port (topic) to listen to facial expressions")
    parser.add_argument("--mware_in", type=str, default=DEFAULT_COMMUNICATOR,
                        help="Middleware to listen to facial expressions",
                        choices=MiddlewareCommunicator.get_communicators())
    parser.add_argument("--should_wait", action="store_true", help="Wait for at least one listener before publishing "
                                                                   "or a publisher before listening")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    fer = FacialExpressionsInterface(**vars(args))
    fer.runModule()
