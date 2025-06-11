#
# This file is part of fgtparser -  A parser for FortiGate Configuration Files
#
# Copyright (C) 2025  Jean Noel Meurisse
# SPDX-License-Identifier: GPL-3.0-only
#

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, TextIO, cast, final

from ._config import (
    FgtConfig,
    FgtConfigComments,
    FgtConfigNode,
    FgtConfigObject,
    FgtConfigRoot,
    FgtConfigSet,
    FgtConfigTable,
    FgtConfigToken,
    FgtConfigTokens,
    FgtConfigUnset,
)

_Char = str
""" The _Char type represents a single character."""

FgtConfigRootFactory = Callable[[str, FgtConfigObject], FgtConfigRoot]
""" Callable used to instantiate a `FgConfigRoot`.  """


@dataclass
class _StreamPosition:
    """ A position in a stream of characters """
    row: int
    col: int

    def __repr__(self):
        return f"({self.row}, {self.col})"

    def format(self) -> str:
        return f"line {self.row}, column {self.col}"


class FgtConfigSyntaxError(Exception):
    """ raised when a syntax error is detected """


class FgtConfigEosError(FgtConfigSyntaxError):
    """ raised when an unexpected end of stream is detected """

    def __init__(self):
        super().__init__("unexpected end of stream")


