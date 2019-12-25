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
from typing import Dict, List, Tuple, Set, Generator, Callable, NoReturn, Union

import box
import pytz
import jsonschema
from ruamel import yaml

TAGS = List[Union[str, Tuple[str]]]


BOX_CONFIG = dict(frozen_box=True, default_box=True)


class BuildpipeException(Exception):
    pass


def _listify(arg: Union[None, str, List[str], Tuple[str]]) -> List[Union[str, Tuple[str]]]:
    """Return a list of strings or tuples where argument can be multiple types"""
    if arg is None or len(arg) == 0:
        return []
    elif isinstance(arg, str):
        return [arg]
    elif (isinstance(arg, list) or isinstance(arg, tuple)):
        return list(arg)
    else:
        raise ValueError(f"Argument is neither None, string nor list. Found {arg}")


def _get_block(project: box.Box) -> List[Union[str, Tuple[str]]]:
    # TODO: remove when block_steps is removed from schema
    return _listify(project.block_stairs) + _listify(project.block_steps)


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
        except ValueError:
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


def buildkite_override(step_func: Callable) -> Callable:
    @functools.wraps(step_func)
    def func_wrapper(stair: box.Box, projects: Set[box.Box]) -> List[Dict]:
        return [_update_dicts(step, stair.buildkite.to_dict()) for step in step_func(stair, projects)]
    return func_wrapper


def generate_default_wait_step() -> List[str]:
    return ['wait']


def generate_wait_step(stair: box.Box) -> List[str]:
    if stair.continue_on_failure:
        return [{'wait': None, 'continue_on_failure': True}]
    else:
        return generate_default_wait_step()


def generate_block_step(block: Dict, stair: box.Box, projects: Set[box.Box]) -> List[Dict]:
    has_block = any(stair.name in _get_block(project) for project in projects)
    return [block] if has_block else []


@buildkite_override
def generate_project_steps(stair: box.Box, projects: Set[box.Box]) -> List[Dict]:
    steps = []
    for project in projects:
        step = {
            'label': f'{stair.name} {project.name} {stair.emoji or project.emoji or ""}'.strip(),
            'env': {
                'BUILDPIPE_STAIR_NAME': stair.name,
                'BUILDPIPE_STAIR_SCOPE': stair.scope,
                'BUILDPIPE_PROJECT_NAME': project.name,
                'BUILDPIPE_PROJECT_PATH': project.path,
                # Deprecated environment variable names
                # TODO: remove when cutover to new minor version
                'STAIR_NAME': stair.name,
                'STAIR_SCOPE': stair.scope,
                'PROJECT_NAME': project.name,
                'PROJECT_PATH': project.path,
                # Add other environment variables specific to project
                **(project.env or {})
            }
        }
        if stair.deploy:
            step['concurrency'] = 1
            step['concurrency_group'] = f'{stair.name}-{project.name}'
        steps.append(step)
    return steps


@buildkite_override
def generate_stair_steps(stair: box.Box, projects: Set[box.Box]) -> List[Dict]:
    return [{
        'label': f'{stair.name} {stair.emoji or ""}'.strip(),
        'env': {
            'BUILDPIPE_STAIR_NAME': stair.name,
            'BUILDPIPE_STAIR_SCOPE': stair.scope
        }
    }] if projects else []


def check_project_affected(changed_files: Set[str], project: box.Box) -> bool:
    for path in [project.path] + list(project.get('dependencies', [])):
        for changed_file in changed_files:
            project_dirs = path.split('/')
            changed_dirs = changed_file.split('/')

            if path == '.' or changed_dirs[:len(project_dirs)] == project_dirs:
                return True
    return False


def get_affected_projects(branch: str, config: box.Box) -> Set[box.Box]:
    deploy_branch = get_deploy_branch(config)
    changed_files = get_changed_files(branch, deploy_branch)
    changed_with_ignore = {f for f in changed_files if not any(fnmatch.fnmatch(f, i) for i in config.get('ignore', []))}
    return {p for p in config.projects if check_project_affected(changed_with_ignore, p)}


def iter_stairs(stairs: List[box.Box], can_autodeploy: bool) -> Generator[box.Box, None, None]:
    for stair in stairs:
        is_deploy = stair.deploy is True
        if not is_deploy or (is_deploy and can_autodeploy):
            yield stair


def check_autodeploy(deploy: Dict) -> bool:
    now = datetime.datetime.now(pytz.timezone(deploy.get('timezone', 'UTC')))
    check_hours = re.match(deploy.get('allowed_hours_regex', '\\d|1\\d|2[0-3]'), str(now.hour))
    check_days = re.match(deploy.get('allowed_weekdays_regex', '[1-7]'), str(now.isoweekday()))
    blacklist_dates = deploy.get('blacklist_dates')
    check_dates = blacklist_dates is None or now.strftime('%m-%d') not in blacklist_dates
    return all([check_hours, check_days, check_dates])


def validate_config(config: box.Box) -> bool:
    schema_path = pathlib.Path(__file__).parent / 'schema.json'
    with schema_path.open() as f_schema:
        schema = json.load(f_schema)

    try:
        jsonschema.validate(json.loads(config.to_json()), schema)
    except jsonschema.exceptions.ValidationError as e:
        raise BuildpipeException("Invalid schema") from e

    return True


def check_tag_rules(stair_tags: TAGS, project_tags: TAGS, project_skip_tags: TAGS) -> bool:
    project_tags_set = set(_listify(project_tags))
    project_skip_tags_set = set(_listify(project_skip_tags))

    # Stairs that don't have tags allow any project
    if len(stair_tags) == 0:
        return True

    # Iterate through stair tags and check if projects having matching tags
    for stair_tag in stair_tags:
        stair_tag_set = set(list(_listify(stair_tag)))
        # Skip any steps a project wants to skip
        if len(stair_tag_set & project_skip_tags_set) > 0:
            return False
        else:
            if (stair_tag_set & project_tags_set) == stair_tag_set:
                return True

    return False


def iter_stair_projects(stair: box.Box, projects: Set[box.Box]) -> Generator[box.Box, None, None]:
    stair_tags = _listify(stair.tags)
    for project in projects:
        project_tags = _listify(project.tags)
        project_skip_tags = _listify(project.skip) + _listify(project.skip_stairs)
        check_stair_name = stair.name not in project_skip_tags
        if check_stair_name and check_tag_rules(stair_tags, project_tags, project_skip_tags):
            yield project


def compile_steps(config: box.Box) -> box.Box:
    validate_config(config)
    branch = get_git_branch()
    projects = get_affected_projects(branch, config)
    can_autodeploy = check_autodeploy(config.deploy.to_dict())
    scope_fn = dict(project=generate_project_steps, stair=generate_stair_steps)

    steps = []
    previous_stair = box.Box({'continue_on_failure': False})
    for stair in iter_stairs(config.stairs, can_autodeploy):
        stair_projects = list(iter_stair_projects(stair, projects))
        if stair_projects:
            steps += generate_wait_step(previous_stair)
            steps += generate_block_step(config.block.to_dict(), stair, stair_projects)
            steps += scope_fn[stair.scope](stair, stair_projects)
        previous_stair = stair

    return box.Box({'steps': steps})


def create_pipeline(infile: str, outfile: str, dry_run: bool = False) -> NoReturn:
    config = box.Box.from_yaml(filename=infile, **BOX_CONFIG)
    steps = compile_steps(config)
    if not dry_run:
        steps.to_yaml(filename=outfile, Dumper=yaml.dumper.SafeDumper)
