#
# This file is part of fgtparser -  A parser for FortiGate Configuration Files
#
# Copyright (C) 2025  Jean Noel Meurisse
# SPDX-License-Identifier: GPL-3.0-only
#

""" fgtparser - A FortiGate configuration file parser """
__version__ = '1.2'

import io
from pathlib import Path
from typing import Optional

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
from .config import FgtAttrView as FgtAttrView
from .config import FgtConfigVisitor as FgtConfigVisitor
from .config import qus as qus
from .config import uqs as uqs
from .parser import FgtConfigEosError as FgtConfigEosError
from .parser import FgtConfigParser as FgtConfigParser
from .parser import FgtConfigRootFactory as FgtConfigRootFactory
from .parser import FgtConfigSyntaxError as FgtConfigSyntaxError


def loads(
    config_value: str,
    factory_fn: Optional[FgtConfigRootFactory] = None
) -> FgtConfig:
    """ Load a FortiGate configuration from a string.

    :param config_value: the configuration.
    :param factory_fn: optional factory function to override the default root factory
    :return: a ``FgtConfig`` object.
    :raise FgtConfigSyntaxError: if a syntax error is detected.
    """
    with io.StringIO(config_value) as config_stream:
        return FgtConfigParser.parse(config_stream, factory_fn)


def load(
    filename: Path | str,
    encoding: str = 'ascii',
    factory_fn: Optional[FgtConfigRootFactory] = None
) -> FgtConfig:
    """ Load a FortiGate configuration from a file.

    :param filename: the configuration filename.
    :param encoding: default encoding.
    :param factory_fn: optional factory function to override the default root factory
    :return: a ``FgtConfig`` object.
    :raise FgtConfigSyntaxError: if a syntax error is detected.
    """
    with open(str(filename), encoding=encoding) as config_stream:
        return FgtConfigParser.parse(config_stream, factory_fn)