class FgtConfigParser:
    """ This class implements a parser of a FortiGate configuration file.

    The accepted syntax of this parser is:
        |   config              = (comment NL)* (config_object)*
        |   config_object       = "config" parameters NL (config_table | config_list) NL "end"
        |   config_table        = config_table_entry | config_table_entry config_table
        |   config_vdom_entry   = "edit" parameter NL config_list NL
        |   config_table_entry  = "edit"  parameter NL config_list NL "next"
        |   config_list         = config_list_item | config_list_item config_list
        |   config_list_item    = set_command | unset_command | config_object
        |   set-command         = "set" reserved-word parameters NL
        |   unset-command       = "unset" reserved-word NL
        |   parameters          = parameter | parameter parameters
        |   parameter           = quoted-string | reserved-word
    with
        NL  = one or more new line characters.

        quoted-string
            A quoted-string argument is a sequence of characters between double-quote (").
            It can span multiple lines.  The double-quote and the backslash, are not
            present as-is inside a quoted string.  These characters are preceded by
            the escape character (\\).

        reserved-word
            A reserved-word argument is a sequence of alphanumerical characters.

        comment
            A line starting with the character #

    FortiGate configuration syntax is partially described in
    https://docs.fortinet.com/document/fortigate/7.6.2/administration-guide/508024/command-syntax
    """
    VDOM: Final[str] = 'vdom'

    @final
    class Lexer:
        # Special characters
        EOS: Final[_Char] = ''  # end of stream
        EOL: Final[_Char] = '\n'  # end of line
        QUOTE: Final[_Char] = '\"'

        def __init__(self, input_stream: TextIO) -> None:
            """ Initialize the lexer """
            self._stream = input_stream
            self._char: _Char | None = None
            self._pos: _StreamPosition = _StreamPosition(1, 1)
            self._token: FgtConfigToken | None = None

        def _update_position(self, c: _Char) -> None:
            """ Keep track of the (line, column) position in the input stream """
            self._pos.col += 1
            if c == self.EOL:
                self._pos.row += 1
                self._pos.col = 1

        @classmethod
        def _is_eol(cls, token: FgtConfigToken) -> bool:
            """ Return true if `token` is an end of line.  """
            return token in {cls.EOL, cls.EOS}

        @classmethod
        def is_eos(cls, token: FgtConfigToken) -> bool:
            """ Return true if `token` is an end of stream.  """
            return token == cls.EOS

        @classmethod
        def is_comment(cls, token: FgtConfigToken) -> bool:
            """ Return true if `token` is a comment """
            return token[0] == "#"

        def _next(self) -> _Char:
            """ Return the next character from the input stream.

            An EOS character is returned when the stream is exhausted.
            The EOS character is represented as an empty string.
            """
            if self._char is None:
                c = self._stream.read(1)
                self._update_position(c)
            else:
                c = self._char
                self._char = None

            return c

        def _unget(self, c: _Char) -> None:
            """ Push back the character so that it becomes available when calling
                _next.
            """
            self._char = c

        def _next_ns(self) -> _Char:
            """ Return the next non-space character including EOF or EOL.

            \\\\n is used as a delimiter and not considered as a space.
            """
            c = self._next()
            while c.isspace() and not self._is_eol(c):
                c = self._next()
            return c

        def get_pos(self) -> _StreamPosition:
            """ Return the current position in the stream. """
            return self._pos

        def push_token(self, token: FgtConfigToken) -> None:
            """ Push back the given token get by the `next_token` method """
            self._token = token

        def next_token(self) -> FgtConfigToken:
            """ Return the next token from the input stream. The token can be :
                - a comment  (a line starting with #)
                - a quoted string
                - a reserved word
                - a newline (EOL)
                - an end of stream (EOS)

            :return: a token.
            :raise FgtConfigSyntaxError: if a quoted string is not correctly
                delimited.
            """
            token: FgtConfigToken
            if self._token is not None:
                token = self._token
                self._token = None
            else:
                c: _Char = self._next_ns()

                if self.is_eos(c):
                    # This is the end of the characters stream
                    token = c

                elif self._is_eol(c):
                    # This is an end of line, just return it
                    token = c

                elif c == '#':
                    # This is a comment line.
                    # Fill the token until the end of line is encountered.
                    token = ''
                    while not self._is_eol(c):
                        token += c
                        c = self._next()

                elif c == self.QUOTE:
                    # a quoted string
                    token = c
                    while True:
                        c = self._next()
                        if self.is_eos(c):
                            msg = f"unbalanced quote at line {self.get_pos().row}"
                            raise FgtConfigSyntaxError(msg)

                        if c == '\\':
                            token += c
                            c = self._next()
                            if self.is_eos(c):
                                msg = f"escape error at line {self.get_pos().row}"
                                raise FgtConfigSyntaxError(msg)
                            token += c

                        elif c == self.QUOTE:
                            token += c
                            break
                        else:
                            token += c

                else:
                    # This is a word (unquoted string).
                    # Fill until a space is found.
                    token = ""
                    while not (c.isspace() or self._is_eol(c)):
                        token += c
                        c = self._next()
                    self._unget(c)

            return token

        def next_parameters(self) -> FgtConfigTokens:
            """ Return all tokens on the current line.

            This function is used to get all parameters after CONFIG,
            SET, UNSET or EDIT commands.

            :returns: a list of tokens
            """
            tokens: FgtConfigTokens = FgtConfigTokens()
            while not self._is_eol(token := self.next_token()):
                if self.is_comment(token):
                    msg = f"unexpected comment found at {self.get_pos().format()}"
                    raise FgtConfigSyntaxError(msg)

                tokens.append(token)

            return tokens

        def next_snl_token(self, raise_eos: bool = True) -> FgtConfigToken:
            """ Skip all spaces and new lines and return the next token.

            By default, the method raises an exception if an EOS is encountered
            unless `raise_eos`is set to False. In that particular case, the EOS
            token is returned.

            :return: a token
            :raise FgtConfigEosError: if an end of stream is encountered before
                a new token is available.
            """
            token = self.next_token()
            while self._is_eol(token) and not self.is_eos(token):
                token = self.next_token()

            if raise_eos and self.is_eos(token):
                raise FgtConfigEosError

            return token

    @classmethod
    def _parse_set_command(cls, lexer: Lexer) -> tuple[str, FgtConfigSet]:
        """ Parse a SET command.

        The method returns a pair consisting of the parameter name and a
        list of values :
            (<parameter_name>, [<parameter_value1>, <parameter_value2>, ...]).

        :return: the parameter name and a `FgtConfigSet` object containing all
            values.
        :raise FgtConfigSyntaxError: if the set command can not be parsed.
        """
        tokens: FgtConfigTokens = lexer.next_parameters()
        if len(tokens) < 2:
            msg = f"invalid set command at line {lexer.get_pos().row - 1}, missing command argument"
            raise FgtConfigSyntaxError(msg)

        return tokens[0], FgtConfigSet(tokens[1:])

    @classmethod
    def _parse_unset_command(cls, lexer: Lexer) -> tuple[str, FgtConfigUnset]:
        """ Parse a UNSET command.

        The method returns a pair consisting of the parameter name and an empty
        list of values : (<parameter_name>, []).

        :return: the parameter name and `FgtConfigSet` object.
        :raise FgtConfigSyntaxError: if the unset command can not be parsed.
        """
        tokens: FgtConfigTokens = lexer.next_parameters()
        if len(tokens) != 1:
            msg = f"invalid unset command at line {lexer.get_pos().row - 1}"
            raise FgtConfigSyntaxError(msg)

        return tokens[0], FgtConfigUnset()

    @classmethod
    def _parse_config_command(
        cls,
        entry: FgtConfigToken,
        lexer: Lexer
    ) -> tuple[str, FgtConfigNode]:
        """ Parse a configuration command.

        :return: the parameter name and a `FgtConfigNode` object.
        :raise FgtConfigSyntaxError: if the configuration command can not be parsed.
        """
        if entry == 'set':
            return cls._parse_set_command(lexer)

        if entry == 'unset':
            return cls._parse_unset_command(lexer)

        if entry == 'config':
            return cls._parse_config(lexer)

        msg = f"invalid entry '{entry[:10]}' near {lexer.get_pos().format()}"
        raise FgtConfigSyntaxError(msg)

    @classmethod
    def _parse_table_entry(
        cls,
        lexer: Lexer,
        vdom: bool = False
    ) -> tuple[str, FgtConfigObject]:
        """ Parse all configuration commands after EDIT up to NEXT delimiter.

        :return: the parameter name and a `FgtConfigObject` object.
        :raise FgtConfigSyntaxError: if an instruction can not be parsed.
        """
        edit_key: FgtConfigTokens = lexer.next_parameters()
        if len(edit_key) != 1:
            msg = f"invalid table configuration near {lexer.get_pos().format()}"
            raise FgtConfigSyntaxError(msg)

        # parse until next keyword or end keyword.  The end keyword is accepted only in a vdom
        # root configuration.  A configuration file including vdoms contains a table param without
        # the `next` instruction.  This particular case forces us to detect the end keyword as a
        # delimiter of an edit instruction.
        # Example:
        #       config vdom
        #           edit vdom_name
        #               config system settings
        #                   set ...
        #               end
        #       end
        #
        config = FgtConfigObject()
        token: FgtConfigToken = lexer.next_snl_token()
        while not ((token == 'next') or (vdom and token == 'end')):
            k, v = cls._parse_config_command(token, lexer)
            config[k] = v
            token = lexer.next_snl_token()

        if vdom and token == 'end':
            lexer.push_token(token)

        return edit_key[0], config

    @classmethod
    def _parse_config(
        cls,
        lexer: Lexer
    ) -> tuple[str, FgtConfigTable | FgtConfigObject]:
        """ Parse all configuration commands after CONFIG up to END delimiter.

        :return: the parameter name and a `FgtConfigTable` or `FgtConfigObject`.
        :raise FgtConfigSyntaxError: if configuration command can not be parsed.
        """
        # get config keys
        config_keys: FgtConfigTokens = lexer.next_parameters()
        if len(config_keys) == 0:
            msg = f"invalid config near {lexer.get_pos().format()}"
            raise FgtConfigSyntaxError(msg)

        # parse until end keyword
        token = lexer.next_snl_token()
        config: FgtConfigTable | FgtConfigObject
        if token == 'edit':
            # it is a table object.
            # Example:
            #    config name \n edit 1\n next\n edit 2\n next\n end\n
            config = FgtConfigTable()
            while token != 'end':
                tk, tv = cls._parse_table_entry(lexer, config_keys[0] == FgtConfigParser.VDOM)
                config[tk] = tv

                token = lexer.next_snl_token()
        else:
            # it is a config object.
            # Example:
            #    config name\n set name1 value1\nset name2 value2\nconfig subconf\nend\nend
            config = FgtConfigObject()
            while token != 'end':
                ck, cv = cls._parse_config_command(token, lexer)
                config[ck] = cv

                token = lexer.next_snl_token()

        return " ".join(config_keys), config

    _root_config_factory: FgtConfigRootFactory = lambda _, cfg: FgtConfigRoot(cfg)

    @classmethod
    def get_root_config_factory(cls) -> FgtConfigRootFactory:
        return FgtConfigParser._root_config_factory

    @classmethod
    def set_root_config_factory(cls, factory: FgtConfigRootFactory) -> None:
        cls._root_config_factory = factory

    @classmethod
    def parse(
        cls,
        input_stream: TextIO,
    ) -> FgtConfig:
        """ Parse a FortiGate configuration.

        :param input_stream: the configuration
        :return: a FgtConfig object
        :raise FgtConfigSyntaxError: if a syntax error is detected
        """
        # get a root factory
        factory_fn = cls.get_root_config_factory()

        # allocate various dictionaries
        comments = FgtConfigComments()
        global_config = FgtConfigObject()
        vdoms_config = dict[str, FgtConfigRoot]()

        # parse the configuration stream
        lexer = cls.Lexer(input_stream)

        # ... parse all comments and empty lines
        while (token := lexer.next_snl_token(raise_eos=False)).startswith('#'):
            comments.append(token)

        # ... parse all config statements
        while not lexer.is_eos(token):
            if token == 'config':
                k, v = cls._parse_config(lexer)
                if k == FgtConfigParser.VDOM:
                    # a vdom is detected.  The vdom configuration file contains duplicate entries.
                    # The first definition is a table declaring the name of the different vdoms.
                    # The second definition contains the actual configuration.  In our
                    # implementation the first definition is overloaded by the second occurrence.
                    # It does not matter since we preserve the name of the vdom.
                    for entry, value in v.items():
                        if isinstance(value, FgtConfigObject):
                            vdoms_config[entry] = factory_fn(comments.version, value)
                        else:
                            msg = f"invalid type '{type(value)}' at line {lexer.get_pos().row - 1}"
                            raise TypeError(msg)
                else:
                    global_config[k] = v

            else:
                msg = f"invalid entry '{token[:10]}' near {lexer.get_pos().format()}"
                raise FgtConfigSyntaxError(msg)

            token = lexer.next_snl_token(raise_eos=False)

        # Handle vdom and non vdom configurations.
        # A vdom config has a unique config global section and multiple config vdom sections.
        # A non vdom config has multiple config sections.
        config_section: FgtConfigObject
        if len(vdoms_config) == 0:
            config_section = global_config
        else:
            config_section = cast(FgtConfigObject, global_config['global'])

        return FgtConfig(
            comments,
            factory_fn(comments.version, config_section),
            vdoms_config
        )
