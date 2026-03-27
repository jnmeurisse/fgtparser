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
from collections.abc import Callable, Iterator
from enum import Enum, auto
from functools import cache
from typing import Any, Final, Optional, TextIO, final, Iterable, MutableMapping, TypeVar, Type

FgtConfigToken = str
""" A token in a config file. A token is a sequence of characters. """

FgtConfigTokens = list[FgtConfigToken]
""" A list of tokens, the list can be empty. """

FgtConfigItem = tuple[str, 'FgtConfigNode']
""" Represents the parameter name and the associated configuration node. """

FgtConfigStack = deque[FgtConfigItem]
""" A stack of configuration items.
This stack is generated during the traversal of the configuration tree. """


class FgtNodeTransition(Enum):
    """ a flag indicating if we enter or leave a node when traversing the configuration tree. """
    ENTER_NODE = auto()
    EXIT_NODE = auto()


FgtConfigTraverseCallback = Callable[
    [FgtNodeTransition, FgtConfigItem, FgtConfigStack, Any], None]
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
    Unquotes a string by removing surrounding double quotes and un-escaping
    escaped quotes and backslashes.
    """
    if len(arg) < 2 or (arg[0] != '"' or arg[-1] != '"'):
        res = arg
    else:
        res = arg[1:-1].replace('\\"', '"').replace('\\\\', '\\')
    return res


def qus(arg: str) -> str:
    """
    Quotes a string by wrapping it in double quotes and escaping
    any existing double quotes and backslashes.
    """
    return '"{}"'.format(arg.replace('\\', '\\\\').replace('"', '\\"'))


class FgtAttrView:
    """
    A proxy view that enables attribute-style access to a ``FgtConfigObject``.

    This class wraps a ``FgtConfigObject`` and allows its parameters to be
    accessed as Python attributes rather than via dictionary-style lookups.
    Nested ``FgtConfigObject`` values are automatically wrapped in a new
    ``FgtAttrView``, enabling fluent chained access.

    Typically obtained via the ``FgtConfigObject.attr`` property rather than
    instantiated directly.

    Example:
        Given the configuration::

            set vdom "root"
            set ip 192.168.254.99 255.255.255.0
            config example
                set status enable
            end

        You can access parameters as follows::

            obj.attr.vdom           # returns '"root"'
            obj.attr.ip             # returns ['192.168.254.99', '255.255.255.0']
            obj.attr.example.status # returns 'enable'  (chained access)

    :raises AttributeError: If the requested attribute does not exist as a key
        in the underlying ``FgtConfigObject``.
    """
    def __init__(self, obj: 'FgtConfigObject') -> None:
        self._obj = obj

    def __getattr__(self, key):
        try:
            value = self._obj[key]
        except KeyError:
            raise AttributeError(key) from None

        # auto-wrap objects for chaining
        if isinstance(value, FgtConfigObject):
            return FgtAttrView(value)
        return value


class FgtConfigVisitor:
    """
    Base class for implementing visitors that traverse a configuration tree.

    Subclass ``FgtConfigVisitor`` and override ``visit_enter`` and/or
    ``visit_exit`` to process nodes during a traversal initiated by
    ``FgtConfigNode.traverse``.

    For each node visited, ``visit_enter`` is called before descending
    into its children, and ``visit_exit`` is called after all children
    have been visited. If ``visit_enter`` returns ``False``, the entire
    subtree rooted at that node is skipped and ``visit_exit`` is **not**
    called for that node.


    The default implementations of both `visit_enter` and `visit_exit`
    are no-ops, so subclasses only need to override the methods relevant
     to their use case.
    """
    def visit_enter(self, item: FgtConfigItem, parents: FgtConfigStack) -> bool:
        """Called before visiting children. Return False to prune subtree."""
        return True

    def visit_exit(self, item: FgtConfigItem, parents: FgtConfigStack) -> None:
        """Called after visiting children. Not called if visit_enter returned False."""
        return


class FgtConfigNode(ABC):
    """ Represents a configuration node in the configuration object tree.

    A configuration node can be a SET command, an UNSET command or a CONFIG
    command. A derived class exists for each object type.  A ``FgtConfigNode``
    is always accessed through a dictionary.
    """

    @abstractmethod
    def children(self) -> Iterator[FgtConfigItem]:
        """
        Yield the direct children of this node as (key, node) pairs.

        Leaf nodes (``FgtConfigSet``, ``FgtConfigUnset``) yield nothing.
        Body nodes (``FgtConfigObject``, ``FgtConfigTable``) yield their
        dictionary entries.

        :yield: A tuple of (parameter name, child node) for each direct
            child of this node.
        """

    def traverse(
            self,
            key: str,  # noqa: ARG002
            visitor: FgtConfigVisitor,
            parents: FgtConfigStack
    ) -> None:
        """
        Recursively traverse the configuration subtree rooted at this node,
        invoking ``visitor`` on each node encountered.

        For each node, ``visitor.visit_enter`` is called before
        descending into its children, and ``visitor.visit_exit``
        is called after. If ``visitor.visit_enter`` returns
        ``False``, the entire subtree rooted at that node is pruned and
        ``visitor.visit_exit`` is not called for it.

        :param key: The key under which this node is stored in its parent
            dictionary. Passed as part of the ``FgtConfigItem`` tuple to
            the visitor callbacks.
        :param visitor: The visitor whose ``visitor.visit_enter``
            and ``visitor.visit_exit`` methods are invoked at
            each node.
        :param parents: A stack of ``(key, node)`` pairs representing the
            ancestors of the current node, from the traversal root down to the
            immediate parent. The caller is responsible for passing an empty
            ``FgtConfigStack`` at the top level.
        """
        item = (key, self)
        if not visitor.visit_enter(item, parents):
            return  # subtree pruned, visit_exit not called

        parents.append((key, self))

        for child_key, child_node in self.children():
            child_node.traverse(child_key, visitor, parents)

        parents.pop()
        visitor.visit_exit(item, parents)


T = TypeVar("T")


class FgtConfigDict(MutableMapping[str, FgtConfigNode]):
    """ A dictionary of configuration nodes. """
    def __init__(self, data: Optional[dict[str, FgtConfigNode]] = None) -> None:
        self._data: dict[str, FgtConfigNode] = data or {}

    def __getitem__(self, key: str) -> FgtConfigNode:
        return self._data[key]

    def __setitem__(self, key: str, value: FgtConfigNode) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def _get_as_type(
            self,
            key: str,
            expected_type: Type[T],
            default: Optional[T] = None
    ) -> Optional[T]:
        """
        Retrieves a value and asserts its type.
        """
        if (value := self.get(key)) is None:
            return default

        if not isinstance(value, expected_type):
            msg = f"Key '{key}' expected {expected_type.__name__}, but got {type(value).__name__}"
            raise TypeError(msg)

        return value

    def skeys(self) -> list[str]:
        """
        :return: A list of all dictionary keys, sorted case-insensitively.
        """
        return sorted(self._data.keys(), key=lambda s: s.lower())


class FgtConfigBody(FgtConfigNode, FgtConfigDict, ABC):
    """ An abstract base class for a CONFIG table or a CONFIG object. """

    def children(self) -> Iterator[FgtConfigItem]:
        """
        Yield all entries in this node's dictionary as (key, node) pairs.

        Both ``FgtConfigObject`` and ``FgtConfigTable`` store their
        sub-commands in an inherited ``FgtConfigDict``, so this single
        implementation covers both. Subclasses may override if they need
        to filter or reorder children.

        :yield: A tuple of (parameter name, child node) for each entry,
            in insertion order.
        """
        yield from self.items()

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
            if isinstance(node, FgtConfigBody):
                pending.extend(
                    [(path + delimiter + k, v) for k, v in node.children()]
                )
                yield path, node
            elif isinstance(node, (FgtConfigSet, FgtConfigUnset)):
                yield path, node
            else:
                msg = f"Unexpected node type '{type(node).__name__}' at path '{path}'"
                raise TypeError(msg)


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

        * `obj['vdom']` or `obj.attr.vdom`
            → returns `"root"`
        * `obj['ip']` or `obj.attr.ip`
            → returns `['192.168.254.99', '255.255.255.0']`
        * `obj['example']` or obj.attr.example
            → returns a `FgtConfigObject`

        The following methods provide type-checked access to specific node
        types:

        * `conf_obj.c_object('example')` → Returns a `FgtConfigObject`
        * `conf_obj.c_table('example')` → Returns a `FgtConfigTable`
        * `conf_obj.c_set('example')` → Returns a `FgtConfigSet`
    """
    @property
    def attr(self) -> FgtAttrView:
        return FgtAttrView(self)

    def c_table(
            self,
            key: str,
            default: Optional['FgtConfigTable'] = None
    ) -> Optional['FgtConfigTable']:
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
        return self._get_as_type(key, FgtConfigTable, default)

    def c_object(
            self,
            key: str,
            default: Optional['FgtConfigObject'] = None
    ) -> Optional['FgtConfigObject']:
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
        return self._get_as_type(key, FgtConfigObject, default)

    def c_set(
            self,
            key: str,
            default: Optional['FgtConfigSet'] = None
    ) -> Optional['FgtConfigSet']:
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
        return self._get_as_type(key, FgtConfigSet, default)

    def param(
            self,
            key: str,
            default: Optional[str] = None
    ) -> Optional[str]:
        """
        Return the value of a simple SET command.

        A simple SET command defines a configuration parameter with a single
        value, such as in: ``set status enable``.

        :param key: The name of the parameter.
        :param default: A fallback value to return if the parameter is not
            found. Defaults to ``None``.
        :return: The value of the parameter or the ``default`` value if the
            parameter is not defined in the CONFIG object.
        :raises TypeError: If the retrieved value is not from a ``FgtConfigSet``.
        :raises ValueError: If the SET command defines multiple values for the
            parameter.
        """
        if (value := self.c_set(key)) is None:
            return default

        if len(value) != 1:
            msg = "param method is available only on SET command with one argument"
            raise ValueError(msg)
        return value[0]


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
            value = self._data.get(str(item))
        elif isinstance(item, str):
            value = self._data.get(item)
            if value is None:
                value = self._data.get(qus(item))
        else:
            msg = f"'{type(item)}' is not a valid type"
            raise TypeError(msg)

        if value is None:
            raise KeyError(item)

        if not isinstance(value, FgtConfigObject):
            msg = f"'{item}' is not of type 'FgtConfigObject'"
            raise TypeError(msg)

        return value

    def c_entry(
            self,
            key: str | int,
            default: Optional[FgtConfigObject] = None
    ) -> Optional[FgtConfigObject]:
        try:
            return self[key]
        except KeyError:
            return default


