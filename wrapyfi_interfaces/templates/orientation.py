import time
import argparse

from wrapyfi.connect.wrapper import MiddlewareCommunicator, DEFAULT_COMMUNICATOR


class OrientationInterface(MiddlewareCommunicator):
    PORT_OUT = "/control_interface/orientation_out"
    MWARE_OUT = DEFAULT_COMMUNICATOR
    PORT_IN = "/control_interface/orientation_in"
    MWARE_IN = DEFAULT_COMMUNICATOR
    SHOULD_WAIT = False

    """
    Broadcast and receive orientation coordinates using middleware of choice.
    This template acts as a bridge between different middleware and/or ports (topics).
    """
    def __init__(self,
                 orientation_port_out=PORT_OUT,
                 mware_out=MWARE_OUT,
                 orientation_port_in=PORT_IN,
                 mware_in=MWARE_IN, should_wait=SHOULD_WAIT):
        super(OrientationInterface, self).__init__()

        self.SHOULD_WAIT = should_wait
        if orientation_port_out and mware_out:
            self.PORT_OUT = orientation_port_out
            self.MWARE_OUT = mware_out
            self.activate_communication("transmit_orientation", "publish")

        if orientation_port_in and mware_in:
            self.PORT_IN = orientation_port_in
            self.MWARE_IN = mware_in
            self.activate_communication("receive_orientation", "listen")
        self.build()

    def build(self):
        """
        Updates the default method arguments according to constructor arguments. This method is called by the module constructor.
        It is not necessary to call it manually.
        """
        OrientationInterface.transmit_orientation.__defaults__ = (None, None, None, None, self.PORT_OUT, self.SHOULD_WAIT, self.MWARE_OUT)
        OrientationInterface.receive_orientation.__defaults__ = (self.PORT_IN, self.SHOULD_WAIT, self.MWARE_IN)

    @MiddlewareCommunicator.register("NativeObject", "$_mware",  "OrientationInterface",
                                     "$orientation_port", should_wait="$_should_wait")
    def transmit_orientation(self, pitch=None, roll=None, yaw=None, speed=None,
                             orientation_port=PORT_OUT, _should_wait=SHOULD_WAIT, _mware=MWARE_OUT, **kwargs):
        """
        Publishes the orientation coordinates to the middleware.
        :param pitch: float->pitch[deg]: Pitch angle in degrees
        :param roll: float->roll[deg]: Roll angle in degrees
        :param yaw: float->yaw[deg]: Yaw angle in degrees
        :param speed: dict{float->pitch[deg/s], float->roll[deg/s], float->yaw[deg/s], **kwargs}: Speed of trajectory
        :orientation_port: str: Port to publish the orientation coordinates to
        :param _should_wait: bool: Whether to wait for a response
        :param _mware: str: Middleware to use
        :kwargs: dict: Additional parameters specific to an application e.g. vergence[deg].
                        Applies to speed as well e.g. vergence[deg/s]
        :return: dict: Orientation coordinates for a given time step
        """
        returns = kwargs
        if pitch is not None:
            returns["pitch"] = pitch
        if roll is not None:
            returns["roll"] = roll
        if yaw is not None:
            returns["yaw"] = yaw
        if speed is not None:
            returns["speed"] = speed

        return {"topic": orientation_port.split("/")[-1],
                **returns,
                "timestamp": kwargs.get("timestamp", time.time())},

    @MiddlewareCommunicator.register("NativeObject", "$_mware",  "OrientationInterface",
                                        "$orientation_port", should_wait="$_should_wait")
    def receive_orientation(self, orientation_port=PORT_IN, _should_wait=SHOULD_WAIT, _mware=MWARE_IN,
                            **kwargs):
        """
        Receives the orientation coordinates from the middleware of choice.
        :param orientation_port: str: Port to receive the orientation coordinates from
        :param _should_wait: bool: Whether to wait for a response
        :param _mware: str: Middleware to use
        :return: dict: Orientation coordinates for a given time step
        """
        return None,

    def getPeriod(self):
        """
        Get the period of the module.
        :return: float: Period of the module
        """
        return 0.01

    def updateModule(self):
        orientation_in, = self.receive_orientation(orientation_port=self.PORT_IN,
                                                   _should_wait=self.SHOULD_WAIT,
                                                   _mware=self.MWARE_IN)
        if orientation_in is not None:
            print(f"Received emotion: {orientation_in}")
            time.sleep(self.getPeriod())
            orientation_out = self.transmit_orientation(**orientation_in,
                                                        orientation_port=self.PORT_OUT,
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
    parser.add_argument("--orientation_port_out", type=str, default="",
                        help="Port (topic) to publish orientation coordinates")
    parser.add_argument("--mware_out", type=str, default=DEFAULT_COMMUNICATOR,
                        help="Middleware to publish orientation coordinates",
                        choices=MiddlewareCommunicator.get_communicators())
    parser.add_argument("--orientation_port_in", type=str, default="",
                        help="Port (topic) to listen to orientation coordinates")
    parser.add_argument("--mware_in", type=str, default=DEFAULT_COMMUNICATOR,
                        help="Middleware to listen to orientation coordinates",
                        choices=MiddlewareCommunicator.get_communicators())
    parser.add_argument("--should_wait", action="store_true", help="Wait for at least one listener before publishing "
                                                                   "or a publisher before listening")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    fer = OrientationInterface(**vars(args))
    fer.runModule()
