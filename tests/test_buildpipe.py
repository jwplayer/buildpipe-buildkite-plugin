import io
import textwrap
from unittest import mock

import pytest

from buildpipe.__main__ import (
    BuildpipeException,
    validate_dynamic_pipeline,
    yaml,
    generate_pipeline,
    get_affected_projects,
    dump_to_string,
)


PROJECTS = yaml.load(
    io.StringIO(
        """
  - label: project1
    path:
      - project1/
  - label: project2
    skip: deploy*
    path:
      - project2/
  - label: project3
    skip:
      - test
      - build
    path:
      - project3/
      - project2/
  - label: project4
    path:
      - project4/somedir/
"""
    )
)


def test_invalide_projects_config():
    config = yaml.load("""
    projects:
      - invalid: foo
    steps:
      - wait
    """)
    with pytest.raises(BuildpipeException):
        validate_dynamic_pipeline(config)


@pytest.mark.parametrize(
    "changed_files, expected",
    [
        (["project1/app.py"], {"project1"}),
        (["project1/test/foo.py"], {"project1"}),
        (["project2/foo.py"], {"project2", "project3"}),
        (["project4/foo.py"], set()),
        (["project4/somedir/foo.py"], {"project4"}),
        (["app.py"], set()),
    ],
)
@mock.patch("buildpipe.__main__.get_changed_files")
def test_get_affected_projects(mock_get_changed_files, changed_files, expected):
    mock_get_changed_files.return_value = changed_files
    projects = get_affected_projects(PROJECTS)
    assert set(p["label"] for p in projects) == expected


def test_generate_pipeline():
    step = yaml.load(
        io.StringIO(
            """
        - label: test
          env:
            BUILDPIPE_SCOPE: project
          command:
            - cd $$BUILDPIPE_PROJECT_PATH
            - make test
        - label: tag
          command: make tag
    """
        )
    )
    pipeline = generate_pipeline(step, PROJECTS)
    assert (
        dump_to_string(pipeline)
        == textwrap.dedent(
            """
    steps:
    - command:
      - cd $$BUILDPIPE_PROJECT_PATH
      - make test
      env:
        BUILDPIPE_PROJECT_LABEL: project1
        BUILDPIPE_PROJECT_PATH: project1/
        BUILDPIPE_SCOPE: project
      label: test project1
    - command:
      - cd $$BUILDPIPE_PROJECT_PATH
      - make test
      env:
        BUILDPIPE_PROJECT_LABEL: project2
        BUILDPIPE_PROJECT_PATH: project2/
        BUILDPIPE_SCOPE: project
      label: test project2
    - command:
      - cd $$BUILDPIPE_PROJECT_PATH
      - make test
      env:
        BUILDPIPE_PROJECT_LABEL: project4
        BUILDPIPE_PROJECT_PATH: project4/somedir/
        BUILDPIPE_SCOPE: project
      label: test project4
    - command: make tag
      label: tag
    """
        ).lstrip()
    )
