# convert a fortigate configuration file to json format.
from json import dumps

from src.fgtparser import FgtConfig, FgtConfigTable, FgtConfigUnset, load, uqs, FgtConfigComments, \
    FgtConfigObject, FgtConfigSet


def encode_fgt_object(obj):
    if isinstance(obj, FgtConfigUnset):
        return {}
    if isinstance(obj, (FgtConfigSet, FgtConfigComments)):
        return list(obj)
    if isinstance(obj, (FgtConfigObject, FgtConfigTable)):
        return {uqs(k): v for k, v in obj.items()}
    if isinstance(obj, FgtConfig):
        return {"comments": obj.comments, "root": obj.root, "vdoms": obj.vdoms}
    raise TypeError(f'Cannot serialize object of {type(obj)}')


def main() -> None:
    config = load("example.conf")
    print(dumps(config, default=encode_fgt_object, indent=4))


if __name__ == '__main__':
    main()
