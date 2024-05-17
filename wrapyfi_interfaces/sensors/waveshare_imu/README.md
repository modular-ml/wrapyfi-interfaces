# Installing IMU

This interface is for reading orientation coordinates (3DoF) using the [Waveshare Inertial Measurement Unit (IMU)](https://www.waveshare.com/wiki/Pico-10DOF-IMU) attached to a RaspberryPi pico.

We use a RaspberryPi pico to communicate with the IMU. The code needed to extract the readings can be compiled using the [compiler](https://1drv.ms/u/s!AtsoXIeDdjRojK0MNIdQL-hXWY-Zbw?e=VT9Fg3) and [raspberry-pico script](https://1drv.ms/u/s!AtsoXIeDdjRoioVLDDwbVtk2IYTHZw?e=ZRaIcB), both of which should be copied/downloaded to a directory named `src` in this directory. First create the `src` directory with `mkdir src` from within this directory, and add the 2 compressed files in there. 

## Compile raspberry-pico code

If you'd like to alter the `raspberry-pico` source, modify `pico/c/main.c` and then compile it (from this directory):

```
cd src 
tar -xf gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2
unzip Pico-10dof-imu.zip
cp ../pico/c/main.c pico-10dof-imu/c/main.c
cd pico-10dof-imu/c/build
cmake -DPICO_SDK_FETCH_FROM_GIT:BOOL=ON -DPICO_TOOLCHAIN_PATH:INTERNAL="$(realpath ../../../gcc-arm-none-eabi-10.3-2021.10/bin)" ..
make
```

push the BOOTSEL button on your raspberry-pico and connect it to your USB port (while holding the BOOTSEL/reset button)

**note:** make sure to set `sudo chmod 777 /dev/ttyACM0`

on make success, an `imu.uf2` file should be generated in the `src/pico-10dof-imu/c/build` directory.
Copy the `imu.uf2` file to your `RPI-RP2` drive which should appear if you pushed the BOOTSEL button.
The drive will automatically unmount. Once again (and every other time you disconnect the pico), make sure to set `sudo chmod 777 /dev/ttyACM0`

Now you can start the `sensor_reader.py` script to read out your serial writes from the pico. 

**note:** to run `interface.py` install pySerial `pip3 install pySerial`


# Running the Interface

1. After copying the script to the RaspberryPi pico, Disconnect it and connect it once more
2. Make sure the TTY device to have all privileges enabled for all users e.g., if `ttyACM0` is the RaspberryPi pico's device ID, then:
   
   ```
   sudo chmod 777 /dev/ttyACM0
   ```

3. The interface provides several options for fliping the orientation, adding a shift, or even aligning the orientation to another baseline device publishing its readings to a specific topic. In its most basic form e.g., reading and publishing the readings from `ttyACM0` to a specific topic over ZeroMQ :
   
  ```
  python3 wrapyfi_interfaces/sensors/waveshare_imu/interface.py --mware zeromq --orientation_coordinates_port /control_interface/orientation_waveshareimu --ser_device /dev/ttyACM0
  ```
