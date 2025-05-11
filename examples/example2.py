# write to stdout a copy of the configuration where all passwords are replaced by a *
import sys
from typing import Any

from fgtparser import parse_file
from fgtparser import FgtConfigItem, FgtConfigStack, FgtConfigSet


def hide_password(enter: bool, item: FgtConfigItem, stack: FgtConfigStack, data: Any) -> None:
    if enter:
        key = item[0]
        value = item[1]
        if key == 'password' and isinstance(value, FgtConfigSet) and value[0] == 'ENC':
            # Replace encrypted password
            value[1] = '*'


def main() -> None:
    config = parse_file("example.conf")
    config.root.traverse('', hide_password, FgtConfigStack(), None)
    config.write(sys.stdout, True, None, None)


if __name__ == '__main__':
    main()
