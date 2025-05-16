# convert a fortigate configuration file to json format.
from fgtparser import uqs, parse_file, FgtConfig, FgtConfigTable, FgtConfigUnset
from json import dumps


def encode_fgt_object(obj):
    if isinstance(obj, FgtConfigUnset):
        return {}
    elif isinstance(obj, FgtConfig):
        return {"comments": obj.comments, "root": obj.root, "vdoms": obj.vdoms}
    elif isinstance(obj, FgtConfigTable):
        return {uqs(entry[0]): entry[1] for entry in obj}
    else:
        raise TypeError(f'Cannot serialize object of {type(obj)}')


def main() -> None:
    config = parse_file("example.conf")
    print(dumps(config, default=encode_fgt_object, indent=4))


if __name__ == '__main__':
    main()
