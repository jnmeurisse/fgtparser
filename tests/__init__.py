from os.path import dirname
from pathlib import Path


def make_test_path(filename) -> Path:
    return Path(dirname(__file__)).joinpath("config").joinpath(filename)
