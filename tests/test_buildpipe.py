import io

from buildpipe.__main__ import yaml, listify


def dump_to_string(d):
    with io.StringIO() as buf:
        yaml.dump(d, buf)
        return buf.getvalue()


def test_listify():
    assert listify("foo") == ["foo"]
