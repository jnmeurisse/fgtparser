#
# This file is part of fgtparser -  A parser for FortiGate Configuration Files
#
# Copyright (C) 2025  Jean Noel Meurisse
# SPDX-License-Identifier: GPL-3.0-only
#

"""
    The implementation of a FortiGate configuration is organized as a hierarchy
    of classes. ``FgtConfigNode`` is the root abstract base classes
    which represents a configuration node in the configuration object tree.

    Class hierarchy :
                            FgtConfigNode
                                  |
                                  |
                 -----------------+------------------
                 |                |                 |
            FgtConfigSet    FgtConfigUnset     FgtConfigBody
                                                      |
                                                      |
                                              --------+--------
                                              |               |
                                        FgtConfigTable   FgtConfigObject
"""
import re
from abc import ABC, abstractmethod
from collections import deque
from typing import Any, Optional, Callable, TextIO, Iterator, final, Self, cast, Final

FgtConfigToken = str
""" A token in a config file. A token is a sequence of characters. """

FgtConfigTokens = list[FgtConfigToken]
""" A list of tokens, the list can be empty. """

FgtConfigItem = tuple[str, 'FgtConfigNode']
""" Represents the parameter name and the associated configuration node. """

FgtConfigStack = deque[FgtConfigItem]
""" A stack of configuration items.  
This stack is generated during the traversal of the configuration tree. """

FgtConfigTraverseCallback = Callable[
    [bool, FgtConfigItem, FgtConfigStack, Any], None]
""" Callback function called during the traversal of the configuration tree. 
The function is called with 4 arguments :
    * a flag indicating if we enter or leave a node,
    * the current node,
    * the stack of parent nodes,
    * user data.
"""

FgtConfigFilterCallback = Callable[
    [FgtConfigItem, FgtConfigStack, Any], bool]
""" Callback function called from `FgtConfig.make_config` method.  
This callback offers the caller to filter some config from the configuration
tree. The function is called with 3 arguments :
    * the current node,
    * the stack of parent nodes,
    * user data.
The filter function must return a boolean.
"""


def uqs(arg: str) -> str:
    """
    Unquotes a string by removing surrounding double quotes and unescaping
    escaped quotes and backslashes.
    """
    if len(arg) < 2:
        res = arg
    elif arg[0] != '"' or arg[-1] != '"':
        res = arg
    else:
        res = arg.replace('\\"', '"').replace('\\\\', '\\')[1:-1]

    return res


def qus(arg: str) -> str:
    """
    Quotes a string by wrapping it in double quotes and escaping
    any existing double quotes and backslashes.
    """
    return '"{}"'.format(arg.replace('\\', '\\\\').replace('"', '\\"'))


class FgtConfigNode(ABC):
    """ Represents a configuration node in the configuration object tree.

    A configuration node can be a SET command, an UNSET command or a CONFIG
    command. A derived class exists for each object type.  A ``FgtConfigNode``
    is always accessed through a dictionary.
    """

    @abstractmethod
    def traverse(
            self,
            key: str,
            fn: FgtConfigTraverseCallback,
            parents: FgtConfigStack,
            data: Any
    ) -> None:
        """
        Recursively traverse a configuration object tree and invoke a callback
        on each node.

        This method enables traversal of a configuration object tree generated
        by ``FgtParser.parse``. The provided callback function ``fn`` is called
        both before and after visiting each CONFIG node.

        It is the caller's responsibility to ensure that the ``key`` parameter
        matches the name used to map this object in its containing dictionary.

        :param key: The configuration parameter name of this object in the
            dictionary.
        :param fn: A callback function to invoke on each node.
        :param parents: A stack of parent nodes, where each entry is a tuple of
            (str, FgtConfigNode).
        :param data: Arbitrary user data to pass to the callback.
        :return: None
        """


class FgtConfigDict(dict[str, FgtConfigNode]):
    """ A dictionary of configuration nodes. """

    def skeys(self) -> list[str]:
        """
        :return: A list of all dictionary keys, sorted case-insensitively.
        """
        return sorted(self.keys(), key=lambda s: s.lower())


