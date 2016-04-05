# About
This repository contains the microcontroller code used to sample the sensors, as well as control the microinjector, as well as a python data acquisition script.

# Dependencies
In order to program the microcontroller, the arduino libraries are needed, and the arduino IDE should be used. 

The python script runs in python3, and also requires the pyserial library.
  Download an install archive from here: https://pypi.python.org/pypi/pyserial
  If you are installing from Linux or a Unix based OS, after extracting the archive run setup.py as:
  $sudo python3 setup.py install
  
# How to use
Begin collecting data using the script data_acquisition.py. The script takes three inputs from the command line:
  - A device location for the serial port that the arduino is connected to
  - A positive integer representing the sampling rate of the accelerometers, in Hz
  - A positive integer representing the sampling rate of the IR sensor, in Hz

The minimum sampling rate for the system is 250Hz and the fastest that should be used is 1KHz. The system may run faster than 1KHz, but the sample time becomes jittery in excess of 15 microseconds. The upper limit of the sampling frequency is not yet known.

Example:
python3 data_acquisition.py /dev/ttyACM0 1000 20
