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
  while read line
  do
    assert_output --partial $line
  done << EOM
steps:
- command:
  - cd $$BUILDPIPE_PROJECT_PATH
  - make test
  env:
    BUILDPIPE_PROJECT_LABEL: project1
    BUILDPIPE_PROJECT_PATH: project1/
    BUILDPIPE_SCOPE: project
  label: test project1
- wait
- agents:
  - queue=build
  branches: master
  command:
  - cd $$BUILDPIPE_PROJECT_PATH
  - make build
  - make publish-image
  env:
    BUILDPIPE_PROJECT_LABEL: project1
    BUILDPIPE_PROJECT_PATH: project1/
    BUILDPIPE_SCOPE: project
  label: build project1
- agents:
  - queue=build
  branches: master
  command:
  - cd $$BUILDPIPE_PROJECT_PATH
  - make build
  - make publish-image
  env:
    BUILDPIPE_PROJECT_LABEL: project2
    BUILDPIPE_PROJECT_PATH: project2/
    BUILDPIPE_SCOPE: project
  label: build project2
- wait
- branches: master
  command:
  - make tag-release
  label: tag
- wait
- branches: master
  command:
  - cd $$BUILDPIPE_PROJECT_PATH
  - make deploy-staging
  concurrency: 1
  concurrency_group: deploy-stg
  env:
    BUILDPIPE_PROJECT_LABEL: project2
    BUILDPIPE_PROJECT_PATH: project2/
    BUILDPIPE_SCOPE: project
  label: deploy-stg project2
- wait
- block: ':rocket: Release!'
  branches: master
- wait
- branches: master
  command:
  - cd $$BUILDPIPE_PROJECT_PATH
  - make deploy-prod
  concurrency: 1
  concurrency_group: deploy-prd
  env:
    BUILDPIPE_PROJECT_LABEL: project2
    BUILDPIPE_PROJECT_PATH: project2/
    BUILDPIPE_SCOPE: project
  label: deploy-prd project2
EOM
}
