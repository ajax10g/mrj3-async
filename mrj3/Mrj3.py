"""Control your mrj3 via serial port.

.. moduleauthor:: John Brodie <john@brodie.me>

"""
from time import sleep
import json
import os
import logging

import serial

import array
import re
import shlex

PATH = os.path.abspath(os.path.dirname(__file__)) + '/mrj3_configs/'


BLU = '\u001b[44;1m'
CYN = '\u001b[46;1m'
GRN = '\u001b[42;1m'
MGT = '\u001b[45;1m'
RED = '\u001b[41;1m'
YEL = '\u001b[43;1m'
REVERSE = '\u001b[7m'
NORM = '\u001b[0m'

sSOH = '\\x01'
sSTX = '\\x02'
sETX = '\\x03'
sEOT = '\\x04'
uSOH = BLU + "\u210f" + NORM   # h-bar character w/ red background
uSTX = BLU +  "\u03b1" + NORM  # Greek alpha character w/ red background
uETX = BLU + '\u03c9' + NORM;
rePatternSoh = sSOH + '(\\w)' + '([\\w ]+)' + sSTX + '(\\w.)' + '([\\w ]*)' + sETX + '([\\w ]+)'
reSubStrSoh =\
    uSOH + REVERSE + "\\1" + NORM + GRN + "\\2" + NORM + uSTX + GRN + '\\3' + NORM + "\\4" + uETX + YEL + "\\5" + NORM
"""STX+Sta+Err+[Data]+ETX+Chk""" """Data field is optional"""
rePatternStx = sSTX + '(\\w)' + '(\\w)' + '(.*)' + sETX + '(\\w+)'
reSubStrStx = uSTX + REVERSE + "\\1" + NORM + YEL + "\\2" + NORM + "\\3" + uETX + YEL + "\\4" + NORM

class CommandFailedError(Exception):
    """A command failed, usually due to an invalid state change."""


class CommandExceptionError(Exception):
    """An executed command caused the device to return an error."""


class InvalidConfigError(Exception):
    """Loading the configuration failed as it is invalid."""


class DeviceConfigMissingError(Exception):
    """The specified device has no associated config file."""


class InvalidCommandError(Exception):
    """The given command or action is invalid for the specified device."""


