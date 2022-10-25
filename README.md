# wrapyfi-interfaces

We provide a collection of robot and device interfaces for actuation and sensing in a [Wrapyfi](https://github.com/modular-ml/wrapyfi) compatible format. For installing device drivers and libraries, refer to the README document provided in each interface package e.g., [/wrapyfi_interfaces/robots/icub_head/](/wrapyfi_interfaces/robots/icub_head/)

For each interface, run the standalone `interface.py` with the necessary arguments. The interface runs in the background acting as a broker for bridging Wrapyfi decorated function calls with the devices available. 

## Installation

To install Wrapyfi-interfaces:

```
python3 setup.py install
```

which automatically installs the available interfaces assuming Wrapyfi is already installed.

The interface can by imported directly e.g.:

```
from wrapyfi_interfaces.robots.icub_head.interface import ICub
```

Or as a broker e.g.:

```
python3 wrapyfi_interfaces/robots/icub_head/interface.py --get_cam_feed --control_head --control_expressions
```
