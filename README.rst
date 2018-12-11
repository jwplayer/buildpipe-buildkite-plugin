Buildpipe
=========

.. image:: https://travis-ci.org/ksindi/buildpipe.svg?branch=master
    :target: https://travis-ci.org/ksindi/buildpipe
    :alt: Build Status

.. image:: https://readthedocs.org/projects/buildpipe/badge/?version=latest
    :target: http://buildpipe.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. image:: https://img.shields.io/pypi/v/buildpipe.svg
    :target: https://pypi.python.org/pypi/buildpipe
    :alt: PyPI Version


Buildpipe allows you to dynamically generate your Buildkite pipelines so that you can:

- Manage continuous deployment logic such as only deploying during business hours
- Maintain monorepos by only looking at git changes in specified projects
- Specify dependencies between projects so that their steps are concurrent

Install
-------

.. code-block:: bash

    pip install buildpipe


Example
-------

Note: For a complete working example see `Buildkite Monorepo Example
<https://github.com/ksindi/buildpipe-monorepo-example>`_.


.. code-block:: yaml

    # trigger deploy steps on master during business hours
    deploy:
      branch: master
      timezone: US/Eastern
      allowed_hours_regex: '9|1[0-7]'
      allowed_weekdays_regex: '[1-5]'
      blacklist_dates:
        - '01-01'
        - '12-31'
    # ignore certain files from triggering steps with fnmatch
    ignore:
      - '*.md'
      - 'pyproject/*.ini'
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
        tags:
          - docker-only
        buildkite:
          agents:
            - queue=build
          branches: master
          command:
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
          command:
            - cd $$BUILDPIPE_PROJECT_PATH
            - make deploy-prod
    projects:
      - name: pyproject
        path: pyproject
        emoji: ":python:"
        tags:
          - docker-only
        dependencies:
          - jsproject
      - name: jsproject
        path: jsproject
        emoji: ":javascript:"
        skip:
          - deploy-staging

The above buildpipe config file specifies the following:

- There are two projects to track in the repo: jsproject and pyproject.
- A stair is a group of steps. It can have a scope of "project" or "stair". Scope "project" creates a step for each project changed while scope "stair" creates only one step.
- You can also limit a stair's scope using tag rules. For example, pyproject has tag "docker-only" and so will include the build step; but jsproject won't have that step.
- Any git file changes that are subpaths of either project's path will trigger steps for each project.
- In addition, pyproject has path jsproject as a dependency: any changes in jsproject will trigger steps for pyproject to be included in the pipeline. Note dependencies are paths and not projects.
- Stairs with "deploy: true" will only trigger in master branch between 9am and 5pm ET during weekdays that are not New Year's Eve or Day.
- Project jsproject will never create step deploy-staging.
- Files ending with .md or .ini files under pyproject will be ignore from triggering deploy steps.

In the above config, if only files under `pyproject` were touched and the merge happened during business hours, then buildpipe would create the following steps:

.. code-block:: yaml

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
        label: 'deploy-prod pyproject :shipit:'

Set up
------

In the Buildkite pipeline settings UI you just have to add the following in "Commands to run":

.. code-block:: bash

    buildpipe -i path/to/buildpipe.yml -o pipeline.yml
    buildkite-agent pipeline upload pipeline.yml


Testing
-------

.. code-block:: bash

    make test


License
-------

MIT