@final
class FgtConfigSet(FgtConfigNode):
    """ Represents a SET command. """
    def __init__(self, parameters: Iterable[str]) -> None:
        self._parameters = list(parameters)

    def __iter__(self) -> Iterator[str]:
        return iter(self._parameters)

    def __len__(self) -> int:
        return len(self._parameters)

    def __getitem__(self, idx: int) -> str:
        return self._parameters[idx]

    def __eq__(self, other) -> bool:
        """
         Compare this ``FgtConfigSet`` for equality with another object.

         Supports three comparison types:

         * ``FgtConfigSet`` — two sets are equal if they contain the same
           sequence of parameters in the same order.
         * ``str`` — a set with exactly one parameter is equal to a string
           if that parameter matches the string. A set with zero or more
           than one parameter is never equal to any string.
         * ``list`` — a set is equal to a list if its parameters match the
           list element-for-element.

         .. warning::
             Operand order matters when comparing against ``str``.
             Python evaluates ``"enable" == cfg_set`` by calling
             ``str.__eq__`` first, which returns ``NotImplemented`` for
             unknown types; the reflected path does not exist for ``__eq__``,
             so Python falls back to identity comparison and the result is
             always ``False``. Always place the ``FgtConfigSet`` on the left:
             ``cfg_set == "enable"``.

         :param other: The object to compare against.
         :return: ``True`` if the objects are considered equal, ``False`` if
             they are not, or ``NotImplemented`` if the comparison is not
             supported for the given type.
         """
        if isinstance(other, FgtConfigSet):
            return self._parameters == other._parameters
        if isinstance(other, list):
            return self._parameters == other
        if isinstance(other, str):
            return len(self._parameters) == 1 and self._parameters[0] == other
        return NotImplemented

    def children(self) -> Iterator[FgtConfigItem]:
        """
        Yield nothing — a SET command has no child nodes.

        :yield: Nothing.
        """
        return iter([])


