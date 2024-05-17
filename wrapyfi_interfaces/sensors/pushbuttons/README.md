# SMART/RANDOM Push Button

This interface was used in the following paper: 

[The Robot in the Room: Influence of Robot Facial Expressions and Gaze on Human-Human-Robot Collaboration](https://ieeexplore.ieee.org/document/10309334)

# Installing Push Button

The push button interface controls two LED buttons attached to an [Arduino Mega 2560](https://www.arduino.cc/en/hardware), following the schematic shown in [this tutorial](https://projecthub.arduino.cc/SBR/working-with-two-leds-and-two-push-buttons-68eaa9). 
Note that the arduino sketch in `arduino/button_switch.ino` is compatible with a wider range of arduino series. 

To compile the sketch, replace the pins shown in the schematic:

* attach wire on pin 12 to pin 10
* attach wire on pin 4 to pin 11
* attach wire on pin 8 to pin 9
* attach wire on pin 2 to pin 8

Once a button is pushed, the interface receives a signal indicating the button pushed. The same interface can be used to trigger either button light. 

**note:** make sure to set `sudo chmod 777 /dev/ttyACM0`

# Running the Interface

1. After copying the script to the Arduino Mega, Disconnect it and connect it once more
2. Make sure the TTY device to have all privileges enabled for all users e.g., if `ttyACM0` is the Arduino Mega's device ID, then:

  ```
   sudo chmod 777 /dev/ttyACM0
  ```

3. The interface is a hardcoded coded example to demonstrate the controlling an Arduino with Wrapyfi. It is not meant to be used as an interface, and therefore, no arguments can be passed to the script. Modify `interface.py` or add your preferred arguments to customize the interface.

  ```
  python3 wrapyfi_interfaces/sensors/pushbuttons/interface.py
  ```
