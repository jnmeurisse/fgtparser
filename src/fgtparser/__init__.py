#
# This file is part of fgtparser -  A parser for FortiGate Configuration Files
#
# Copyright (C) 2025  Jean Noel Meurisse
# SPDX-License-Identifier: GPL-3.0-only
#

""" fgtparser - A FortiGate configuration file parser """
__version__ = '1.0'

import io
from pathlib import Path

from ._config import FgtConfig as FgtConfig
from ._config import FgtConfigComments as FgtConfigComments
from ._config import FgtConfigItem as FgtConfigItem
from ._config import FgtConfigNode as FgtConfigNode
from ._config import FgtConfigObject as FgtConfigObject
from ._config import FgtConfigRoot as FgtConfigRoot
from ._config import FgtConfigSet as FgtConfigSet
from ._config import FgtConfigStack as FgtConfigStack
from ._config import FgtConfigTable as FgtConfigTable
from ._config import FgtConfigTraverseCallback as FgtConfigTraverseCallback
from ._config import FgtConfigUnset as FgtConfigUnset
from ._config import qus as qus
from ._config import uqs as uqs
from ._parser import FgtConfigEosError as FgtConfigEosError
from ._parser import FgtConfigParser as FgtConfigParser
from ._parser import FgtConfigRootFactory as FgtConfigRootFactory
from ._parser import FgtConfigSyntaxError as FgtConfigSyntaxError


def set_root_config_factory(factory: FgtConfigRootFactory) -> None:
    """ Define the factory that the parser uses to create a ``FgtConfigRoot`` """
    FgtConfigParser.set_root_config_factory(factory)


def get_root_config_factor() -> FgtConfigRootFactory:
    """ Return the current ``FgtConfigRoot`` factory. """
    return FgtConfigParser.get_root_config_factory()


def parse_string(config_value: str) -> FgtConfig:
    """ Parse a FortiGate configuration string.

    :param config_value: the configuration.
    :return: a ``FgtConfig`` object.
    :raise FgtConfigSyntaxError: if a syntax error is detected.
    """
    with io.StringIO(config_value) as config_stream:
        return FgtConfigParser.parse(config_stream)


def parse_file(filename: Path | str, encoding: str = 'ascii') -> FgtConfig:
    """ Parse a FortiGate configuration file.

    :param filename: the configuration filename.
    :param encoding: default encoding.
    :return: a ``FgtConfig`` object.
    :raise FgtConfigSyntaxError: if a syntax error is detected.
    """
    with open(str(filename), encoding=encoding) as config_stream:
        return FgtConfigParser.parse(config_stream)
