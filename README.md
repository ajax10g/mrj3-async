MRJ3-Async
========

A generic library to easily send serial commands to the Mitsubishi Servo Amplifier MR-J3
Install via pip: `pip install mrj3`.

Not sure how to use this library?  Check [this blog post](http://blog.brodie.me/2013/08/control-your-projector-from-your.html) for a more in-depth tutorial on how to set everything up.


Usage
=====

```Python
from mrj3 import Mrj3

# Look up what port your projector is connected to, using something
# like `dmesg` if you're on linux.
port = '/dev/ttyUSB0'

# The only valid device id at the moment is `mrj3`. This is used
# to figure out what commands are supported, and the format needed.
device_id = 'mrj3'

mrj3 = Mrj3.Mrj3(port=port, device_id=device_id)

# Let's check what commands claim to be supported by our device.
print(mrj3.command_list)

# Let's check the actions associated with each command
print(mrj3.command_spec)

# Turn the projector on
mrj3.power('on')
# We need to change the source, which are supported?
print(mrj3.get_actions_for_command('source'))
# Change the source to hdmi-2
mrj3.source('hdmi_2')
# It's too loud!
mrj3.volume('down')
# We're done here
mrj3.power('off')

# We can also interact directly with the underlying `PySerial` instance
mrj3.serial.write('some other command here')
```

From the command line
=====================

Want to control your projector from the command line?  Use the `mrj3_controller`
script included.

```
Usage: mrj3_controller [-h] [-s SERIAL] {mrj3} port station command action [data]

positional arguments:
  {mrj3}                The device you wish to control
  port                  The serial port your device is connected to
  station               The station number to send to the device. ex: 0,1,2,...,9,A,B,...V
  command               The command to send to the device. ex: 02
  action                The action to send to the device. ex: 70

optional arguments:
  -h, --help            show this help message and exit
  -s SERIAL, --serial SERIAL
                        Extra PySerial config values
```


Example: `./mrj3_controller mrj3 "/dev/ttyUSB0" power on` to turn the projector on.

Your device isn't supported?
============================

You should be able to easily add support for other devices using a
simple json file. Check the files in `mrj3/projector_configs` for examples.

It should follow the template below...

```JSON
{
    "left_surround": "\r\n*",
    "right_surround": "#\r\n",
    "seperator": "=",
    "wait_time": 1,
    "command_failed_message": "*Block item#",
    "exception_message": "*Illegal format#",
    "serial": {
        "baudrate": 57600,
        "parity": "none",
        "stopbits": 1,
        "bytesize": 8
    },
    "command_list": {
        "power": {
            "command": "pow",
            "actions": {
                "on": "on",
                "off": "off",
                "status": "?"
            }
        },
        ...
        ...
    }
}
```
Please do make pull requests for any other devices.  If code changes need made
in order for your device to work, open an issue and I'll work to resolve it.
