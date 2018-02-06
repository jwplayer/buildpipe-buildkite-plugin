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


Install
-------

.. code-block:: bash

    pip install buildpipe


Example
-------

.. code-block:: yaml

    deploy:
      branch: master
      timezone: US/Eastern
      allowed_hours_regex: '0[9]|1[0-7]'
      allowed_weekdays_regex: '[1-5]'
      blacklist_dates_regex: '\d{4}\-(01\-01|12\-31)'
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
        buildkite_override:
          agents:
            - queue=build
      - name: tag
        type: tag
        commands:
          - make tag-release
      - name: deploy-staging
        type: deploy
        commands:
          - make deploy-staging
      - name: deploy-prod
        type: deploy
        commands:
          - make deploy-prod
    projects:
      - name: jsproject
        path: jsproject
        emoji: ":javascript:"
        skip_stairs:
          - deploy-prod
      - name: pyproject
        path: py_project
        emoji: ":python:"
        dependencies:
          - jsproject


The above buildpipe config file specifies the following:

- There are two projects to track in the repo: jsProject and pyproject
- The default steps ("stairs") for each project are: test, build, tag, deploy-staging and deploy-prod
- Any git file changes that are subpaths of either project's path will trigger steps for each project
- In addition pyproject has jsproject as a dependency; any changes in jsproject will trigger steps for pyproject to be included in the pipeline
- Deploys will only happen in master branch between 9am and 5pm ET during weekdays that are not on Christmas or New Years day
- Project jsproject will never create step deploy-prod
- Stairs like build can be overridden with additional buildkite configuration such as the agent queue


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
