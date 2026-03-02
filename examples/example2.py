# write to stdout a copy of the configuration where all passwords are replaced by a *
import sys
from typing import Any

from src.fgtparser import FgtConfigItem, FgtConfigSet, FgtConfigStack, FgtNodeTransition, load


def hide_password(transition: FgtNodeTransition, item: FgtConfigItem, stack: FgtConfigStack, data: Any) -> None:
    if transition == FgtNodeTransition.ENTER_NODE:
        key = item[0]
        value = item[1]
        if key == 'password' and isinstance(value, FgtConfigSet) and value[0] == 'ENC':
            # Replace encrypted password
            value[1] = '*'


def main() -> None:
    config = load("example.conf")
    config.root.traverse('', hide_password, FgtConfigStack(), None)
    config.dump(sys.stdout, True, None, None)


if __name__ == '__main__':
    main()