class FgtConfigBody(FgtConfigNode, FgtConfigDict, ABC):
    """ An abstract base class for a CONFIG table or a CONFIG object. """

    def traverse(
            self,
            key: str,
            fn: FgtConfigTraverseCallback,
            parents: FgtConfigStack,
            data: Any
    ) -> None:
        # … enter the config section
        fn(True, (key, self), parents, data)
        parents.append((key, self))

        # ... traverse all items in this dictionary
        for item_key, item_value in self.items():
            item_value.traverse(item_key, fn, parents, data)

        # … leave the config section
        parents.pop()
        fn(False, (key, self), parents, data)

    def walk(self, key: str, delimiter: str = "/") -> Iterator[FgtConfigItem]:
        """
        Recursively yield all descendant configuration nodes in the tree,
        including this node.

        This method performs a breadth-first search (BFS) traversal starting
        from the current node. It visits each child node, constructs its path by
        joining keys with the specified delimiter, and yields a tuple of the
        path and the node.

        :param key: The configuration parameter name of this object in the
            dictionary.
        :param delimiter: The path delimiter used to concatenate keys.
            Defaults to ``"/"``.
        :yield: A tuple containing the full path and the corresponding config
            node.
        """
        pending: deque[FgtConfigItem] = deque([(key, self)])
        while len(pending) > 0:
            path, node = pending.popleft()
            if isinstance(node, (FgtConfigObject, FgtConfigTable)):
                pending.extend(
                    [(path + delimiter + k, v) for k, v in node.items()]
                )
                yield path, node
            elif isinstance(node, (FgtConfigSet, FgtConfigUnset)):
                yield path, node
            else:
                raise TypeError()


