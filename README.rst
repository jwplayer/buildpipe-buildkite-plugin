Buildpipe
=========

.. image:: https://travis-ci.org/ksindi/buildpipe.svg?branch=master
    :target: https://travis-ci.org/ksindi/buildpipe
    :alt: Build Status

.. image:: https://readthedocs.org/projects/buildpipe/badge/?version=latest
    :target: http://buildpipe.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status


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

.. code-block:: yaml

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
          command:
            - cd $$PROJECT_PATH
            - make deploy-prod
    projects:
      - name: pyproject
        path: pyproject
        emoji: ":python:"
        dependencies:
          - jsproject
      - name: jsproject
        path: jsproject
        emoji: ":javascript:"
        skip_stairs:
          - deploy-staging

The above buildpipe config file specifies the following:

- There are two projects to track in the repo: jsproject and pyproject
- A stair is a group of steps; it can have a scope of "project" or "start", the former which will create a step for each project affected
- Any git file changes that are subpaths of either project's path will trigger steps for each project
- In addition, pyproject has jsproject as a dependency: any changes in jsproject will trigger steps for pyproject to be included in the pipeline
- Stairs with "deploy: true" will only happen in master branch between 9am and 5pm ET during weekdays that are not on New Year's Eve and Day
- Project jsproject will never create step deploy-staging

For example, if only files under `pyproject` were touched and the merge happened during business hours, then buildpipe would create the following steps:

.. code-block:: yaml

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
          STAIR_NAME: deploy-prod
          STAIR_SCOPE: project
        label: 'deploy-prod pyproject :shipit:'

Set Up
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
