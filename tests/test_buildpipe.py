import io
import shlex
import tempfile
import pathlib
import datetime
import textwrap
from unittest import mock

import yaml
import pytest
import freezegun
from box import Box

from buildpipe import pipeline
from buildpipe.__main__ import create_parser


def box_from_yaml(s):
    return Box(yaml.load(s), **pipeline.BOX_CONFIG)


def steps_to_yaml(steps):
    return steps.to_yaml(Dumper=yaml.dumper.SafeDumper)


@pytest.mark.parametrize('source,overrides,expected', [
    ({'hello1': 1}, {'hello2': 2}, {'hello1': 1, 'hello2': 2}),
    ({'hello': 'to_override'}, {'hello': 'over'}, {'hello': 'over'}),
    ({'hello': {'value': 'to_override', 'no_change': 1}}, {'hello': {'value': 'over'}}, {'hello': {'value': 'over', 'no_change': 1}}),  # noqa
    ({'hello': {'value': 'to_override', 'no_change': 1}},  {'hello': {'value': {}}}, {'hello': {'value': {}, 'no_change': 1}}),  # noqa
    ({'hello': {'value': {}, 'no_change': 1}}, {'hello': {'value': 2}}, {'hello': {'value': 2, 'no_change': 1}}),
])
def test_update_dicts(source, overrides, expected):
    pipeline._update_dicts(source, overrides)
    assert source == expected


@pytest.mark.parametrize('changed_files, expected', [
    (['project1/README.md'], {'project1'}),
    (['project2/somedir/README.md'], {'project1', 'project2', 'project4'}),
    (['project3'], {'project3', 'project4'}),
    (['project3/somedir/README.md'], {'project1', 'project3', 'project4'}),
    (['project3/README.md'], {'project3', 'project4'}),
    (['README.md'], set()),
])
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_get_affected_projects(mock_get_changed_files, changed_files, expected):
    config = box_from_yaml(io.StringIO("""
    stairs: []
    projects:
      - name: project1
        path: project1
        dependencies:
          - project2
          - project3/somedir
      - name: project2
        path: project2
      - name: project3
        path: project3
      - name: project4
        path: project4
        dependencies:
          - project2
          - project3
    """))
    mock_get_changed_files.return_value = changed_files
    projects = pipeline.get_affected_projects('branch', config)
    assert set(p.name for p in projects) == expected


@pytest.mark.parametrize('test_dt, expected', [
    (datetime.datetime(2013, 11, 22, 8, 0, 0), False),
    (datetime.datetime(2013, 11, 22, 9, 0, 0), True),
    (datetime.datetime(2013, 11, 22, 18, 0, 0), False),
    (datetime.datetime(2013, 12, 31, 10, 0, 0), False),
    (datetime.datetime(2013, 12, 30, 10, 0, 0), True),
    (datetime.datetime(2013, 11, 22, 12, 0, 0), True),
    (datetime.datetime(2013, 11, 23, 12, 0, 0), False),  # Saturday
    (datetime.datetime(2013, 11, 24, 12, 0, 0), False),  # Sunday
])
def test_check_autodeploy(test_dt, expected):
    config = box_from_yaml(io.StringIO("""
    deploy:
      timezone: UTC
      allowed_hours_regex: '9|1[0-7]'
      allowed_weekdays_regex: '[1-5]'
      blacklist_dates_regex: '\d{4}\-(01\-01|12\-31)'
    """))
    with freezegun.freeze_time(test_dt):
        assert pipeline.check_autodeploy(config['deploy']) == expected


@mock.patch('buildpipe.pipeline.get_git_branch')
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_compile_steps(mock_get_changed_files, mock_get_git_branch):
    config = box_from_yaml("""
    deploy: {}
    stairs:
      - name: test
        scope: project
        buildkite:
          command:
            - cd $$PROJECT_PATH
            - make test
      - name: build
        scope: project
        emoji: ":docker:"
        buildkite:
          agents:
            - queue=build
          branches: master
          command:
            - cd $$PROJECT_PATH
            - make build
            - make publish-image
      - name: tag
        scope: stair
        emoji: ":github:"
        buildkite:
          branches: master
          command: make tag
      - name: deploy-staging
        scope: project
        emoji: ":shipit:"
        deploy: true
        buildkite:
          branches: master
          command:
            - cd $$PROJECT_PATH
            - make deploy-staging
      - name: deploy-prod
        scope: project
        emoji: ":shipit:"
        deploy: true
        buildkite:
          branches: master
          env:
            SOME_ENV: "true"
          command:
            - cd $$PROJECT_PATH
            - make deploy-prod
    projects:
      - name: pyproject
        path: pyproject
        emoji: ":python:"
    """)
    mock_get_changed_files.return_value = {'origin..HEAD', 'pyproject/README.md'}
    mock_get_git_branch.return_value = 'master'
    steps = pipeline.compile_steps(config)
    pipeline_yml = steps_to_yaml(steps)
    assert pipeline_yml == textwrap.dedent("""
    steps:
    - wait
    - command:
      - cd $$PROJECT_PATH
      - make test
      env:
        PROJECT_NAME: pyproject
        PROJECT_PATH: pyproject
        STAIR_NAME: test
        STAIR_SCOPE: project
      label: 'test pyproject :python:'
    - wait
    - agents:
      - queue=build
      branches: master
      command:
      - cd $$PROJECT_PATH
      - make build
      - make publish-image
      env:
        PROJECT_NAME: pyproject
        PROJECT_PATH: pyproject
        STAIR_NAME: build
        STAIR_SCOPE: project
      label: 'build pyproject :docker:'
    - wait
    - branches: master
      command: make tag
      env:
        STAIR_NAME: tag
        STAIR_SCOPE: stair
      label: 'tag :github:'
    - wait
    - branches: master
      command:
      - cd $$PROJECT_PATH
      - make deploy-staging
      concurrency: 1
      concurrency_group: deploy-staging-pyproject
      env:
        PROJECT_NAME: pyproject
        PROJECT_PATH: pyproject
        STAIR_NAME: deploy-staging
        STAIR_SCOPE: project
      label: 'deploy-staging pyproject :shipit:'
    - wait
    - branches: master
      command:
      - cd $$PROJECT_PATH
      - make deploy-prod
      concurrency: 1
      concurrency_group: deploy-prod-pyproject
      env:
        PROJECT_NAME: pyproject
        PROJECT_PATH: pyproject
        SOME_ENV: 'true'
        STAIR_NAME: deploy-prod
        STAIR_SCOPE: project
      label: 'deploy-prod pyproject :shipit:'
    """).lstrip()