@final
class FgtConfigUnset(FgtConfigNode):
    """ Represents an UNSET command. """

    def __len__(self) -> int:
        return 0

    def children(self) -> Iterator[FgtConfigItem]:
        """
        Yield nothing — a UNSET command has no child nodes.

        :yield: Nothing.
        """
        return iter([])


class FgtConfigRoot(FgtConfigObject):
    """
    Represents the root configuration object.

    This class provides methods for accessing sections within the root
    configuration and traversing through its entire configuration tree.
    """
    def __init__(self, config: FgtConfigObject):
        super().__init__(dict(config._data))

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
                if isinstance(v, (FgtConfigTable, FgtConfigObject)) and compiled_pattern.match(k):
                    yield k, v

    def traverse(
            self,
            key: str,  # noqa: ARG002
            visitor: FgtConfigVisitor,
            parents: FgtConfigStack
    ) -> None:
        """
        Traverse all top-level sections of the root configuration, forwarding
        each to ``FgtConfigNode.traverse``.

        Unlike the base implementation, this override does **not** invoke
        ``visitor.visit_enter`` or ``visitor.visit_exit`` for the root node itself.
        The root is a structural container with no representation in the
        FortiGate file format — it has no ``config``/``end`` envelope — so
        emitting enter/exit events for it would produce spurious output in
        callers such as ```FgtConfig.dumps```.

        :param key: Ignored. Present only to satisfy the
            ``FgtConfigNode.traverse`` interface.
        :param visitor: The visitor forwarded unchanged to each top-level
            child's ``FgtConfigNode.traverse`` call.
        :param parents: The ancestor stack forwarded unchanged to each
            top-level child. Callers should pass an empty
            ``FgtConfigStack`` at the top level.
        """
        for item_key, item_value in self.items():
            item_value.traverse(item_key, visitor, parents)


