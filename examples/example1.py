# print the admin timeout configuration
from fgtparser import load


def main() -> None:
    config = load("example.conf")
    root = config.root

    global_section = root.c_object('system global')
    print(global_section.attr.admintimeout)


if __name__ == '__main__':
    main()