class FgtConfigObject(FgtConfigBody):
    """
    Represents a CONFIG command containing multiple SET, UNSET or
    CONFIG sub-commands.

    Sub-commands can be accessed using dictionary-like syntax or
    typed methods.

    Accessing parameters:
        You can retrieve parameters using any of the following:

        * `conf_obj.get('param')`
        * `conf_obj['param']`
        * `conf_obj.param` (attribute-style access)

    Example:
        Given the configuration:
            set vdom "root"
            set ip 192.168.254.99 255.255.255.0
            set allowaccess ping https
            set alias "mngt"
            config example
            end

        You can access the parameters as follows:

        * `obj['vdom']` or `obj.vdom`
            → returns `"root"`
        * `obj['ip']` or `obj.ip`
            → returns `['192.168.254.99', '255.255.255.0']`
        * `obj['example']` or obj.example
            → returns a `FgtConfigObject`

        The following methods provide type-checked access to specific node
        types:

        * `conf_obj.c_object('example')` → Returns a `FgtConfigObject`
        * `conf_obj.c_table('example')` → Returns a `FgtConfigTable`
        * `conf_obj.c_set('example')` → Returns a `FgtConfigSet`
    """

    def __getattr__(self, key: str) -> FgtConfigNode | str:
        """
        Return the sub-command using object.param syntax.
        """
        if key not in self.keys():
            return super().__getattribute__(key)

        attribute = self.get(key)
        if isinstance(attribute, FgtConfigSet) and len(attribute) == 1:
            return attribute[0]
        else:
            return attribute

    def c_table(
            self,
            key: str,
            default: Optional['FgtConfigTable'] = None
    ) -> 'FgtConfigTable':
        """
        Retrieve a configuration table by key, optionally returning a default.

        This convenience method fetches the configuration node associated with
        the given key. If the key is not present and a ``default`` is provided,
        the default is returned. If the resulting value is not an instance of
        ``FgtConfigTable``, a ``TypeError`` is raised.

        :param key: The key associated with the desired configuration table.
        :param default: A fallback value to return if the key is not found.
            Defaults to ``None``.
        :return: The configuration table associated with the key.
        :raises TypeError: If the retrieved value is not of type
            ``FgtConfigTable``.
        """
        value = self.get(key, default)
        if value is not None and not isinstance(value, FgtConfigTable):
            raise TypeError(f"'{key}' is not of type 'FgtConfigTable'")

        return value

    def c_object(
            self,
            key: str,
            default: Optional['FgtConfigObject'] = None
    ) -> Self:
        """
        Retrieve a configuration object by key, optionally returning a default.

        This convenience method fetches the configuration node associated with
        the given key. If the key is not present and a ``default`` is provided,
        the default is returned. If the resulting value is not an instance of
        ``FgtConfigObject``, a ``TypeError`` is raised.

        :param key: The key associated with the desired configuration object.
        :param default: A fallback value to return if the key is not found.
            Defaults to ``None``.
        :return: The configuration object associated with the key.
        :raises TypeError: If the retrieved value is not of type
            ``FgtConfigObject``.
        """
        value = self.get(key, default)
        if value is not None and not isinstance(value, FgtConfigObject):
            raise TypeError(f"'{key}' is not of type 'FgtConfigObject'")

        return value

    def c_set(
            self,
            key: str,
            default: Optional['FgtConfigSet'] = None
    ) -> 'FgtConfigSet':
        """
        Retrieve a configuration set by key, optionally returning a default.

        This convenience method fetches the configuration node associated with
        the given key. If the key is not present and a ``default`` is provided,
        the default is returned. If the resulting value is not an instance of
        ``FgtConfigSet``, a ``TypeError`` is raised.

        :param key: The key associated with the desired configuration set.
        :param default: A fallback value to return if the key is not found.
            Defaults to ``None``.
        :return: The configuration set associated with the key.
        :raises TypeError: If the retrieved value is not of type
            ``FgtConfigSet``.
        """
        value = self.get(key, default)
        if value is not None and not isinstance(value, FgtConfigSet):
            raise TypeError(f"'{key}' is not of type 'FgtConfigSet'")

        return value

    def param(
            self,
            key: str,
            default: Optional[str] = None
    ) -> str:
        """
        Return the value of a simple SET command.

        A simple SET command defines a configuration parameter with a single
        value, such as in: ``set status enable``.

        :param key: The name of the parameter.
        :param default: A fallback value to return if the parameter is not
            found. Defaults to ``None``.
        :return: The value of the parameter or the ``default`` value if the
            parameter is not defined in the CONFIG object.
        :raises TypeError: If the retrieved value is not from a
            ``FgtConfigSet``.
        :raises ValueError: If the SET command defines multiple values for the
            parameter.
        """
        value = self.c_set(key, FgtConfigSet([default]) if default else None)

        if value:
            if len(value) != 1:
                raise ValueError(
                    "param method is available only on SET command with one argument"
                )
            value = value[0]

        return value


class FgtConfigTable(FgtConfigBody):
    """ Represents a CONFIG command containing multiple EDIT commands """

    def __getitem__(self, item: int | str) -> FgtConfigObject:
        """
        Retrieve a configuration object by the given key.

        This method allows you to access configuration objects in the table by
        either a string or integer key.

        :param item: The item used to look up the configuration object. Can either
            be a string (e.g., ``"opt1"``) or an integer (e.g., ``1``).
        :return: The configuration object corresponding to the provided key.
        :raises TypeError: If the retrieved configuration node is not of type
            ``FgtConfigObject``.
        :raises KeyError: If the specified key is not found in the configuration
            table.

        :example:
            With the following configuration table:

            config test
                edit "opt1"
                next
                edit "opt2"
                next
            end

            - ``self['opt1']``
                returns the configuration object for ``"opt1"``.
            - ``self.['opt2']``
                returns the configuration object for ``"opt2"``.

            For a configuration table using numeric keys:

            config test
                edit 1
                next
                edit 2
                next
            end

            - ``self[1]``
                returns the configuration object for ``1``.
            - ``self[2]``
                returns the configuration object for ``2``.
        """
        if isinstance(item, int):
            value = super().get(str(item))
        elif isinstance(item, str):
            value = super().get(qus(item))
        else:
            raise TypeError("Invalid key type")

        if value and not isinstance(value, FgtConfigObject):
            raise TypeError(f"'{item}' is not of type 'FgtConfigObject'")

        return value

    def c_entry(
            self,
            key: str | int,
            default: Optional[FgtConfigObject] = None
    ) -> FgtConfigObject:
        try:
            return cast(FgtConfigObject, self[key])
        except KeyError:
            return default


