# convert a fortigate configuration file to json format.
from json import dumps

from src.fgtparser import FgtConfig, FgtConfigTable, FgtConfigUnset, load, uqs


def encode_fgt_object(obj):
    if isinstance(obj, FgtConfigUnset):
        return {}
    if isinstance(obj, FgtConfig):
        return {"comments": obj.comments, "root": obj.root, "vdoms": obj.vdoms}
    if isinstance(obj, FgtConfigTable):
        return {uqs(entry[0]): entry[1] for entry in obj}
    raise TypeError(f'Cannot serialize object of {type(obj)}')


def main() -> None:
    config = load("example.conf")
    print(dumps(config, default=encode_fgt_object, indent=4))


if __name__ == '__main__':
    main()
