import time
import argparse
import logging

from wrapyfi.connect.wrapper import MiddlewareCommunicator, DEFAULT_COMMUNICATOR


class BoundingBoxInterface(MiddlewareCommunicator):
    """
    Broadcast and receive bounding box coordinates using middleware of choice.
    This template acts as a bridge between different middleware and/or ports (topics).
    """

    PORT_OUT = "/control_interface/bounding_box_out"
    MWARE_OUT = DEFAULT_COMMUNICATOR
    PORT_IN = "/control_interface/bounding_box_in"
    MWARE_IN = DEFAULT_COMMUNICATOR
    SHOULD_WAIT = False

    def __init__(self,
                 bounding_box_port_out=PORT_OUT,
                 mware_out=MWARE_OUT,
                 bounding_box_port_in=PORT_IN,
                 mware_in=MWARE_IN, should_wait=SHOULD_WAIT):
        super(BoundingBoxInterface, self).__init__()

        self.SHOULD_WAIT = should_wait
        if bounding_box_port_out and mware_out:
            self.PORT_OUT = bounding_box_port_out
            self.MWARE_OUT = mware_out
            self.activate_communication("transmit_bounding_box", "publish")

        if bounding_box_port_in and mware_in:
            self.PORT_IN = bounding_box_port_in
            self.MWARE_IN = mware_in
            self.activate_communication("receive_bounding_box", "listen")
        self.build()

    def build(self):
        """
        Updates the default method arguments according to constructor arguments. This method is called by the module constructor.
        It is not necessary to call it manually.
        """
        BoundingBoxInterface.transmit_bounding_box.__defaults__ = (None, None, None, None, None, None, self.PORT_OUT, self.SHOULD_WAIT, self.MWARE_OUT)
        BoundingBoxInterface.receive_bounding_box.__defaults__ = (self.PORT_IN, self.SHOULD_WAIT, self.MWARE_IN)

    @MiddlewareCommunicator.register("NativeObject", "$_mware",  "BoundingBoxInterface",
                                     "$bounding_box_port", should_wait="$_should_wait")
    def transmit_bounding_box(self, x_min=None, y_min=None, x_max=None, y_max=None, width=None, height=None,
                             bounding_box_port=PORT_OUT, _should_wait=SHOULD_WAIT, _mware=MWARE_OUT, **kwargs):
        """
        Publishes the bounding box coordinates to the middleware.
        :param x_min: int->x[pixels]: Leftmost pixel of the bounding box
        :param y_min: int->y[pixels]: Topmost pixel of the bounding box
        :param x_max: int->x[pixels]: Rightmost pixel of the bounding box
        :param y_max: int->y[pixels]: Bottommost pixel of the bounding box
        :param width: float->x[pixels]: Width of the bounding box (defaults x_max - x_min but could use other units)
        :param height: float->y[pixels]: Height of the bounding box (defaults y_max - y_min but could use other units)
        :bounding_box_port: str: Port to publish the bounding box coordinates to
        :param _should_wait: bool: Whether to wait for a response
        :param _mware: str: Middleware to use
        :kwargs: dict: Additional parameters specific to an application
                        e.g., float->score[0,1], or float->reference_scale[-inf,inf]
        :return: dict: Bounding box coordinates for a given time step
        """
        returns = kwargs
        if x_min is not None:
            returns["x_min"] = x_min
        if y_min is not None:
            returns["y_min"] = y_min
        if x_max is not None:
            returns["x_max"] = x_max
        if y_max is not None:
            returns["y_max"] = y_max

        if width is not None:
            returns["width"] = width
        elif x_min is not None and x_max is not None:
            returns["width"] = x_max - x_min

        if height is not None:
            returns["height"] = height
        elif y_min is not None and y_max is not None:
            returns["height"] = y_max - y_min

        return {"topic": bounding_box_port.split("/")[-1],
                **returns,
                "timestamp": kwargs.get("timestamp", time.time())},

    @MiddlewareCommunicator.register("NativeObject", "$_mware",  "BoundingBoxInterface",
                                        "$bounding_box_port", should_wait="$_should_wait")
    def receive_bounding_box(self, bounding_box_port=PORT_IN, _should_wait=SHOULD_WAIT, _mware=MWARE_IN,
                            **kwargs):
        """
        Receives the bounding box coordinates from the middleware of choice.
        :param bounding_box_port: str: Port to receive the bounding box coordinates from
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
        bounding_box_in, = self.receive_bounding_box(bounding_box_port=self.PORT_IN,
                                               _should_wait=self.SHOULD_WAIT,
                                               _mware=self.MWARE_IN)
        if bounding_box_in is not None:
            logging.info(f"Received bounding box: {bounding_box_in}")
            time.sleep(self.getPeriod())
            bounding_box_out = self.transmit_bounding_box(**bounding_box_in,
                                                        bounding_box_port=self.PORT_OUT,
                                                        _should_wait=self.SHOULD_WAIT,
                                                        _mware=self.MWARE_OUT)
            if bounding_box_out is not None:
                logging.info(f"Sent bounding box: {bounding_box_out}")
                time.sleep(self.getPeriod())

    def runModule(self):
        while True:
            try:
                self.updateModule()
            except:
                break

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bounding_box_port_out", type=str, default="",
                        help="Port (topic) to publish bounding_box coordinates")
    parser.add_argument("--mware_out", type=str, default=DEFAULT_COMMUNICATOR,
                        help="Middleware to publish bounding_box coordinates",
                        choices=MiddlewareCommunicator.get_communicators())
    parser.add_argument("--bounding_box_port_in", type=str, default="",
                        help="Port (topic) to listen to bounding_box coordinates")
    parser.add_argument("--mware_in", type=str, default=DEFAULT_COMMUNICATOR,
                        help="Middleware to listen to bounding_box coordinates",
                        choices=MiddlewareCommunicator.get_communicators())
    parser.add_argument("--should_wait", action="store_true", help="Wait for at least one listener before publishing "
                                                                   "or a publisher before listening")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    fer = BoundingBoxInterface(**vars(args))
    fer.runModule()
