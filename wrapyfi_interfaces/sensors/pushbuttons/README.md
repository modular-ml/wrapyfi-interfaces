# Installing Push Button

The push button interface controls two LED buttons attached to an [Arduino Mega 2560](https://www.arduino.cc/en/hardware), following the schematic shown in [this tutorial](https://create.arduino.cc/projecthub/SBR/working-with-two-leds-and-two-push-buttons-1d4182). 
Note that the arduino sketch in `arduino/button_switch.ino` is compatible with a wider range of arduino series. 

To compile the sketch, replace the pins shown in the schematic:

* attach wire on pin 12 to pin 10
* attach wire on pin 4 to pin 11
* attach wire on pin 8 to pin 9
* attach wire on pin 2 to pin 8

Once a button is pushed, the interface receives a signal indicating the button pushed. The same interface can be used to trigger either button light. 

**note:** make sure to set `sudo chmod 777 /dev/ttyACM0`

# Running the Interface

(TODO)
