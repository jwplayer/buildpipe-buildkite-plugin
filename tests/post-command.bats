#!/usr/bin/env bats

load "$BATS_PATH/load.bash"

setup() {
  _GET_CHANGED_FILE='log --name-only --no-merges --pretty=format: origin..HEAD'
  stub git "${_GET_CHANGED_FILE} : echo 'project1/app.py'"
  stub buildkite-agent pipeline upload
}

teardown() {
  unstub git
  # TODO: fix not being able to unstub
  # unstub buildkite-agent
}


@test "Checks projects affected" {
  export BUILDKITE_PLUGIN_BUILDPIPE_DYNAMIC_PIPELINE="tests/dynamic_pipeline.yml"
  export BUILDKITE_PLUGIN_BUILDPIPE_LOG_LEVEL="DEBUG"
  export BUILDKITE_PLUGIN_BUILDPIPE_TEST_MODE="true"
  export BUILDKITE_BRANCH="not_master"

  run hooks/command

  assert_success
  refute_output --partial "label: deploy-stg project1"
  refute_output --partial "label: deploy-prd project1"
  refute_output --partial "label: deploy-stg project3"
  refute_output --partial "label: deploy-prd project3"
  refute_output --partial "label: test project2"
  refute_output --partial "label: test project3"
  IFS=''

  assert_output --partial << EOM
steps:
- command:
  - make bootstrap
  env:
    TEST_ENV_PIPELINE: test-pipeline
  key: bootstrap
  label: bootstrap
- command:
  - cd \$\$BUILDPIPE_PROJECT_PATH
  - make test
  env:
    BUILDPIPE_PROJECT_LABEL: project1
    BUILDPIPE_PROJECT_PATH: project1/
    BUILDPIPE_SCOPE: project
    TEST_ENV_PIPELINE: test-pipeline
    TEST_ENV_PROJECT: test-project
  key: test:project1
  label: test project1
- wait: null
- agents:
  - queue=build
  branches: master
  command:
  - cd \$\$BUILDPIPE_PROJECT_PATH
  - make build
  - make publish-image
  depends_on:
  - bootstrap
  - test:project1
  env:
    BUILDPIPE_PROJECT_LABEL: project1
    BUILDPIPE_PROJECT_PATH: project1/
    BUILDPIPE_SCOPE: project
    TEST_ENV_PIPELINE: test-pipeline
    TEST_ENV_PROJECT: test-project
    TEST_ENV_STEP: test-step
  label: build project1
- agents:
  - queue=build
  branches: master
  command:
  - cd \$\$BUILDPIPE_PROJECT_PATH
  - make build
  - make publish-image
  depends_on:
  - bootstrap
  - test:project2
  env:
    BUILDPIPE_PROJECT_LABEL: project2
    BUILDPIPE_PROJECT_PATH: project2/
    BUILDPIPE_SCOPE: project
    TEST_ENV_PIPELINE: test-pipeline
    TEST_ENV_STEP: test-step
  label: build project2
- wait
- branches: master
  command:
  - make tag-release
  env:
    TEST_ENV_PIPELINE: test-pipeline
  label: tag
- wait
- branches: master
  command:
  - cd \$\$BUILDPIPE_PROJECT_PATH
  - make deploy-staging
  concurrency: 1
  concurrency_group: deploy-stg
  env:
    BUILDPIPE_PROJECT_LABEL: project2
    BUILDPIPE_PROJECT_PATH: project2/
    BUILDPIPE_SCOPE: project
    TEST_ENV_PIPELINE: test-pipeline
  key: deploy-stg:project2
  label: deploy-stg project2
- wait
- block: ':rocket: Release!'
  branches: master
- wait
- branches: master
  command:
  - cd \$\$BUILDPIPE_PROJECT_PATH
  - make deploy-prod
  concurrency: 1
  concurrency_group: deploy-prd
  depends_on:
  - deploy-stg:project2
  env:
    BUILDPIPE_PROJECT_LABEL: project2
    BUILDPIPE_PROJECT_PATH: project2/
    BUILDPIPE_SCOPE: project
    TEST_ENV_PIPELINE: test-pipeline
  label: deploy-prd project2
EOM
}
