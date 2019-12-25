import io
import shlex
import tempfile
import pathlib
import datetime
import textwrap
from unittest import mock

import pytest
import freezegun
from box import Box
from ruamel import yaml

from buildpipe import pipeline
from buildpipe.__main__ import create_parser


def box_from_yaml(s):
    return Box(yaml.load(s), **pipeline.BOX_CONFIG)


def steps_to_yaml(steps):
    return steps.to_yaml(Dumper=yaml.dumper.SafeDumper)


@pytest.mark.parametrize('stair_tags,project_tags,project_skip_tags,expected', [
    # No stair tags should default to true
    ([], [], [], True),
    ([], [], ['foo'], True),
    ([], ['foo'], [], True),
    # Nonsensical but should work
    ([], ['foo'], ['foo'], True),
    # Matching tags
    (['foo'], ['foo'], [], True),
    # Non-matching tags
    (['foo'], ['baz'], [], False),
    # Matching tag skips
    (['foo'], [], ['foo'], False),
    # Skips take priority
    (['foo'], ['foo'], ['foo'], False),
    # Matching tags using tag groups
    ([('foo', 'bar'), 'baz'], ['foo', 'bar'], [], True),
    # Matching skips using tag groups
    ([('foo', 'bar'), 'baz'], [], ['foo'], False),
    # Non-matching tag groups despite some matching
    ([('foo', 'bar')], ['foo'], [], False),
    ([('foo', 'bar')], ['bar'], [], False),
])
def test_check_tag_rules(stair_tags, project_tags, project_skip_tags, expected):
    assert pipeline.check_tag_rules(stair_tags, project_tags, project_skip_tags) == expected


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
    (['project1/app.py'], {'project1'}),
    (['project1/README.md'], set()),
    (['project1/test/README.md'], set()),
    (['project1/config.ini'], set()),
    (['project2/config.ini'], {'project4', 'project2', 'project1'}),
    (['project2/somedir/app.py'], {'project1', 'project2', 'project4'}),
    (['project3'], {'project3', 'project4'}),
    (['project3/somedir/app.py'], {'project1', 'project3', 'project4'}),
    (['project3/app.py'], {'project3', 'project4'}),
    (['nested/path/app.py'], {'project5'}),
    (['app.py'], set()),
])
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_get_affected_projects(mock_get_changed_files, changed_files, expected):
    config = box_from_yaml(io.StringIO("""
    ignore:
      - '*.md'
      - 'project1/*.ini'
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
      - name: project5
        path: nested/path
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
      blacklist_dates:
        - '12-31'
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
            - cd $$BUILDPIPE_PROJECT_PATH
            - make test
      - name: build
        scope: project
        emoji: ":docker:"
        buildkite:
          agents:
            - queue=build
          branches: master
          command:
            - cd $$BUILDPIPE_PROJECT_PATH
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
            - cd $$BUILDPIPE_PROJECT_PATH
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
            - cd $$BUILDPIPE_PROJECT_PATH
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
      - cd $$BUILDPIPE_PROJECT_PATH
      - make test
      env:
        BUILDPIPE_PROJECT_NAME: pyproject
        BUILDPIPE_PROJECT_PATH: pyproject
        BUILDPIPE_STAIR_NAME: test
        BUILDPIPE_STAIR_SCOPE: project
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
      - cd $$BUILDPIPE_PROJECT_PATH
      - make build
      - make publish-image
      env:
        BUILDPIPE_PROJECT_NAME: pyproject
        BUILDPIPE_PROJECT_PATH: pyproject
        BUILDPIPE_STAIR_NAME: build
        BUILDPIPE_STAIR_SCOPE: project
        PROJECT_NAME: pyproject
        PROJECT_PATH: pyproject
        STAIR_NAME: build
        STAIR_SCOPE: project
      label: 'build pyproject :docker:'
    - wait
    - branches: master
      command: make tag
      env:
        BUILDPIPE_STAIR_NAME: tag
        BUILDPIPE_STAIR_SCOPE: stair
      label: 'tag :github:'
    - wait
    - branches: master
      command:
      - cd $$BUILDPIPE_PROJECT_PATH
      - make deploy-staging
      concurrency: 1
      concurrency_group: deploy-staging-pyproject
      env:
        BUILDPIPE_PROJECT_NAME: pyproject
        BUILDPIPE_PROJECT_PATH: pyproject
        BUILDPIPE_STAIR_NAME: deploy-staging
        BUILDPIPE_STAIR_SCOPE: project
        PROJECT_NAME: pyproject
        PROJECT_PATH: pyproject
        STAIR_NAME: deploy-staging
        STAIR_SCOPE: project
      label: 'deploy-staging pyproject :shipit:'
    - wait
    - branches: master
      command:
      - cd $$BUILDPIPE_PROJECT_PATH
      - make deploy-prod
      concurrency: 1
      concurrency_group: deploy-prod-pyproject
      env:
        BUILDPIPE_PROJECT_NAME: pyproject
        BUILDPIPE_PROJECT_PATH: pyproject
        BUILDPIPE_STAIR_NAME: deploy-prod
        BUILDPIPE_STAIR_SCOPE: project
        PROJECT_NAME: pyproject
        PROJECT_PATH: pyproject
        SOME_ENV: 'true'
        STAIR_NAME: deploy-prod
        STAIR_SCOPE: project
      label: 'deploy-prod pyproject :shipit:'
    """).lstrip()


@mock.patch('buildpipe.pipeline.get_git_branch')
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_skip(mock_get_changed_files, mock_get_git_branch):
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
        skip:
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
        BUILDPIPE_PROJECT_NAME: myproject
        BUILDPIPE_PROJECT_PATH: myproject
        BUILDPIPE_STAIR_NAME: test
        BUILDPIPE_STAIR_SCOPE: project
        PROJECT_NAME: myproject
        PROJECT_PATH: myproject
        STAIR_NAME: test
        STAIR_SCOPE: project
      label: 'test myproject :python:'
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
        BUILDPIPE_PROJECT_NAME: myproject
        BUILDPIPE_PROJECT_PATH: myproject
        BUILDPIPE_STAIR_NAME: test
        BUILDPIPE_STAIR_SCOPE: project
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
        skip:
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
        BUILDPIPE_PROJECT_NAME: project1
        BUILDPIPE_PROJECT_PATH: project1
        BUILDPIPE_STAIR_NAME: test-integration
        BUILDPIPE_STAIR_SCOPE: project
        PROJECT_NAME: project1
        PROJECT_PATH: project1
        STAIR_NAME: test-integration
        STAIR_SCOPE: project
      label: test-integration project1
    """).lstrip()


@mock.patch('buildpipe.pipeline.get_git_branch')
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_tag_groups(mock_get_changed_files, mock_get_git_branch):
    config = box_from_yaml("""
    stairs:
      - name: step1
        scope: project
        tags:
          - foo
          - ["bar", "baz"]
        buildkite:
          command:
            - make step1
    projects:
      - name: project1
        path: project1
        tags:
          - bar
          - baz
      - name: project2
        path: project2
      - name: project3
        path: project3
        skip:
          - bar
    """)
    mock_get_changed_files.return_value = {'project1/README.md', 'project2/README.md', 'project3/README.md'}
    mock_get_git_branch.return_value = 'master'
    steps = pipeline.compile_steps(config)
    pipeline_yml = steps_to_yaml(steps)
    assert pipeline_yml == textwrap.dedent("""
    steps:
    - wait
    - command:
      - make step1
      env:
        BUILDPIPE_PROJECT_NAME: project1
        BUILDPIPE_PROJECT_PATH: project1
        BUILDPIPE_STAIR_NAME: step1
        BUILDPIPE_STAIR_SCOPE: project
        PROJECT_NAME: project1
        PROJECT_PATH: project1
        STAIR_NAME: step1
        STAIR_SCOPE: project
      label: step1 project1
    """).lstrip()


@mock.patch('buildpipe.pipeline.get_git_branch')
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_project_substring(mock_get_changed_files, mock_get_git_branch):
    config = box_from_yaml("""
    stairs:
      - name: test
        scope: project
        buildkite:
          command:
            - make test
    projects:
      - name: project
        path: project
      - name: project-api
        path: project-api
    """)
    mock_get_changed_files.return_value = {'project-api/README.md'}
    mock_get_git_branch.return_value = 'master'
    steps = pipeline.compile_steps(config)
    pipeline_yml = steps_to_yaml(steps)
    assert pipeline_yml == textwrap.dedent("""
    steps:
    - wait
    - command:
      - make test
      env:
        BUILDPIPE_PROJECT_NAME: project-api
        BUILDPIPE_PROJECT_PATH: project-api
        BUILDPIPE_STAIR_NAME: test
        BUILDPIPE_STAIR_SCOPE: project
        PROJECT_NAME: project-api
        PROJECT_PATH: project-api
        STAIR_NAME: test
        STAIR_SCOPE: project
      label: test project-api
    """).lstrip()


@mock.patch('buildpipe.pipeline.get_git_branch')
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_project_env(mock_get_changed_files, mock_get_git_branch):
    config = box_from_yaml("""
    stairs:
      - name: test
        scope: project
        buildkite:
          command:
            - make test
    projects:
      - name: project
        path: project
        env:
          DEPLOYMENT_TYPE: job
    """)
    mock_get_changed_files.return_value = {'project/README.md'}
    mock_get_git_branch.return_value = 'master'
    steps = pipeline.compile_steps(config)
    pipeline_yml = steps_to_yaml(steps)
    assert pipeline_yml == textwrap.dedent("""
    steps:
    - wait
    - command:
      - make test
      env:
        BUILDPIPE_PROJECT_NAME: project
        BUILDPIPE_PROJECT_PATH: project
        BUILDPIPE_STAIR_NAME: test
        BUILDPIPE_STAIR_SCOPE: project
        DEPLOYMENT_TYPE: job
        PROJECT_NAME: project
        PROJECT_PATH: project
        STAIR_NAME: test
        STAIR_SCOPE: project
      label: test project
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
        BUILDPIPE_PROJECT_NAME: myproject
        BUILDPIPE_PROJECT_PATH: myproject
        BUILDPIPE_STAIR_NAME: test
        BUILDPIPE_STAIR_SCOPE: project
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


@mock.patch('buildpipe.pipeline.get_changed_files')
def test_create_pipeline(mock_get_changed_files):
    mock_get_changed_files.return_value = {'origin..HEAD', 'myproject/README.md'}
    infile = str(pathlib.Path(__file__).parent.parent / 'examples/buildpipe.yml')
    with tempfile.NamedTemporaryFile() as f_out:
        pipeline.create_pipeline(infile, f_out.name)


@mock.patch('buildpipe.pipeline.get_git_branch')
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_block_stairs(mock_get_changed_files, mock_get_git_branch):
    config = box_from_yaml("""
    deploy:
      branch: master
    block:
      block: "Release!"
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
        block_stairs:
          - deploy
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
        BUILDPIPE_PROJECT_NAME: myproject
        BUILDPIPE_PROJECT_PATH: myproject
        BUILDPIPE_STAIR_NAME: test
        BUILDPIPE_STAIR_SCOPE: project
        PROJECT_NAME: myproject
        PROJECT_PATH: myproject
        STAIR_NAME: test
        STAIR_SCOPE: project
      label: 'test myproject :python:'
    - wait
    - block: Release!
    - command:
      - make deploy
      concurrency: 1
      concurrency_group: deploy-myproject
      env:
        BUILDPIPE_PROJECT_NAME: myproject
        BUILDPIPE_PROJECT_PATH: myproject
        BUILDPIPE_STAIR_NAME: deploy
        BUILDPIPE_STAIR_SCOPE: project
        PROJECT_NAME: myproject
        PROJECT_PATH: myproject
        STAIR_NAME: deploy
        STAIR_SCOPE: project
      label: 'deploy myproject :python:'
    """).lstrip()


@mock.patch('buildpipe.pipeline.get_git_branch')
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_wait_continue_on_failure(mock_get_changed_files, mock_get_git_branch):
    config = box_from_yaml("""
    stairs:
      - name: test
        scope: project
        continue_on_failure: true
        buildkite:
          command:
            - make test
      - name: cleanup
        scope: stair
        buildkite:
          command:
            - make cleanup
    projects:
      - name: project
        path: project
    """)
    mock_get_changed_files.return_value = {'project/README.md'}
    mock_get_git_branch.return_value = 'master'
    steps = pipeline.compile_steps(config)
    pipeline_yml = steps_to_yaml(steps)
    assert pipeline_yml == textwrap.dedent("""
    steps:
    - wait
    - command:
      - make test
      env:
        BUILDPIPE_PROJECT_NAME: project
        BUILDPIPE_PROJECT_PATH: project
        BUILDPIPE_STAIR_NAME: test
        BUILDPIPE_STAIR_SCOPE: project
        PROJECT_NAME: project
        PROJECT_PATH: project
        STAIR_NAME: test
        STAIR_SCOPE: project
      label: test project
    - continue_on_failure: true
      wait: null
    - command:
      - make cleanup
      env:
        BUILDPIPE_STAIR_NAME: cleanup
        BUILDPIPE_STAIR_SCOPE: stair
      label: cleanup
    """).lstrip()


def test_create_parser():
    parser = create_parser()
    command = "--infile file.yml --dry-run"
    args = parser.parse_args(shlex.split(command))
    assert args.dry_run
    assert args.infile == 'file.yml'
    assert args.outfile == 'pipeline.yml'
