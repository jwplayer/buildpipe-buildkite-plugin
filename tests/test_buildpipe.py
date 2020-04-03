import io
import os
from unittest import mock

import pytest

from buildpipe.__main__ import yaml, listify, get_projects


def dump_to_string(d):
    with io.StringIO() as buf:
        yaml.dump(d, buf)
        return buf.getvalue()


@pytest.mark.parametrize('arg,expected', [
    (None, []),
    ("foo", ["foo"]),
    (["foo"], ["foo"]),
])
def test_listify(arg, expected):
    assert listify(arg) == expected


@mock.patch.dict(os.environ, {
    "BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_0_LABEL": "label0",
    "BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_0_PATH": "path0",
    "BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_LABEL": "label1",
    "BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH_0": "path10",
    "BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH_1": "path11",
    "BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_INCLUDE_0": "include10",
    "BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_INCLUDE_1": "include11",
    "BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_EXCLUDE_0": "exclude10",
})
def test_get_projects():
    assert get_projects() == [
        {
            "label": "label0",
            "path": ["path0"],
            "main_path": "path0",
            "include": [],
            "exclude": [],
        },
        {
            "label": "label1",
            "path": ["path10", "path11"],
            "main_path": "path10",
            "include": ["include10", "include11"],
            "exclude": ["exclude10"],
        },
    ]