@final
class FgtConfigComments:
    _config_version_comment: Final[str] = '#config-version='

    def __init__(self, tokens: Iterable[str] = ()) -> None:
        self._tokens: list[str] = list(tokens)

    def __iter__(self) -> Iterator[str]:
        return iter(self._tokens)

    def __len__(self) -> int:
        return len(self._tokens)

    def __getitem__(self, idx: int) -> str:
        return self._tokens[idx]

    def __eq__(self, other) -> bool:
        """
        Compare this ``FgtConfigComments`` for equality with another object.
        Warning::
            Operand order matters when comparing against ``list``.
            Always place the ``FgtConfigComments`` on the left:
            ``comments == [...]``.
        """
        if isinstance(other, FgtConfigComments):
            return self._tokens == other._tokens
        if isinstance(other, list):
            return self._tokens == other
        return NotImplemented

    def append(self, comment: str) -> None:
        self._tokens.append(comment)

    def _config_version(self) -> list[str]:
        """
        Extract and split the config-version string from the comment block.

        Scans all comments for a line beginning with the config-version
        prefix (``#config-version=``). When found, the remainder of the
        line after the prefix is split on ``':'`` and returned as a list
        of fields. If no such comment exists, the sentinel ``["?-?"]`` is
        returned so that callers always receive a non-empty list with a
        parseable first element.

        The last matching comment wins when duplicates are present, which
        mirrors FortiGate behaviour where a later header line overrides an
        earlier one.

        Expected format of the raw comment line::

            #config-version=FGT60F-7.4.1-FW-build2571-230510:opmode=0:...

        In this example the return value would be::

            ['FGT60F-7.4.1-FW-build2571-230510', 'opmode=0', ...]

        :return: A list of fields extracted from the config-version comment,
            or ``['?-?']`` if no such comment is present.
        """
        version = ["?-?"]
        for comment in self:
            if comment.startswith(self._config_version_comment):
                version = comment[len(self._config_version_comment):].split(':')
        return version

    @cache
    def _parsed_version(self) -> tuple[str, str]:
        """
        Parse the config-version comment into a (model, version) pair.

        Returns ``('?', '?')`` for either component that cannot be found.
        Cached because the comment list is immutable after construction.
        """
        raw, sep, version = self._config_version()[0].partition('-')
        if not sep:
            return '?', '?'
        return raw, version

    @property
    def version(self) -> str:
        """Return the FortiOS version, or ``'?'`` if not present."""
        return self._parsed_version()[1]

    @property
    def model(self) -> str:
        """Return the firewall model, or ``'?'`` if not present."""
        return self._parsed_version()[0]


