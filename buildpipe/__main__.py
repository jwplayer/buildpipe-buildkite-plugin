#!/usr/bin/env python3
"""Dynamically generate Buildkite pipeline artifact based on git changes."""
import argparse
from fnmatch import fnmatch
import io
import json
import logging
import os
import pathlib
import subprocess
import sys
from typing import List, Set, Union

import jsonschema
from ruamel.yaml import YAML
from ruamel.yaml.scanner import ScannerError

from buildpipe import __version__


PLUGIN_PREFIX = "BUILDKITE_PLUGIN_BUILDPIPE_"

logging.basicConfig(format="%(levelname)s %(message)s")
logger = logging.getLogger("buildpipe")
log_level = os.getenv(f"{PLUGIN_PREFIX}LOG_LEVEL", "INFO")
logger.setLevel(log_level)

yaml = YAML(typ="safe")
yaml.default_flow_style = False
yaml.representer.ignore_aliases = lambda *data: True


def listify(arg: Union[None, str, List[str]]) -> List[str]:
    if arg is None or len(arg) == 0:
        return []
    elif isinstance(arg, str):
        return [arg]
    elif isinstance(arg, (list, tuple)):
        return list(arg)
    else:
        raise ValueError(f"Argument is neither None, string nor list. Found {arg}")


def dump_to_string(d):
    with io.StringIO() as buf:
        yaml.dump(d, buf)
        return buf.getvalue()


def get_git_branch() -> str:
    branch = os.getenv("BUILDKITE_BRANCH")
    if not branch:
        try:
            result = subprocess.run(
                "git rev-parse --abbrev-ref HEAD", stdout=subprocess.PIPE, shell=True,
            )
            branch = result.stdout.decode("utf-8").strip()
        except Exception as e:
            logger.error("Error running command: %s", e)
            sys.exit(-1)
    return branch


def get_changed_files() -> Set[str]:
    branch = get_git_branch()
    logger.debug("Current branch: %s", branch)
    deploy_branch = os.getenv(f"{PLUGIN_PREFIX}DEPLOY_BRANCH", "master")
    commit = os.getenv("BUILDKITE_COMMIT") or branch
    if branch == deploy_branch:
        command = f"git log -m -1 --name-only --pretty=format: {commit}"
    else:
        diff = os.getenv(f"{PLUGIN_PREFIX}DIFF")
        if diff:
            command = diff
        else:
            command = "git log --name-only --no-merges --pretty=format: origin..HEAD"

    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, shell=True)
        changed = result.stdout.decode("utf-8").split("\n")
    except Exception as e:
        logger.error(e)
        sys.exit(-1)

    if branch == deploy_branch:
        try:
            first_merge_break = changed.index("")
            changed = changed[:first_merge_break]
        except ValueError:
            pass

    return {line for line in changed if line}


def generate_project_steps(step: dict, projects: List[dict]) -> List[dict]:
    return [
        {
            **step,
            **{
                "label": f'{step["label"]} {project["label"]}',
                "env": {
                    "BUILDPIPE_PROJECT_LABEL": project["label"],
                    "BUILDPIPE_PROJECT_PATH": listify(project["path"])[0],
                    # Make sure step envs aren't overridden
                    **(step.get("env") or {}),
                },
            },
        }
        for project in projects
        if check_project_rules(step, project)
    ]


def check_project_affected(project: dict, changed_files: Set[str]) -> bool:
    for path in listify(project.get("path")):
        if path == ".":
            return True
        project_dirs = os.path.normpath(path).split("/")
        for changed_file in changed_files:
            changed_dirs = changed_file.split("/")
            if changed_dirs[: len(project_dirs)] == project_dirs:
                return True

    return False


def get_affected_projects(projects: List[dict]) -> List[dict]:
    changed_files = get_changed_files()
    return [
        project
        for project in projects
        if check_project_affected(project, changed_files)
    ]


def check_project_rules(step: dict, project: dict) -> bool:
    for pattern in listify(project.get("skip")):
        if fnmatch(step["label"], pattern):
            return False

    return True


def generate_pipeline(steps: List[dict], projects: List[dict]) -> dict:
    generated_steps = []
    for step in steps:
        if "env" in step and step.get("env", {}).get("BUILDPIPE_SCOPE") == "project":
            generated_steps += generate_project_steps(step, projects)
        else:
            generated_steps += [step]

    return {"steps": generated_steps}


def load_dynamic_pipeline() -> dict:
    filename = os.environ[f"{PLUGIN_PREFIX}DYNAMIC_PIPELINE"]
    try:
        with open(filename, "r") as f:
            pipeline = yaml.load(f)
    except FileNotFoundError as e:
        logger.error("Filename %s not found: %s", filename, e)
        sys.exit(-1)
    except ScannerError as e:
        logger.error("Invalid YAML in file %s: %s", filename, e)
        sys.exit(-1)
    else:
        return pipeline


def upload_pipeline(pipeline: dict):
    outfile = "pipeline_output"
    with open(outfile, "w") as f:
        yaml.dump(pipeline, f)

    try:
        subprocess.run([f"buildkite-agent pipeline upload {outfile}"], shell=True)
    except subprocess.CalledProcessError as e:
        logger.debug(e)
        sys.exit(-1)
    else:
        out = dump_to_string(pipeline)
        logger.debug("Pipeline:\n%s", out)


def validate_projects(projects: list) -> bool:
    schema_path = pathlib.Path(__file__).parent / "schema.json"
    with schema_path.open() as f_schema:
        schema = json.load(f_schema)

    try:
        jsonschema.validate(dict(projects=projects), schema)
    except jsonschema.exceptions.ValidationError as e:
        raise Exception("Invalid projects schema") from e
    else:
        return True


def create_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", "-V", action="version", version=__version__)
    return parser


def main():
    parser = create_parser()
    parser.parse_args()
    dynamic_pipeline = load_dynamic_pipeline()
    steps, projects = dynamic_pipeline["steps"], dynamic_pipeline["projects"]
    # validate_projects(projects)
    affected_projects = get_affected_projects(projects)

    if not affected_projects:
        logger.info("No project was affected from changes")
        sys.exit(0)

    generated_pipeline = generate_pipeline(steps, affected_projects)
    upload_pipeline(generated_pipeline)
