from ruamel.yaml import YAML
from ruamel.yaml.nodes import ScalarNode, SequenceNode
import os

"""
This is an example file that was used for testing a method of incorporating
the include tag into the ruamel framework.  

The current state is a working design, but it is not pretty and likely has
side effects and bugs.
"""

def load(path, yaml):
    """Load the configuration file.
    Args:
      path:  The file to load
      yaml:  The ruamel instance
    Returns:
      dict: Returns the configuration dictionary.
    """
    with open(path, "r") as f:
        return yaml.load(f)

def save(path, data, yaml):
    """save the configuration file.
    Args:
      path:  The file to save
      data:  The data to write
      yaml:  The ruamel instance
    Returns:
      None
    """
    data = recurse(path,data,yaml)
    with open(path, "w+") as f:
        yaml.dump(data, f)
        return

def recurse(path, data, yaml):
    """Recursively searches the data structure looking for the flags of 
    an include file.  If any include is found, it is individually saved
    to the proper file and a reference is added to the calling file.
    Args:
      path:  The file to save
      data:  The data to write
      yaml:  The ruamel instance
    Returns:
      None
    """
    if hasattr(data, "!include"):
        includePath = getattr(data, "!include")
        delattr(data, "!include")
        save(includePath, data, yaml)
        data = Include(includePath)
    elif hasattr(data, "!includeSequence"):
        includePath = getattr(data, "!includeSequence")
        delattr(data, "!includeSequence")
        for includeFile in data:
            singleIncludePath = getattr(data, "!include")
            delattr(data, "!include")
            save(singleIncludePath, includeFile, yaml)
        data = Include(includePath)
    elif (isinstance(data,list)):
        for i in range(len(data)):
            data[i] = recurse(path,data[i],yaml)
    elif (isinstance(data,dict)):
        for k in data.keys():
            data[k] = recurse(path,data[k],yaml)
    return data

def include(loader, node):
    """Used as a function in the construtor that is called whenever an
    include tag is found.
    Args:
      loader:  The yaml loader
      node:  The include node
    Returns:
      The loaded and parsed data from the include file
    """
    global base_config_dir
    y = loader.loader
    yaml = YAML(typ=y.typ, pure=y.pure)
    yaml.composer.anchors = loader.composer.anchors
    # input is a single file to load.
    if isinstance(node, ScalarNode):
        with open(os.path.join(base_config_dir, node.value), "r") as f:
            result = yaml.load(f)
            setattr(result, "!include", node.value)
            return result

    # input is a list of files to load.
    elif isinstance(node, SequenceNode):
        result = []
        setattr(result, "!includeSequence", node.value)
        for include_file in node.value:
            with open(os.path.join(base_config_dir, include_file), "r") as f:
                singleFile = yaml.load(f)
                setattr(singleFile, "!include", include_file)
                result += singleFile
        return result

    else:
        msg = ("Error: unrecognized node type in !include statement: %s"
                % str(node))
        raise yaml.constructor.ConstructorError(msg)

def represent(representer, node):
    """Called whenever the representer comes across the Include class.  This
    is used to save the Include tag in the parent file.
    Args:
      representer:  The representer instance
      node:  The Include instance
    Returns:
      A represented scalar to be saved
    """
    return representer.represent_scalar("!include", u'{.path}'.format(node))

class Include:
    """A placeholder class that triggers the writing of the include tag in
    the parent file
    """
    def __init__(self, path):
        self.path = path

## Example Usage
yaml=YAML()
base_config_dir = os.path.dirname('test-config.yaml')
yaml.Constructor.add_constructor("!include", include)
yaml.Representer.add_representer(Include, represent)
yaml.preserve_quotes = True

#Load the base config file
result = load('test-config.yaml', yaml)

# Do something to the data structure

# Save the config to a seperate file so that we can run a diff
save('test-config2.yaml', result, yaml)
