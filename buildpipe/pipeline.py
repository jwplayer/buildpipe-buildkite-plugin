"""Dynamically generate Buildkite pipeline artifact based on git changes."""
import re
import os
import sys
import json
import pathlib
import datetime
import functools
import subprocess

import box
import yaml
import pytz
import jsonschema


class PipelineException(Exception):
    pass


def get_git_branch():
    branch = os.getenv('BUILDKITE_BRANCH')
    if not branch:
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                stdout=subprocess.PIPE, check=True
            )
            branch = result.stdout.decode('utf-8').strip()
        except Exception as e:
            print(e)
            sys.exit(-1)
    return branch


def get_deploy_branch(config):
    return config.deploy.branch or 'master'


def get_changed_files(branch, deploy_branch):
    commit = os.getenv('BUILDKITE_COMMIT') or branch
    if branch == deploy_branch:
        command = ['git', 'log', '-m', '-1', '--name-only', '--pretty=format:', commit]
    else:
        command = ['git', 'whatchanged', '--name-only', '--pretty=format:', 'origin..HEAD']

    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, check=True)
        changed = result.stdout.decode('utf-8').split('\n')
    except Exception as e:
        print(e)
        sys.exit(-1)

    if branch == deploy_branch:
        try:
            first_merge_break = changed.index('')
            changed = changed[0:first_merge_break]
        except ValueError as e:
            pass

    return {line for line in changed if line}


def check_project_affected(changed_files, project):
    for changed_file in changed_files:
        if project.path == '.' or changed_file.startswith(project.path):
            return True
    for dependency in project.get('dependencies', []):
        for changed_file in changed_files:
            if changed_file.startswith(dependency):
                return True
    return False


def get_changed_projects(changed_files, projects):
    changed_projects = set()
    for project in projects:
        if check_project_affected(changed_files, project):
            changed_projects.add(project)
    return changed_projects


def buildkite_override(step_func):
    @functools.wraps(step_func)
    def func_wrapper(stair, projects):
        return [{**step, **stair.to_dict().get('buildkite_override', {})}
                for step in step_func(stair, projects)]
    return func_wrapper


def generate_wait_step():
    return ['wait']


@buildkite_override
def generate_test_steps(stair, projects):
    return [{
        'command': [
            f'cd {project.path}',
            *stair.commands
        ],
        'label': f'{stair.name} {project.name} {project.emoji}',
        'env': {
            'PROJECT_NAME': project.name
        }
    } for project in projects]


@buildkite_override
def generate_build_steps(stair, projects):
    return [{
        'command': [
            f'cd {project.path}',
            *stair.commands
        ],
        'label': f'{stair.name} {project.name} :docker:',
        'env': {
            'PROJECT_NAME': project.name
        }
    } for project in projects]


@buildkite_override
def generate_tag_steps(stair, projects):
    return [{
        'command': [
            *stair.commands,
            *[f'buildkite-agent meta-data set "project:{p.name}" "true"' for p in projects]
        ],
        'label': f'{stair.name} :github:'
    }] if projects else []


@buildkite_override
def generate_deploy_steps(stair, projects):
    return [{
        'command': [
            f'cd {project.path}',
            *stair.commands
        ],
        'label': f'{stair.name} {project.name} :shipit:',
        'concurrency': 1,
        'concurrency_group': f'{stair.name}-{project.name}',
        'env': {
            'PROJECT_NAME': project.name
        }
    } for project in projects]


def get_affected_projects(branch, config):
    deploy_branch = get_deploy_branch(config)
    changed_files = get_changed_files(branch, deploy_branch)
    changed_projects = get_changed_projects(changed_files, config.projects)
    return changed_projects


def iter_stairs(stairs, branch, deploy_branch, can_autodeploy):
    for stair in stairs:
        if any([
            stair.type == 'test',
            stair.type in {'build', 'tag'} and branch == deploy_branch,
            stair.type == 'deploy' and branch == deploy_branch and can_autodeploy,
        ]):
            yield stair


def check_autodeploy(deploy):
    now = datetime.datetime.now(pytz.timezone(deploy.get('timezone', 'UTC')))
    check_hours = re.match(deploy.get('allowed_hours_regex', '\d|1\d|2[0-3]'), str(now.hour))
    check_days = re.match(deploy.get('allowed_weekdays_regex', '[0-6]'), str(now.isoweekday()))
    if 'blacklist_dates_regex' in deploy:
        check_blacklist = not re.match(deploy['blacklist_dates_regex'], now.strftime('%Y-%m-%d'))
    else:
        check_blacklist = True
    return all([check_hours, check_days, check_blacklist])


def validate_config(config):
    schema_path = pathlib.Path(__file__).parent / 'schema.json'
    with schema_path.open() as f_schema:
        schema = json.load(f_schema)
    jsonschema.validate(json.loads(config.to_json()), schema)

    stair_names = set(stair.name for stair in config.stairs)
    for project in config.projects:
        for stair_name in project.skip_stairs:
            if stair_name not in stair_names:
                raise PipelineException(f'Unrecognized stair {stair_name} for project {project.name}')  # noqa: E501
    return True


def compile_steps(config):
    validate_config(config)
    step_fn = dict(
        test=generate_test_steps,
        build=generate_build_steps,
        tag=generate_tag_steps,
        deploy=generate_deploy_steps
    )
    branch = get_git_branch()
    deploy_branch = get_deploy_branch(config)
    projects = get_affected_projects(branch, config)
    can_autodeploy = check_autodeploy(config.deploy.to_dict())

    steps = []
    for stair in iter_stairs(config.stairs, branch, deploy_branch, can_autodeploy):
        stair_projects = [p for p in projects if stair.name not in p.skip_stairs]
        if stair_projects:
            steps += generate_wait_step()
            steps += step_fn[stair.type](stair, stair_projects)

    return steps


def box_from_io(buf):
    return box.Box(yaml.load(buf), frozen_box=True, default_box=True)


def steps_to_io(steps, buf):
    yaml.safe_dump({'steps': steps}, buf, default_flow_style=False)


def create_pipeline(infile, outfile, dry_run=False):
    with open(infile) as f_in:
        config = box_from_io(f_in)
    steps = compile_steps(config)
    if not dry_run:
        with open(outfile, 'w') as f_out:
            steps_to_io(steps, f_out)
