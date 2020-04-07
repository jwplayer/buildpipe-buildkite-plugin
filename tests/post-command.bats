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
  assert_output --partial "label: test project1"
  refute_output --partial "label: deploy-stg project1"
  refute_output --partial "label: deploy-prd project1"
  refute_output --partial "label: test project2"
  assert_output --partial "label: deploy-stg project2"
  assert_output --partial "label: deploy-prd project2"
  assert_output --partial "make tag"
  assert_output --partial "block: ':rocket: Release!'"
  assert_output --partial "wait"
}