@final
class FgtConfigSet(FgtConfigNode, FgtConfigTokens):
    """ Represents a SET command. """
    def __init__(self, parameters: FgtConfigTokens) -> None:
        super().__init__(parameters)

    def __eq__(self, other) -> bool:
        if isinstance(other, FgtConfigSet):
            return super().__eq__(other)
        elif isinstance(other, list):
            return self == FgtConfigSet(other)
        elif isinstance(other, str):
            return self == FgtConfigSet([other])
        else:
            raise TypeError()

    def traverse(
            self,
            key: str,
            fn: FgtConfigTraverseCallback,
            parents: FgtConfigStack,
            data: Any
    ) -> None:
        fn(True, (key, self), parents, data)


@final
class FgtConfigUnset(FgtConfigNode):
    """ Represents an UNSET command. """

    def traverse(
            self,
            key: str,
            fn: FgtConfigTraverseCallback,
            parents: FgtConfigStack,
            data: Any
    ) -> None:
        fn(True, (key, self), parents, data)

    def __len__(self) -> int:
        return 0


class FgtConfigRoot(FgtConfigObject):
    """
    Represents the root configuration object.

    This class provides methods for accessing sections within the root
    configuration and traversing through its entire configuration tree.
    """

    def sections(
            self,
            pattern: Optional[str] = None
    ) -> Iterator[tuple[str, FgtConfigTable | FgtConfigObject]]:
        """
        Returns all sections in the root configuration, optionally filtered by a
        pattern. Each yielded tuple contains the section key (as a string) and
        the corresponding section (as a ``FgtConfigObject`` or ``FgtConfigTable``
        instance).

        :example:
            for key, section in root.sections():
                print(key, section)

            for key, section in root.sections("system replacemsg *")
                print(key, section)
        """
        if pattern is None:
            for k, v in self.items():
                if isinstance(v, (FgtConfigTable, FgtConfigObject)):
                    yield k, v
        else:
            compiled_pattern = re.compile(pattern)
            for k, v in self.items():
                if isinstance(v, (FgtConfigTable, FgtConfigObject)):
                    if compiled_pattern.match(k):
                        yield k, v

    def traverse(
            self,
            key: str,
            fn: FgtConfigTraverseCallback,
            parents: FgtConfigStack,
            data: Any
    ) -> None:
        for item_key, item_value in self.items():
            item_value.traverse(item_key, fn, parents, data)


@final
class FgtConfigComments(FgtConfigTokens):
    _config_version_comment: Final[str] = '#config-version='

    def _config_version(self) -> list[str]:
        version = ["?-?"]
        for comment in self:
            if comment.startswith(self._config_version_comment):
                version = comment[len(self._config_version_comment):].split(':')
        return version

    @property
    def version(self) -> str:
        """ Return the FortiOS version. """
        config_version = self._config_version()[0]
        return config_version[config_version.index('-') + 1:]

    @property
    def model(self) -> str:
        """ Return the firewall model. """
        config_version = self._config_version()[0]
        return config_version[0:config_version.index('-')]


