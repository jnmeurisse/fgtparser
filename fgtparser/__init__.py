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

from .config import FgtConfig, FgtConfigRoot, FgtConfigComments
from .config import FgtConfigNode, FgtConfigObject, FgtConfigTable, FgtConfigSet, FgtConfigUnset
from .config import qus, uqs
from .config import FgtConfigItem, FgtConfigStack, FgtConfigTraverseCallback
from .parser import FgtConfigRootFactory, FgtConfigParser
from .parser import FgtConfigSyntaxError, FgtConfigEosError


def set_root_config_factory(factory: FgtConfigRootFactory) -> None:
    """ Define the factory that the parser uses to create ```FgtConfigRoot``` """
    FgtConfigParser.set_root_config_factory(factory)


def get_root_config_factor() -> FgtConfigRootFactory:
    """ Return the current ```FgtConfigRoot``` factory. """
    return FgtConfigParser.get_root_config_factory()


def parse_string(config_value: str) -> FgtConfig:
    """ Parse a FortiGate configuration string.

    :param config_value: the configuration.
    :return: a `FgtConfig` object.
    :raise FgtConfigSyntaxError: if a syntax error is detected.
    """
    with io.StringIO(config_value) as config_stream:
        return FgtConfigParser.parse(config_stream)


def parse_file(filename: Path | str) -> FgtConfig:
    """ Parse a FortiGate configuration file.

    :param filename: the configuration filename.
    :return: a `FgtConfig` object.
    :raise FgtConfigSyntaxError: if a syntax error is detected.
    """
    with io.open(str(filename), "r", encoding='ascii') as config_stream:
        return FgtConfigParser.parse(config_stream)
