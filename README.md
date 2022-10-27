# wrapyfi-interfaces

We provide a collection of simple robot and device interfaces for actuation and sensing in a 
[Wrapyfi](https://github.com/modular-ml/wrapyfi) compatible format. For installing device 
drivers and libraries, refer to the README document provided in each interface package 
e.g., [/wrapyfi_interfaces/robots/icub_head/](/wrapyfi_interfaces/robots/icub_head/)

For each interface, run the standalone `interface.py` with the necessary arguments. 
The interface runs in the background acting as a broker for bridging Wrapyfi decorated 
function calls with the devices available. 

We demonstrate the communication with multiple devices including robots such as the iCub head, 
and microcontrollers (e.g., arduino or raspberry pi pico) with sensors attached to them.

## Installation

To install Wrapyfi-interfaces:

```
python3 setup.py install
```

which automatically installs the available interfaces assuming Wrapyfi is already installed.

The interface can be imported directly e.g.:

```
import wrapyfi_interfaces.robots.icub_head.interface as icub_head_interface
```

Or as a broker e.g.:

```
python3 wrapyfi_interfaces/robots/icub_head/interface.py --get_cam_feed --control_head --control_expressions
```

## Naming Conventions

To unify interfaces, we follow the naming conventions specified for getters:

* **acquire_** method prefix: method receiving data over middleware. These include methods which receive values over middleware or execute actions based on peripheral device controls 
(e.g., keyboard capture) to issue an action. Switching between device reading or middleware reading is triggered by switching activation from "publish" to "listen"
* **read_** method prefix: instantaneous reading from sensor devices. Similar to **acquire_** methods but readings do not persist for iterations to follow
* **receive_** method prefix: exclusive reading from middleware. Similar to **acquire_** methods but do not accept changes triggered by sensors or peripheral devices

order of last-mention takes precedence, e.g., a method which exclusively receives data from middleware over Wrapyfi, but also changes instantaneously (**read_**) would have a prefix of **receive_**

We follow the naming convention specified for setters:

* **update_** or **control_** method prefix: methods directly modifying properties (update) and actuate devices (control) and should not be activated in "listen" mode. If such devices must be controlled over middleware, 
a corresponding **acquire_**, **read_**, or **receive_** method should be created and set to "listen" mode. It is not recommended to call **update_** or **control_** methods from within **acquire_**, **read_**, or **receive_** methods and vice-versa
* **write_** method prefix: instantaneous changes written to devices. Similar to **update_** or **control_** but changes do not persist on the device for iterations to follow
* **transmit_** method prefix: exclusive writing to middleware. Similar to **update_** or **control_** but do not communicate with devices through other interfaces or packages. 

order of last-mention takes precedence, e.g., a method which exclusively transmits data to middleware over Wrapyfi, but also changes instantaneously (**write_**) would have a prefix of **transmit_**

Following the `yarp.RFModule` convention, we name methods accordingly:

* **getPeriod()** method name: returns a float specifying the interval between polling iterations (in milliseconds)
* **runModule()** method name: calls **updateModule()** in a loop with an interval 
* **updateModule()** method name: triggers **acquire_**, **receive_**, **read_**, **update_**, **control_**, or **write_** methods along with other methods to scan or control all devices per timestep