@final
class FgtConfig(object):
    """ A FortiGate configuration. """

    def __init__(
            self,
            comments: FgtConfigComments,
            root: FgtConfigRoot,
            vdoms: dict[str, FgtConfigRoot]
    ) -> None:
        """
        Initialize a configuration object with comments, root configuration, and
        VDOMs.

        This constructor initializes the configuration with the provided list of
        comments, the root configuration (which contains config objects and
        tables), and a dictionary of VDOMs, each containing its own root
        configuration. If VDOMs are not used, the `vdoms` dictionary should be
        empty.

        :param comments: A list of comments found at the start of the
            configuration file.
        :param root: A dictionary of configuration objects and tables.
        :param vdoms: A dictionary of root configurations for each VDOM. Should
            be empty if VDOMs are not used.

        :raises ValueError: If any value in the `root` dictionary is not an
            instance of `FgtConfigObject` or `FgtConfigTable`.
        """
        if not all(isinstance(v, (FgtConfigObject, FgtConfigTable)) for v in
                   root.values()
                   ):
            raise ValueError()

        self._comments: FgtConfigComments = comments
        self._root: FgtConfigRoot = root
        self._vdoms: dict[str, FgtConfigRoot] = vdoms
        self._indent: int = 4

    @property
    def comments(self) -> FgtConfigComments:
        """ Return the collection of comments """
        return self._comments

    @property
    def multi_vdom(self) -> bool:
        """ Return true if the firewall is configured with VDOMs"""
        return len(self._vdoms) > 0

    @property
    def root(self) -> FgtConfigRoot:
        """ Return the root configuration.

        The function returns all config objects/tables under 'config global'
        section in a multiple VDOMs configuration and the whole configuration
        (all config objects/tables) if VDOMs are not configured.
        """
        return self._root

    @property
    def vdoms(self) -> dict[str, FgtConfigRoot]:
        """ Return a dictionary of VDOMs. """
        return self._vdoms

    def make_config(
            self,
            item_filter: Optional[FgtConfigFilterCallback] = None,
            data: Optional[Any] = None
    ) -> list[str]:
        """
        Generate the configuration as a list of strings.

        This method creates the configuration by traversing the configuration
        tree and generating a string representation of each item. The list of
        strings can be joined to form the complete configuration.

        :param item_filter: An optional filtering callback. This function is
            called for each node in the configuration tree. If the callback
            returns `True`, the node is included. Defaults to `None`.
        :param data: Optional data that can be passed to the `item_filter`
            callback function. Defaults to `None`.

        :return: A list of strings representing the configuration.
        """

        def append_entry(
                begin_of_section: bool,
                item: FgtConfigItem,
                parents: FgtConfigStack,
                output_list: list[str]
        ) -> None:
            # check if we skip this item
            if item_filter and not item_filter(item, parents, data):
                return

            # extract key, value from the given item
            key = item[0]
            value = item[1]

            if isinstance(value, FgtConfigSet):
                line = f"set {key} {' '.join(value)}"
            elif isinstance(value, FgtConfigUnset):
                line = f"unset {key}"
            elif isinstance(value, (FgtConfigTable, FgtConfigObject)):
                if len(parents) == 0 or isinstance(parents[-1][1],
                                                   FgtConfigObject
                                                   ):
                    line = f"config {key}" if begin_of_section else "end"
                elif len(parents) > 0 or isinstance(parents[-1][1],
                                                    FgtConfigTable
                                                    ):
                    line = f"edit {key}" if begin_of_section else "next"
                else:
                    raise ValueError()
            else:
                raise ValueError()

            # create indentation spaces to prefix the line
            spaces: str = ' ' * (len(parents) * self._indent)

            # append it to the output list
            output_list.append(spaces + line)

        output: list[str] = []
        if self.multi_vdom:
            output.append('')
            output.append('config vdom')
            for k in self.vdoms.keys():
                output.append('edit ' + k)
                output.append('next')
            output.append('end')
            output.append('')
            output.append('config global')
            self.root.traverse('', append_entry, FgtConfigStack(), output)
            output.append('end')
            output.append('')
            for k, v in self.vdoms.items():
                output.append('config vdom')
                output.append('edit ' + k)
                v.traverse('', append_entry, deque(), output)
                output.append('end')
                output.append('')
        else:
            self.root.traverse('', append_entry, FgtConfigStack(), output)
        return output

    def __repr__(self) -> str:
        return "\n".join(self.make_config())

    def write(
            self,
            file: TextIO,
            include_comments: bool,
            item_filter: Optional[FgtConfigFilterCallback] = None,
            data: Optional[Any] = None
    ) -> None:
        """ Write the configuration to a file.

        :param file: the output file.
        :param include_comments: output configuration comments when true.
        :param item_filter: an optional filtering callback. This function is
            called for each node in the configuration tree.  The node is included
            if the callback returns true.
        :param data: optional data passed to the item_filter callback.
        """
        if include_comments and len(self.comments) > 0:
            file.write("\n".join(self.comments))
            file.write("\n")
        file.write("\n".join(self.make_config(item_filter, data)))
        file.write("\n")
