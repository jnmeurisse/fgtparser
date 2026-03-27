# write to stdout a copy of the configuration where all passwords are replaced by a *
import sys
from src.fgtparser import FgtConfigItem, FgtConfigSet, FgtConfigStack, FgtNodeTransition, load, FgtConfigVisitor


def solution1() -> None:
    class PasswordRemover(FgtConfigVisitor):
        def visit_enter(self, item: FgtConfigItem, parents: FgtConfigStack) -> bool:
            key, value = item
            if key == 'password' and isinstance(value, FgtConfigSet) and len(value) == 2 and value[0] == 'ENC':
                # Replace encrypted password
                value[1] = '*'
            return True

    config = load("example.conf")
    config.root.traverse('', PasswordRemover(), FgtConfigStack())
    config.dump(sys.stdout, True, None, None)


def solution2() -> None:
    config = load("example.conf")
    for key, value in config.root.walk(''):
        if key.endswith('/password') and isinstance(value, FgtConfigSet) and len(value) == 2 and value[0] == 'ENC':
            # Replace encrypted password
            value[1] = '?'
    config.dump(sys.stdout, True, None, None)


def main() -> None:
    solution1()
    solution2()



if __name__ == '__main__':
    main()
