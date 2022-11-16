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

        self.build()

    def build(self):
        """
        Updates the default method arguments according to constructor arguments. This method is called by the module constructor.
        It is not necessary to call it manually.
        """
        FacialExpressionsInterface.transmit_emotion.__defaults__ = (None, None, None, self.PORT_OUT, self.SHOULD_WAIT, self.MWARE_OUT)
        FacialExpressionsInterface.receive_emotion.__defaults__ = (self.PORT_IN, self.SHOULD_WAIT, self.MWARE_IN)

    @MiddlewareCommunicator.register("NativeObject", "$_mware",  "FacialExpressionsInterface",
                                     "$_facial_expressions_port", should_wait="$_should_wait")
    def transmit_emotion(self, emotion_category=None, emotion_continuous=None, emotion_index=None,
                         facial_expressions_port=PORT_OUT, _should_wait=SHOULD_WAIT, _mware=MWARE_OUT, **kwargs):
        """
        Send emotion data to middleware of choice.
        :param emotion_category: list[str] or str: Emotion category (e.g. Happy, Sad, Angry, ...). Final/winning emotion is the last element when a list is provided.
        :param emotion_continuous: list[tuple(str->valence, str->arousal)] or tuple(str->valence, str->arousal): Continuous emotion in the range [0, 1] representing valence and arousal
        :param emotion_index: list[int] or int: Emotion index indicating category (e.g. 0 for Happy, 1 for Sad, 2 for Angry, ...). Final/winning emotion is the last element when a list is provided.
        :param facial_expressions_port: str:  Port to send emotion data to
        :param _should_wait: bool: Whether to wait for a response
        :param _mware: str: Middleware to use
        :kwargs: dict: Additional parameters specific to an application e.g. int->participant_index
        :return: dict: Emotion data for a given time step
        """
        returns = kwargs
        if emotion_category is not None:
            returns["emotion_category"] = emotion_category
        if emotion_continuous is not None:
            returns["emotion_continuous"] = emotion_continuous
        if emotion_index is not None:
            returns["emotion_index"] = emotion_index

        return {"topic": facial_expressions_port.split("/")[-1],
                **returns,
                "timestamp": kwargs.get("timestamp", time.time())},

    @MiddlewareCommunicator.register("NativeObject", "$_mware",  "FacialExpressionsInterface",
                                        "$facial_expressions_port", should_wait="$_should_wait")
    def receive_emotion(self, facial_expressions_port=PORT_IN, _should_wait=SHOULD_WAIT, _mware=MWARE_IN, **kwargs):
        """
        Receive emotion data from middleware of choice.
        :param facial_expressions_port: str: Port to receive emotion data from
        :param _should_wait: bool: Whether to wait for a response
        :param _mware: str: Middleware to use
        :return: dict: Emotion data for a given time step
        """
        return None,

    def getPeriod(self):
        """
        Get the period of the module.
        :return: float: Period of the module
        """
        return 0.01

    def updateModule(self):
        emotion_in, = self.receive_emotion(facial_expressions_port=self.PORT_IN,
                                           _should_wait=self.SHOULD_WAIT,
                                           _mware=self.MWARE_IN)
        if emotion_in is not None:
            print(f"Received emotion: {emotion_in}")
            time.sleep(self.getPeriod())
            emotion_out = self.transmit_emotion(**emotion_in,
                                                facial_expressions_port=self.PORT_OUT,
                                                _should_wait=self.SHOULD_WAIT,
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
