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

from .config import FgtConfig as FgtConfig
from .config import FgtConfigComments as FgtConfigComments
from .config import FgtConfigItem as FgtConfigItem
from .config import FgtConfigNode as FgtConfigNode
from .config import FgtConfigObject as FgtConfigObject
from .config import FgtConfigRoot as FgtConfigRoot
from .config import FgtConfigSet as FgtConfigSet
from .config import FgtConfigStack as FgtConfigStack
from .config import FgtConfigTable as FgtConfigTable
from .config import FgtConfigTraverseCallback as FgtConfigTraverseCallback
from .config import FgtConfigUnset as FgtConfigUnset
from .config import FgtNodeTransition as FgtNodeTransition
from .config import qus as qus
from .config import uqs as uqs
from .parser import FgtConfigEosError as FgtConfigEosError
from .parser import FgtConfigParser as FgtConfigParser
from .parser import FgtConfigRootFactory as FgtConfigRootFactory
from .parser import FgtConfigSyntaxError as FgtConfigSyntaxError


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


def load_file(filename: Path | str, encoding: str = 'ascii') -> FgtConfig:
    """ Load a FortiGate configuration file.

    :param filename: the configuration filename.
    :param encoding: default encoding.
    :return: a ``FgtConfig`` object.
    :raise FgtConfigSyntaxError: if a syntax error is detected.
    """
    with open(str(filename), encoding=encoding) as config_stream:
        return FgtConfigParser.parse(config_stream)