@mock.patch('buildpipe.pipeline.get_git_branch')
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_skip_stairs(mock_get_changed_files, mock_get_git_branch):
    config = box_from_yaml("""
    stairs:
      - name: test
        scope: project
        buildkite:
          command:
            - make test
      - name: build
        scope: project
        buildkite:
          command:
            - make build
    projects:
      - name: myproject
        path: myproject
        emoji: ":python:"
        skip_stairs:
          - build
    """)
    mock_get_changed_files.return_value = {'origin..HEAD', 'myproject/README.md'}
    mock_get_git_branch.return_value = 'master'
    steps = pipeline.compile_steps(config)
    pipeline_yml = steps_to_yaml(steps)
    assert pipeline_yml == textwrap.dedent("""
    steps:
    - wait
    - command:
      - make test
      env:
        PROJECT_NAME: myproject
        PROJECT_PATH: myproject
        STAIR_NAME: test
        STAIR_SCOPE: project
      label: 'test myproject :python:'
    """).lstrip()


@mock.patch('buildpipe.pipeline.get_git_branch')
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_tags(mock_get_changed_files, mock_get_git_branch):
    config = box_from_yaml("""
    stairs:
      - name: test-integration
        scope: project
        tags:
          - integration
        buildkite:
          command:
            - make test-integration
    projects:
      - name: project1
        path: project1
        tags:
          - integration
      - name: project2
        path: project2
      - name: project3
        path: project3
        skip_stairs:
          - test-integration
    """)
    mock_get_changed_files.return_value = {'project1/README.md', 'project2/README.md', 'project3/README.md'}
    mock_get_git_branch.return_value = 'master'
    steps = pipeline.compile_steps(config)
    pipeline_yml = steps_to_yaml(steps)
    assert pipeline_yml == textwrap.dedent("""
    steps:
    - wait
    - command:
      - make test-integration
      env:
        PROJECT_NAME: project1
        PROJECT_PATH: project1
        STAIR_NAME: test-integration
        STAIR_SCOPE: project
      label: test-integration project1
    """).lstrip()


@freezegun.freeze_time('2013-11-22 08:00:00')
@mock.patch('buildpipe.pipeline.get_git_branch')
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_no_deploy(mock_get_changed_files, mock_get_git_branch):
    config = box_from_yaml("""
    deploy:
      branch: master
      timezone: UTC
      allowed_hours_regex: '9|1[0-7]'
    stairs:
      - name: test
        scope: project
        buildkite:
          command:
            - make test
      - name: deploy
        scope: project
        deploy: true
        buildkite:
          command:
            - make deploy
    projects:
      - name: myproject
        path: myproject
        emoji: ":python:"
    """)
    mock_get_changed_files.return_value = {'origin..HEAD', 'myproject/README.md'}
    mock_get_git_branch.return_value = 'master'
    steps = pipeline.compile_steps(config)
    pipeline_yml = steps_to_yaml(steps)
    assert pipeline_yml == textwrap.dedent("""
    steps:
    - wait
    - command:
      - make test
      env:
        PROJECT_NAME: myproject
        PROJECT_PATH: myproject
        STAIR_NAME: test
        STAIR_SCOPE: project
      label: 'test myproject :python:'
    """).lstrip()


def test_invalidate_config():
    with pytest.raises(pipeline.BuildpipeException):
        config = box_from_yaml("""
        stairs:
          - name: test
            scope: project
            command:
              - make test
        """)
        pipeline.compile_steps(config)


def test_pipeline_exception():
    with pytest.raises(pipeline.BuildpipeException):
        config = box_from_yaml("""
        deploy: {}
        stairs:
          - name: test
            scope: project
            buildkite:
              command:
                - make test
        projects:
          - name: myproject
            path: myproject
            emoji: ":python:"
            skip_stairs:
              - foo
        """)
        pipeline.compile_steps(config)


@mock.patch('buildpipe.pipeline.get_changed_files')
def test_create_pipeline(mock_get_changed_files):
    mock_get_changed_files.return_value = {'origin..HEAD', 'myproject/README.md'}
    infile = str(pathlib.Path(__file__).parent.parent / 'examples/buildpipe.yml')
    with tempfile.NamedTemporaryFile() as f_out:
        pipeline.create_pipeline(infile, f_out.name)


def test_create_parser():
    parser = create_parser()
    command = "--infile file.yml --dry-run"
    args = parser.parse_args(shlex.split(command))
    assert args.dry_run
    assert args.infile == 'file.yml'
    assert args.outfile == 'pipeline.yml'