class _VisitorWriter(FgtConfigVisitor):
    def __init__(
            self,
            indent: int,
            item_filter: Optional[FgtConfigFilterCallback] = None,
            data: Optional[Any] = None
    ) -> None:
        self._indent = indent
        self._item_filter = item_filter
        self._data = data
        self.output: list[str] = []

    def _spaces(self, parents: FgtConfigStack) -> str:
        return ' ' * (len(parents) * self._indent)

    @staticmethod
    def _is_under_object(parents: FgtConfigStack) -> bool:
        return len(parents) == 0 or isinstance(parents[-1][1], FgtConfigObject)

    def visit_enter(self, item: FgtConfigItem, parents: FgtConfigStack) -> bool:
        if self._item_filter is not None and not self._item_filter(item, parents, self._data):
            return False                # prune subtree, visit_exit won't be called

        key, value = item
        spaces = self._spaces(parents)

        if isinstance(value, FgtConfigSet):
            self.output.append(f"{spaces}set {key} {' '.join(value)}")
        elif isinstance(value, FgtConfigUnset):
            self.output.append(f"{spaces}unset {key}")
        elif isinstance(value, (FgtConfigTable, FgtConfigObject)):
            tag = "config" if self._is_under_object(parents) else "edit"
            self.output.append(f"{spaces}{tag} {key}")
        else:
            raise TypeError(f"Unexpected node type: {type(value).__name__}")

        return True

    def visit_exit(self, item: FgtConfigItem, parents: FgtConfigStack) -> None:
        key, value = item
        spaces = self._spaces(parents)

        if isinstance(value, (FgtConfigTable, FgtConfigObject)):
            tag = "end" if self._is_under_object(parents) else "next"
            self.output.append(f"{spaces}{tag}")


@final
class FgtConfig:
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

        :param comments: A list of comments found at the start of the configuration file.
        :param root: A dictionary of configuration objects and tables.
        :param vdoms: A dictionary of root configurations for each VDOM. Should
            be empty if VDOMs are not used.

        :raises ValueError: If any value in the `root` dictionary is not an
            instance of `FgtConfigObject` or `FgtConfigTable`.
        """
        for k, v in root.items():
            if not isinstance(v, (FgtConfigObject, FgtConfigTable)):
                msg = f"Value at key '{k}' must be FgtConfigObject or FgtConfigTable, got {type(v).__name__}."
                raise ValueError(msg)

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

    def dumps(
            self,
            item_filter: Optional[FgtConfigFilterCallback] = None,
            data: Optional[Any] = None
    ) -> list[str]:
        visitor = _VisitorWriter(self._indent, item_filter, data)

        if self.multi_vdom:
            visitor.output.extend(('', 'config vdom'))
            for k in self.vdoms:
                visitor.output.extend(('edit ' + k, 'next'))
            visitor.output.extend(('end', '', 'config global'))
            self.root.traverse('', visitor, FgtConfigStack())
            visitor.output.extend(('end', ''))
            for k, v in self.vdoms.items():
                visitor.output.extend(('config vdom', 'edit ' + k))
                v.traverse('', visitor, FgtConfigStack())
                visitor.output.extend(('end', ''))
        else:
            self.root.traverse('', visitor, FgtConfigStack())

        return visitor.output

    def __repr__(self) -> str:
        return "\n".join(self.dumps())

    def dump(
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
        file.write("\n".join(self.dumps(item_filter, data)))
        file.write("\n")
