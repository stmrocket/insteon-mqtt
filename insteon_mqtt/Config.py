#===========================================================================
#
# Configuration file utiltiies.
#
#===========================================================================

__doc__ = """Configuration file utilties
"""

#===========================================================================
import time
import difflib
import os
from datetime import datetime
from shutil import copy
from ruamel.yaml import YAML
from ruamel.yaml.nodes import ScalarNode, SequenceNode
from . import device


class Config:
    """Config file class

    This class handles the loading, parsing, and saving of the configuration
    file.
    """
    def __init__(self, path):
        self.path = path
        # Configuration file input description to class map.
        self.devices = {
            # Key is config file input.  Value is tuple of (class, **kwargs)
            # of the class to use and any extra keyword args to pass to the
            # constructor.
            'dimmer' : (device.Dimmer, {}),
            'battery_sensor' : (device.BatterySensor, {}),
            'fan_linc' : (device.FanLinc, {}),
            'io_linc' : (device.IOLinc, {}),
            'keypad_linc' : (device.KeypadLinc, {'dimmer' : True}),
            'keypad_linc_sw' : (device.KeypadLinc, {'dimmer' : False}),
            'leak' : (device.Leak, {}),
            'mini_remote4' : (device.Remote, {'num_button' : 4}),
            'mini_remote8' : (device.Remote, {'num_button' : 8}),
            'motion' : (device.Motion, {}),
            'outlet' : (device.Outlet, {}),
            'smoke_bridge' : (device.SmokeBridge, {}),
            'switch' : (device.Switch, {}),
            'thermostat' : (device.Thermostat, {}),
            }
        self.data = []
        self.backup = ''  # Contains the most recent backup file name

        # Initialize the config data
        self.load()

#===========================================================================
    def load(self):
        """Load or reloads the configuration file.  Called on object init
        """
        with open(self.path, "r") as f:
            yaml = YAML()
            yaml.Constructor.add_constructor("!include", self._include)
            yaml.preserve_quotes = True
            self.data = yaml.load(f)

#===========================================================================
    def save(self):
        """Saves the configuration data to file.  Creates and keeps a backup
        file if diff produced is significant in size compared to original
        file size.  The diff process is a little intensive.  We could
        consider making this a user configurable option, but it seems prudent
        to have this given the amount of work a user may put into creating
        a config file.
        """
        # Create a backup file first`
        ts = time.time()
        timestamp = datetime.fromtimestamp(ts).strftime('%Y-%m-%d_%H-%M-%S')
        self.backup = self.path + "." + timestamp
        copy(self.path, self.backup)

        # Save the config file
        with open(self.path, "w") as f:
            yaml = YAML()
            yaml.preserve_quotes = True
            yaml.indent(mapping=2, sequence=4, offset=2)
            yaml.dump(self.data, f)

        # Check for diff
        orgCount = 0
        with open(self.backup, 'r') as old:
            for line in old:  # pylint: disable=W0612
                orgCount += 1
        with open(self.path, 'r') as new:
            with open(self.backup, 'r') as old:
                diff = difflib.unified_diff(
                    old.readlines(),
                    new.readlines(),
                    fromfile='old',
                    tofile='new',
                )
        # Count the number of deleted lines
        diffCount = len([l for l in diff if l.startswith('- ')])
        # Delete backup if # of lines deleted or altered from original file
        # is less than 5% of original file
        if diffCount / orgCount <= 0.05:
            os.remove(self.backup)
            self.backup = ''

#===========================================================================
    def apply(self, mqtt, modem):
        """Apply the configuration to the main MQTT and modem objects.

        Args:
          mqtt (mqtt.Mqtt):  The main MQTT handler.
          modem (Modem):  The PLM modem object.
        """
        # We must load the MQTT config first - loading the insteon config
        # triggers device creation and we need the various MQTT config's set
        # before that.
        mqtt.load_config(self)
        modem.load_config(self)

#===========================================================================
    def find(self, name):
        """Find a device class from a description.

        Valid inputs are defined in the self.devices dictionary.

        Raises:
          Exception if the input device is unknown.

        Args:
          name (str):  The device type name.

        Returns:
          Returns a tuple of the device class to use for the input and
          any extra keyword args to pass to the device class constructor.
        """
        dev = self.devices.get(name.lower(), None)
        if not dev:
            raise Exception("Unknown device name '%s'.  Valid names are "
                            "%s." % (name, self.devices.keys()))

        return dev

#===========================================================================
    def _include(self, loader, node):
        """Used as a function in the construtor that is called whenever an
        include tag is found.  Since we do not have an include representer
        this will collapse the include tree into a single config file on
        save
        Args:
          loader:  The yaml loader
          node:  The include node
        Returns:
          The loaded and parsed data from the include file
        """
        y = loader.loader
        yaml = YAML(typ=y.typ, pure=y.pure)
        yaml.composer.anchors = loader.composer.anchors
        baseDir = os.path.dirname(self.path)

        # input is a single file to load.
        if isinstance(node, ScalarNode):
            with open(os.path.join(baseDir, node.value), "r") as f:
                result = yaml.load(f)

        # input is a list of files to load.
        elif isinstance(node, SequenceNode):
            result = []
            for include_file in node.value:
                with open(os.path.join(baseDir, include_file.value), "r") as f:
                    singleFile = yaml.load(f)
                    result += singleFile

        else:
            msg = ("Error: unrecognized node type in !include statement: %s"
                   % str(node))
            raise yaml.constructor.ConstructorError(msg)
        return result