class Mrj3(object):

    possible_pyserial_settings = [
        'port', 'baudrate', 'bytesize', 'parity', 'stopbits', 'timeout',
        'xonxoff', 'rtscts', 'dsrdtr', 'writeTimeout', 'InterCharTimeout',
    ]
    pyserial_config_converter = {
        'bytesize': {
            5: serial.FIVEBITS,
            6: serial.SIXBITS,
            7: serial.SEVENBITS,
            8: serial.EIGHTBITS,
        },
        'parity': {
            'none': serial.PARITY_NONE,
            'even': serial.PARITY_EVEN,
            'odd': serial.PARITY_ODD,
            'mark': serial.PARITY_MARK,
            'space': serial.PARITY_SPACE,
        },
        'stopbits': {
            1: serial.STOPBITS_ONE,
            1.5: serial.STOPBITS_ONE_POINT_FIVE,
            2: serial.STOPBITS_TWO,
        },

    }

    def __init__(
            self,
            port=None,
            device_id='benq',
            **kwargs
    ):
        """Initialize a new Mrj3 object.

        :param port: The device name or port number your device is connected
            to. If left as ``None``, you must call :func:`open` with the port
            before issuing commands.

        :param device_id: The string which identifies the command set to use
            with your device.

            .. note::

                Currently, only the default value, 'benq', is supported. Please
                fill in a config file for your mrj3 and make a pull
                request!

        :param **kwargs: Any extra keyword args will be passed to the internal
            :mod:`pyserial` :class:`serial.Serial` object, and will override
            any device settings specified in the command set.

        """
        self.port = port
        self.device_id = device_id
        self.get_config(device_id, kwargs)
        self.serial = self._initialize_pyserial(port)
        self._create_commands()

    def get_config(self, device_id, overrides):
        """Get configuration for :mod:`pyserial` and the device.

        Any configuration values for the internal:mod:`pyserial`
        :class:`serial.Serial` specified will override the defaults from
        the device configuration. Any config values not specified will
        be left at the device default.

        :param device_id: The string which identifies the command set to use
            with your device.

        :param overrides: A dict of configuration values.

        """
        self.available_configs = self._populate_configs()
        self.config = self.get_device_config_from_id(device_id)
        self._apply_overrides(overrides)
        self._validate_config()
        self.pyserial_config = self.get_pyserial_config()

    def _validate_config(self):
        """Do basic sanity-checking on the loaded `config`."""
        if 'serial' not in self.config:
            raise InvalidConfigError(
                'Configuration file for {0} does not contain needed serial'
                'config values. Add a `serial` section to the config.'.format(
                    self.device_id)
            )
        if ('command_list' not in self.config or
                len(self.config['command_list']) == 0):
            raise InvalidConfigError(
                'Configuration file for {0} does not define any commands. '
                'Add a `serial` section to the config.'.format(
                    self.device_id)
            )

    def _populate_configs(self):
        """Load all json config files for devices.

        :returns: dict -- All available configs.

        """
        configs = {}
        for f in os.listdir(PATH):
            if f.endswith('.json'):
                data = open(PATH + f)
                json_data = json.loads(data.read())
                name = os.path.splitext(f)[0]
                configs[name] = json_data
        return configs

    def _apply_overrides(self, overrides):
        """Override specified values of the default configuration."""
        self.config.update(overrides)

    def get_device_config_from_id(self, device_id):
        """Get device configuration.

        :param device_id: The string which identifies the command set to use.

        :returns: dict -- The device configuration, including default
        :mod:`pyserial` settings, as well as the command set.

        :raises: DeviceConfigMissingError

        """
        try:
            config = self.available_configs[device_id]
        except KeyError:
            raise DeviceConfigMissingError(
                'Could not find device config with name {0}. '
                'Check that the file exists in '
                ' `mrj3/mrj3_configs/`'.format(device_id)
            )
        return config

    def get_pyserial_config(self):
        """Get the :mod:`pyserial` config values from the device config.

        This also checks that config values are sane, and casts them to
        the appropriate type, as needed.

        :func:`get_device_config_from_id` must be called before this method.

        :returns: dict -- The config values for :class:`serial.Serial`.
        :raises: InvalidConfigError

        """
        serial_config = self.config['serial']
        for key, value in serial_config.items():
            if key not in self.possible_pyserial_settings:
                raise InvalidConfigError(
                    'Configuration file for {0} specifies a serial '
                    'setting "{1}" not recognized by pyserial. Check '
                    'http://pyserial.sourceforge.net/pyserial_api.html'
                    'for valid settings'.format(
                        self.device_id, key)
                )
            if key in self.pyserial_config_converter:
                try:
                    serial_config[key] = (
                        self.pyserial_config_converter[key][value])
                except KeyError:
                    raise InvalidConfigError(
                        'Configuration file for {0} specifies a serial '
                        'setting for "{1}" for key "{2}" not recognized '
                        'by pyserial. Check '
                        'http://pyserial.sourceforge.net/pyserial_api.html'
                        'for valid settings'.format(
                            self.device_id, value, key)
                    )
        return serial_config

    def _initialize_pyserial(self, port):
        """Initialize the internal :class:`serial.Serial` object."""
        return serial.Serial(port=port, **self.pyserial_config)

    def _send(self, data):
        logging.debug("_send: " + repr(data))
        self.serial.write(data.encode())

    def _recv(self, size=1):
        data = self.serial.read(size).decode()
        if data:
            logging.debug("_recv: " + repr(data))
        return data

    def _do_handshake(self):
        h = self.config.get('handshake')
        if h == None:
            return
        self._send(h['send'])
        sleep(h['wait'])
        expected = h['expect']
        resp = self._recv(len(expected))
        if resp != expected:
            logging.error("unexpected response to handshake " + repr(resp))

    # def _command_handler(self, command, action, data):
    def _command_handler(self, station, command, action, data, error, xcommand):
        """Send the `command` and `action` to the device.

        :param command: The command to send, for example, "power".
        :param action: The action to send, for example, "on".

        :returns: str -- The response from the device.

        :raises: InvalidCommandError if `action` is not valid for `command`.

        """
        if command!='x':
            if action not in self.get_actions_for_command(command):
                raise InvalidCommandError(
                    '{0} is not a valid action for comand {1}'.format(
                        action, command)
                )
        command_string = self._create_command_string(station, command, action, data, error, xcommand)
        logging.info("send: " + repr(command_string))
        logging.info("------ " + re.sub(rePatternSoh, reSubStrSoh, command_string))
        self._do_handshake()
        self._send(command_string)
        sleep(self.config.get('wait_time', 1))
        response = self.get_response()
        logging.info("recv: " + repr(response))
        logging.info("------ " + re.sub(rePatternStx, reSubStrStx, response))

        self._check_response(response)
        return response

    def _strip_response(self, response):
        rs = right_surround=self.config.get('right_surround', '')
        ls = left_surround=self.config.get('left_surround', '')
        return response.rstrip(rs).lstrip(ls)

    def _check_response(self, response):
        """Check for errors in the response."""
        if response is None:
            return
        known_responses = self.config.get('known_responses')
        if known_responses:
            response = self._strip_response(response)
            if response in known_responses:
                print (known_responses[response])
                return
            else:
                raise CommandFailedError(
                    'Received an unknown response',
                    response
                )
        failed_message = self.config.get('command_failed_message')
        if failed_message is not None and failed_message in response:
            raise CommandFailedError(
                'Command failed! This is likely due to an invalid state '
                'change.'
            )
        exception_message = self.config.get('exception_message')
        if exception_message is not None and exception_message in response:
            raise CommandExceptionError(
                'Command caused an exception on the device. Your command '
                'is likely invalid, check your json mrj3 config!'
            )

    def _create_commands(self):
        """Add commands to class."""
        # TODO: Clean this up.
        def _create_handler(command):
            def handler(station, action, data, error, xcommand):
                return self._command_handler(station, command, action, data, error, xcommand)
            return handler
        for command in self.command_spec:
            setattr(self, command, _create_handler(command))

    def get_response(self):
        """Get any message waiting in the serial port buffer.

        :returns: str -- Response from the device, empty string if no response.

        """
        response = ''
        # while self.serial.inWaiting() > 0:
        while self.serial.in_waiting > 0:
            response += self._recv(1)
        return response

    def _create_command_string(self, station, command, action, data, error, xcommand):
        """Create a command string ready to send to the device.

        .. note:: The `command` param will be translated from english
        to the proper command for the device.

        """
        try:
            stationValue = int(station.upper(), 10)
            """Keep 0,1,...,8,9 as is"""
            """Convert 10,11,...,30,31 to A,B,...,U,V"""
            if 0 <= stationValue <= 9:
                serial_station = chr(stationValue + (ord('0')-0))
            elif 10 <= stationValue <= 31:
                serial_station = chr(stationValue + (ord('A')-10))
        except:
            """Allow g,h,...,u,v or G,H,...,U,V"""
            serial_station = station.upper()

        if command == 'x':
            serial_command = xcommand
            serial_action  = action
            serial_data = data
        else:
            serial_command = self.command_spec[command]['command']
            serial_action  = self.command_spec[command]['actions'][action]
            if 'data' in self.command_spec[command]:
                try:
                    """data is expected to be a string of hex bytes separated by white-space(s) or comma(s) ex: '0 9 2a f'"""
                    """for literal space character(s), bracket it with quotes ex. ' '"""
                    serial_data = "".join(shlex.split(data))
                except:
                    print("Error:  Missing parameter!")
                    print("\t..." + " " + command + " " + serial_action + " data(as string of hex bytes ex: '0 11 2a')")
                    exit()
            else:
                serial_data = ""

        if 'error' in self.command_spec[command]:
            try:
                """data is expected to be an ascii coded hex byte """
                serial_error = error
            except:
                print("Error:  Missing parameter!")
                print("\t..." + " " + command + " " + serial_action + " error(as string of hex bytes ex: '0 11 2a')")
                exit()
        else:
            serial_error = ""

        if command == "slave":
            command_without_chksum_string = (
                '{sta}{error}'
                '{data}{etx}'.format(
                    sta=serial_station,
                    error=serial_error,
                    data=serial_data,
                    etx=self.config.get('etx', '')
                )
            )
            command_string = (
                '{stx}{chksumed}{chksum}'.format(
                    stx=self.config.get('stx', ''),
                    chksumed = command_without_chksum_string,
                    chksum = self.calc_chksum(command_without_chksum_string)
                )
            )
        elif command == "eot":
            command_string = (
                '{eot}'.format(
                    eot=self.config.get('eot', ''),
                )
            )
        else:
            command_without_chksum_string = (
                '{sta}{command}{stx}'
                '{action}{data}{etx}'.format(
                    sta=serial_station,
                    command=serial_command,
                    stx=self.config.get('stx', ''),
                    action=serial_action,
                    data=serial_data,
                    etx=self.config.get('etx', '')
                )
            )
            command_string = (
                '{soh}{chksumed}{chksum}'.format(
                    soh=self.config.get('soh', ''),
                    chksumed = command_without_chksum_string,
                    chksum = self.calc_chksum(command_without_chksum_string)
                )
            )
        return command_string

    def calc_chksum(self, s):
        """Return the checksum in ascii code of the bytes represented in string s."""
        b = bytearray()
        b.extend(map(ord, s))
        total_chksum = sum(b)
        """The desired chksum value is the last 2-digits in ascii code of the total_chksum"""
        total_chksum_in_ascii = "{0:0{1}x}".format(total_chksum, 2).upper()
        return total_chksum_in_ascii[-2:]

    def get_actions_for_command(self, command):
        """Get a list of all valid actions for a given command."""
        return self.command_spec.get(command, {}).get('actions').keys()

    @property
    def command_list(self):
        """Get a list of all commands.

        :returns: dict -- List of valid commands.

        """
        return self.config['command_list'].keys()

    @property
    def command_spec(self):
        """Return all command specifications.

        :returns: dict -- All command specs, with the pattern:
            "<alias>": {
                "command": "<serial_command>",
                "actions": {
                    "<alias>": "<serial_command>",
                    ...,
                },
            },
            ...
        """
        return self.config['command_list']
