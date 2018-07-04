"""Dynamically generate Buildkite pipeline artifact based on git changes."""
import re
import os
import sys
import json
import fnmatch
import pathlib
import datetime
import functools
import subprocess
import collections
from typing import Dict, List, Set, Generator, Callable

import box
import yaml
import pytz
import jsonschema


BOX_CONFIG = dict(frozen_box=True, default_box=True)


class BuildpipeException(Exception):
    pass


def get_git_branch() -> str:
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


def get_deploy_branch(config: box.Box) -> str:
    return config.deploy.branch or 'master'


def get_changed_files(branch: str, deploy_branch: str) -> Set[str]:
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


def _update_dicts(source: Dict, overrides: Dict) -> Dict:
    for key, value in overrides.items():
        if isinstance(value, collections.Mapping) and value:
            returned = _update_dicts(source.get(key, {}), value)
            source[key] = returned
        else:
            source[key] = overrides[key]
    return source


def buildkite_override(step_func: Callable):
    @functools.wraps(step_func)
    def func_wrapper(stair: Dict, projects: Set[str]) -> List[Dict]:
        return [_update_dicts(step, stair.buildkite.to_dict()) for step in step_func(stair, projects)]
    return func_wrapper


def generate_wait_step() -> List[str]:
    return ['wait']


@buildkite_override
def generate_project_steps(stair: Dict, projects: Set) -> List[Dict]:
    steps = []
    for project in projects:
        step = {
            'label': f'{stair.name} {project.name} {stair.emoji or project.emoji or ""}'.strip(),
            'env': {
                'STAIR_NAME': stair.name,
                'STAIR_SCOPE': stair.scope,
                'PROJECT_NAME': project.name,
                'PROJECT_PATH': project.path,
                **(project.env or {})
            }
        }
        if stair.deploy:
            step['concurrency'] = 1
            step['concurrency_group'] = f'{stair.name}-{project.name}'
        steps.append(step)
    return steps


@buildkite_override
def generate_stair_steps(stair, projects) -> List[Dict]:
    return [{
        'label': f'{stair.name} {stair.emoji or ""}'.strip(),
        'env': {
            'STAIR_NAME': stair.name,
            'STAIR_SCOPE': stair.scope
        }
    }] if projects else []


def check_project_affected(changed_files: Set[str], project: str) -> bool:
    for path in [project.path] + list(project.get('dependencies', [])):
        for changed_file in changed_files:
            project_dirs = path.split('/')
            changed_dirs = changed_file.split('/')

            if path == '.' or changed_dirs[:len(project_dirs)] == project_dirs:
                return True
    return False


def get_affected_projects(branch: str, config: box.Box) -> Set[str]:
    deploy_branch = get_deploy_branch(config)
    changed_files = get_changed_files(branch, deploy_branch)
    changed_with_ignore = {f for f in changed_files if not any(fnmatch.fnmatch(f, i) for i in config.get('ignore', []))}
    return {p for p in config.projects if check_project_affected(changed_with_ignore, p)}


def iter_stairs(stairs, can_autodeploy: bool) -> Generator[Dict, None, None]:
    for stair in stairs:
        is_deploy = stair.deploy is True
        if not is_deploy or (is_deploy and can_autodeploy):
            yield stair


def check_autodeploy(deploy: Dict) -> bool:
    now = datetime.datetime.now(pytz.timezone(deploy.get('timezone', 'UTC')))
    check_hours = re.match(deploy.get('allowed_hours_regex', '\d|1\d|2[0-3]'), str(now.hour))
    check_days = re.match(deploy.get('allowed_weekdays_regex', '[1-7]'), str(now.isoweekday()))
    check_blacklist = not re.match(deploy.get('blacklist_dates_regex', 'dummy'), now.strftime('%Y-%m-%d'))
    return all([check_hours, check_days, check_blacklist])


def validate_config(config: box.Box) -> bool:
    schema_path = pathlib.Path(__file__).parent / 'schema.json'
    with schema_path.open() as f_schema:
        schema = json.load(f_schema)

    try:
        jsonschema.validate(json.loads(config.to_json()), schema)
    except jsonschema.exceptions.ValidationError as e:
        raise BuildpipeException("Invalid schema") from e

    valid_stair_names = set(stair.name for stair in config.stairs)
    for project in config.projects:
        for stair_name in project.skip_stairs:
            if stair_name not in valid_stair_names:
                raise BuildpipeException(f'Unrecognized stair {stair_name} for project {project.name}')  # noqa: E501
    return True


def iter_stair_projects(stair: Dict, projects: Set[str]) -> Generator[str, None, None]:
    for project in projects:
        check_skip_stair = stair.name not in project.skip_stairs
        if stair.tags:
            project_tags = project.tags or set([])
            check_tags = len(set(stair.tags) & set(project_tags)) > 0
        else:
            check_tags = True
        if check_skip_stair and check_tags:
            yield project


def compile_steps(config: box.Box) -> box.Box:
    validate_config(config)
    branch = get_git_branch()
    projects = get_affected_projects(branch, config)
    can_autodeploy = check_autodeploy(config.deploy.to_dict())
    scope_fn = dict(project=generate_project_steps, stair=generate_stair_steps)

    steps = []
    for stair in iter_stairs(config.stairs, can_autodeploy):
        stair_projects = list(iter_stair_projects(stair, projects))
        if stair_projects:
            steps += generate_wait_step()
            steps += scope_fn[stair.scope](stair, stair_projects)

    return box.Box({'steps': steps})


def create_pipeline(infile: str, outfile: str, dry_run: bool = False):
    config = box.Box.from_yaml(filename=infile, **BOX_CONFIG)
    steps = compile_steps(config)
    if not dry_run:
        steps.to_yaml(filename=outfile, Dumper=yaml.dumper.SafeDumper)
