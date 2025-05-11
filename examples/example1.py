# print the admin timeout configuration
from fgtparser import parse_file


def main() -> None:
    config = parse_file("example.conf")
    root = config.root

    global_section = root.c_object('system global')
    print(global_section.admintimeout)


if __name__ == '__main__':
    main()
