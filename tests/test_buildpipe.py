import io
import shlex
import tempfile
import pathlib
import datetime
import textwrap
from unittest import mock

import pytest
import freezegun
import jsonschema

from buildpipe import pipeline
from buildpipe.__main__ import create_parser


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
    config = pipeline.box_from_io(io.StringIO("""
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
    (datetime.datetime(2013, 11, 22, 18, 0, 0), False),
    (datetime.datetime(2013, 12, 31, 10, 0, 0), False),
    (datetime.datetime(2013, 12, 30, 10, 0, 0), True),
    (datetime.datetime(2013, 11, 22, 12, 0, 0), True),
    (datetime.datetime(2013, 11, 23, 12, 0, 0), False),  # Saturday
])
def test_check_autodeploy(test_dt, expected):
    config = pipeline.box_from_io(io.StringIO("""
    deploy:
      branch: master
      timezone: UTC
      allowed_hours_regex: '0[9]|1[0-7]'
      allowed_weekdays_regex: '[1-5]'
      blacklist_dates_regex: '\d{4}\-(01\-01|12\-31)'
    """))
    with freezegun.freeze_time(test_dt):
        assert pipeline.check_autodeploy(config['deploy']) == expected


@mock.patch('buildpipe.pipeline.get_git_branch')
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_compile_steps(mock_get_changed_files, mock_get_git_branch):
    config = pipeline.box_from_io(io.StringIO("""
    deploy: {}
    stairs:
      - name: test
        type: test
        commands:
          - make test
      - name: build
        type: build
        commands:
          - make build
          - make publish-image
      - name: tag
        type: tag
        commands:
          - make tag
      - name: deploy-staging
        type: deploy
        commands:
          - make deploy-staging
      - name: deploy-prod
        type: deploy
        commands:
          - make deploy-prod
    projects:
      - name: myproject
        path: myproject
        emoji: ":snake:"
    """))
    mock_get_changed_files.return_value = {'origin..HEAD', 'myproject/README.md'}
    mock_get_git_branch.return_value = 'master'
    steps = pipeline.compile_steps(config)
    with io.StringIO() as f_out:
        pipeline.steps_to_io(steps, f_out)
        pipeline_yml = f_out.getvalue()
    assert pipeline_yml == textwrap.dedent("""
    steps:
    - wait
    - command:
      - cd myproject
      - make test
      env:
        PROJECT_NAME: myproject
      label: 'test myproject :snake:'
    - wait
    - command:
      - cd myproject
      - make build
      - make publish-image
      env:
        PROJECT_NAME: myproject
      label: 'build myproject :docker:'
    - wait
    - command:
      - make tag
      - buildkite-agent meta-data set "project:myproject" "true"
      label: 'tag :github:'
    - wait
    - command:
      - cd myproject
      - make deploy-staging
      concurrency: 1
      concurrency_group: deploy-staging-myproject
      env:
        PROJECT_NAME: myproject
      label: 'deploy-staging myproject :shipit:'
    - wait
    - command:
      - cd myproject
      - make deploy-prod
      concurrency: 1
      concurrency_group: deploy-prod-myproject
      env:
        PROJECT_NAME: myproject
      label: 'deploy-prod myproject :shipit:'
    """).lstrip()


@mock.patch('buildpipe.pipeline.get_git_branch')
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_not_deploy_branch(mock_get_changed_files, mock_get_git_branch):
    config = pipeline.box_from_io(io.StringIO("""
    stairs:
      - name: test
        type: test
        commands:
          - make test
      - name: build
        type: build
        commands:
          - make build
          - make publish-image
      - name: tag
        type: tag
        commands:
          - make tag
      - name: deploy-staging
        type: deploy
        commands:
          - make deploy-staging
      - name: deploy-prod
        type: deploy
        commands:
          - make deploy-prod
    projects:
      - name: myproject
        path: myproject
        emoji: ":snake:"
    """))
    mock_get_changed_files.return_value = {'origin..HEAD', 'myproject/README.md'}
    mock_get_git_branch.return_value = 'feature'
    steps = pipeline.compile_steps(config)
    with io.StringIO() as f_out:
        pipeline.steps_to_io(steps, f_out)
        pipeline_yml = f_out.getvalue()
    assert pipeline_yml == textwrap.dedent("""
    steps:
    - wait
    - command:
      - cd myproject
      - make test
      env:
        PROJECT_NAME: myproject
      label: 'test myproject :snake:'
    """).lstrip()


@mock.patch('buildpipe.pipeline.get_git_branch')
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_skip_stairs(mock_get_changed_files, mock_get_git_branch):
    config = pipeline.box_from_io(io.StringIO("""
    stairs:
      - name: test
        type: test
        commands:
          - make test
      - name: build
        type: build
        commands:
          - make build
          - make publish-image
    projects:
      - name: myproject
        path: myproject
        emoji: ":snake:"
        skip_stairs:
          - build
    """))
    mock_get_changed_files.return_value = {'origin..HEAD', 'myproject/README.md'}
    mock_get_git_branch.return_value = 'master'
    steps = pipeline.compile_steps(config)
    with io.StringIO() as f_out:
        pipeline.steps_to_io(steps, f_out)
        pipeline_yml = f_out.getvalue()
    assert pipeline_yml == textwrap.dedent("""
    steps:
    - wait
    - command:
      - cd myproject
      - make test
      env:
        PROJECT_NAME: myproject
      label: 'test myproject :snake:'
    """).lstrip()


@mock.patch('buildpipe.pipeline.get_git_branch')
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_buildkite_override(mock_get_changed_files, mock_get_git_branch):
    config = pipeline.box_from_io(io.StringIO("""
    stairs:
      - name: build
        type: build
        commands:
          - make build
        buildkite_override:
          agents:
            - queue=default
    projects:
      - name: myproject
        path: myproject
        emoji: ":snake:"
    """))
    mock_get_changed_files.return_value = {'origin..HEAD', 'myproject/README.md'}
    mock_get_git_branch.return_value = 'master'
    steps = pipeline.compile_steps(config)
    with io.StringIO() as f_out:
        pipeline.steps_to_io(steps, f_out)
        pipeline_yml = f_out.getvalue()
    assert pipeline_yml == textwrap.dedent("""
    steps:
    - wait
    - agents:
      - queue=default
      command:
      - cd myproject
      - make build
      env:
        PROJECT_NAME: myproject
      label: 'build myproject :docker:'
    """).lstrip()


@freezegun.freeze_time('2013-11-22 08:00:00')
@mock.patch('buildpipe.pipeline.get_git_branch')
@mock.patch('buildpipe.pipeline.get_changed_files')
def test_no_deploy(mock_get_changed_files, mock_get_git_branch):
    config = pipeline.box_from_io(io.StringIO("""
    deploy:
      branch: master
      timezone: UTC
      allowed_hours_regex: '0[9]|1[0-7]'
    stairs:
      - name: test
        type: test
        commands:
          - make test
      - name: build
        type: build
        commands:
          - make build
          - make publish-image
      - name: tag
        type: tag
        commands:
          - make tag
      - name: deploy-staging
        type: deploy
        commands:
          - make deploy-staging
      - name: deploy-prod
        type: deploy
        commands:
          - make deploy-prod
    projects:
      - name: myproject
        path: myproject
        emoji: ":snake:"
    """))
    mock_get_changed_files.return_value = {'origin..HEAD', 'myproject/README.md'}
    mock_get_git_branch.return_value = 'master'
    steps = pipeline.compile_steps(config)
    with io.StringIO() as f_out:
        pipeline.steps_to_io(steps, f_out)
        pipeline_yml = f_out.getvalue()
    assert pipeline_yml == textwrap.dedent("""
    steps:
    - wait
    - command:
      - cd myproject
      - make test
      env:
        PROJECT_NAME: myproject
      label: 'test myproject :snake:'
    - wait
    - command:
      - cd myproject
      - make build
      - make publish-image
      env:
        PROJECT_NAME: myproject
      label: 'build myproject :docker:'
    - wait
    - command:
      - make tag
      - buildkite-agent meta-data set "project:myproject" "true"
      label: 'tag :github:'
    """).lstrip()


def test_invalidate_config():
    with pytest.raises(jsonschema.exceptions.ValidationError):
        config = pipeline.box_from_io(io.StringIO("""
        stairs:
          - name: test
            type: test
            commands:
              - make test
        """))
        pipeline.compile_steps(config)


def test_pipeline_exception():
    with pytest.raises(pipeline.PipelineException):
        config = pipeline.box_from_io(io.StringIO("""
        deploy: {}
        stairs:
          - name: test
            type: test
            commands:
              - make test
        projects:
          - name: myproject
            path: myproject
            emoji: ":snake:"
            skip_stairs:
              - foo
        """))
        pipeline.compile_steps(config)


def test_create_pipeline():
    parent = pathlib.Path(__file__).parent.parent
    infile = parent / 'examples/buildpipe.yml'
    with tempfile.NamedTemporaryFile() as f_out:
        pipeline.create_pipeline(infile, f_out.name)


def test_create_parser():
    parser = create_parser()
    command = "--infile file.yml --dry-run"
    args = parser.parse_args(shlex.split(command))
    assert args.dry_run
    assert args.infile == 'file.yml'
    assert args.outfile == 'pipeline.yml'
