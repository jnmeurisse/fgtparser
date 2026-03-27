<h1>A FortiGate configuration file parser</h1>

# Description
This package provides a non-validating FortiGate configuration file parser. 

A FortiGate configuration file contains a set of command lines. A command line 
consists of a command word (`set`, `unset` or `config`), usually followed by 
configuration data.  The `set` command is used to configure a parameter, 
the `unset` command is used to reset a parameter to its default value and the
`config` command is used to introduce a configuration object such as in the 
example 1 here after or a configuration table as in the example 2.
#### Example 1 : a config object
    config system global
        set admin-server-cert "my-cert"
        set admintimeout 30
        set alias "FGT60EXX123456"
        set gui-certificates enable
    end
#### Example 2 : a config table
    config system interface
        edit "wan1"
            set vdom "root"
            set ip 182.168.10.1 255.255.255.0
            ...
        next
        edit "wan2"
            ...
        next
    end

# Features
The function `FgtConfigParser.parse_file` parses a FortiGate backup file and returns 
an instance of `FgtConfig` that holds the configuration.  The main 
properties of this object are
- `multi_vdom`: True in multi-VDOM mode.
- `root`: provides an instance of `FgtConfigRoot` that contains all config 
objects or tables under *config global* section in a multiple VDOMs 
(multi_vdom is True) configuration and the whole configuration (all config 
objects/tables) if VDOMs are not configured (multi_vdom is False).
- `vdoms`: provides a dictionary that maps a VDOM name to an instance of 
`FgtConfigRoot`.

After parsing, the firewall configuration is stored in a hierarchy of objects 
derived from `FgtConfigNode` class:
- `FgtConfigSet` class represents a `set` command. 
- `FgtConfigUnset` class represents a `unset` command.
- `FgtConfigObject` class represents a `config` object (see example 1).
- `FgtConfigTable` class represents a `config` table (see example 2).

`FgtConfigObject` and `FgtConfigTable` are dictionaries that allows the 
retrieval of sub configuration nodes.  `FgtConfigRoot` is a derived class of `FgtConfigObject`.


### Class Hierarchy

```text
FgtConfigNode (abstract)
├── FgtConfigSet
├── FgtConfigUnset
└── FgtConfigBody (abstract)
    ├── FgtConfigTable
    └── FgtConfigObject
        └── FgtConfigRoot
```

### Key Classes & methods

- `FgtConfig`: Full configuration representation
  - `multi_vdom` : True in multi-VDOM mode 
  - `root`: global or `config global` section
  - `vdoms`: named virtual domains
  - `comments`: configuration metadata and version information

- `FgtConfigObject`: dictionary of nested nodes (`FgtConfigSet`, `FgtConfigTable`, etc.)
  - `c_object(key)`: Get a config object (→ `FgtConfigObject`)
  - `c_table(key)` : Get a config table (→ `FgtConfigTable`)
  - `c_set(key)` : Get a config set (→ `FgtConfigSet`)  
  - `param(key)`: Get parameter (equivalent to `c_set(key)[0]`)
  - Attribute-style access (`obj.param`)

- `FgtConfigTable`: dictionary of `edit` blocks (each as a `FgtConfigObject`)
  - `c_entry(key)`: Return a config entry by name or index (→ `FgtConfigObject`)

- `FgtConfigSet`: a `set` command
- `FgtConfigUnset`: an `unset` command

---

# ✏️ Examples

- print the admin timeout
  ```
  from fgtparser import load

  config = load("example.conf")
  root = config.root

  global_section = root.c_object('system global')
  print(global_section.attr.admintimeout)
  ```

- remove password from a configuration
  ```
  import sys 
  from fgtparser import load
  from fgtparser import FgtConfigSet
     
  config = load("example.conf")
  for key, value in config.root.walk(''):
    if key.endswith('/password') and isinstance(value, FgtConfigSet) and len(value) == 2 and value[0] == 'ENC':
      # Replace encrypted password
      value[1] = '?'
  config.dump(sys.stdout, True, None, None)
  ```

___
# Installation
Download wheel file from github and install it using pip (note: this package requires Python version >= 3.11) 

```
pip3 install fgtparser-1.2-py3-none-any.whl
```
