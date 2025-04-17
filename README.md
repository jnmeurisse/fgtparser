<h1 align="center">A FortiGate configuration file parser</h1>

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

# 🧩 Features
`FgtConfigParser.parse_file` parses a FortiGate backup file and returns 
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
retrieval of sub configuration nodes.  `FgtConfigSet` and `FgtConfigUnset` are 
the leaf in the object hierarchy.

`FgtConfigRoot` is a derived class of `FgtConfigObject`.


### 🏗 Class Hierarchy

```text
FgtConfigNode (abstract)
├── FgtConfigSet
├── FgtConfigUnset
└── FgtConfigBody (abstract)
    ├── FgtConfigTable
    └── FgtConfigObject
        └── FgtConfigRoot
```

### 🔍 Key Classes

#### `FgtConfig` 
- description : Full configuration representation
- methods:
  - `multi_vdom` : True in multi-VDOM mode 
  - `root`: global or `config global` section
  - `vdoms`: named virtual domains
  - `comments`: config metadata and version info

#### `FgtConfigObject`
- description : Dictionary of nested nodes (`FgtConfigSet`, `FgtConfigTable`, etc.)
- methods
  - `c_object(key)`: Get a config object (→ `FgtConfigObject`)
  - `c_table(key)` : Get a config table (→ `FgtConfigTable`)
  - `c_set(key)` : Get a config set (→ `FgtConfigSet`)  
  - `param(key)`: Get parameter (equivalent to `c_set(key)[0]`)
  - `same(key, value)`: Compare `param` result to the value.
  - Attribute-style access (`obj.param`)

### `FgtConfigTable`
- description: Dictionary of `edit` blocks (each as a `FgtConfigObject`)
- method:
  - `c_entry(key)`: Return a config entry by name or index (→ `FgtConfigObject`)

### `FgtConfigSet`
- description : Simple `set` command
- method
  - List-like access to parameters

---

# ✏️ Examples

- print the admin timeout
  ```
  from fgtparser import parse_file
  
  config = parse_file("example.conf")
  root = config.root
  
  global_section = root.c_object('system global')
  print(global_section.admintimeout)
  ```

- remove password and comments from a configuration
  ```
  import sys
  from typing import Any, cast
  
  from fgtparser import parse_file
  from fgtparser import FgtConfigItem, FgtConfigStack, FgtConfigSet
   
  def hide_password(in_out: bool, item: FgtConfigItem, stack: FgtConfigStack, data: Any) -> None:
      if in_out:
          key = item[0]
          value = item[1]
          if key == 'password' and isinstance(value, FgtConfigSet) and value[0] == 'ENC':
              value[1] = '*'

  def filter_item(item: FgtConfigItem, stack: FgtConfigStack, data: Any) -> bool:
      return item[0] != 'comment'
   
  config = parse_file("example.conf")
  config.root.traverse('', hide_password, FgtConfigStack(), None)
  config.write(sys.stdout, True, filter_item, None)
  ```

___
# Installation
