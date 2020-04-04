#!/usr/bin/env bats

load "$BATS_PATH/load.bash"

# Uncomment to enable stub debugging
export GIT_STUB_DEBUG=/dev/tty

setup() {
  _GET_GIT_BRANCH='rev-parse --abbrev-ref HEAD'
  _GET_CHANGED_FILE='log --name-only --no-merges --pretty=format: origin..HEAD'
  stub git \
      "${_GET_GIT_BRANCH} : echo 'not_master'" \
      "${_GET_CHANGED_FILE} : echo 'project0/app.py'"
}

#teardown() {
#  unstub git
#}


@test "Checks projects affected" {
  export BUILDKITE_PLUGIN_BUILDPIPE_DYNAMIC_PIPELINE="tests/dynamic_pipeline.yml"
  export BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_0_LABEL="project0"
  export BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_0_PATH="path0"
  export BUILDKITE_PLUGIN_BUILDPIPE_LOG_LEVEL="DEBUG"

  stub git "log abc123 : echo 'foo'"
  result="$(run git log abc123)"
  [ "$result" == 'foo' ]

  run python3 "$PWD/buildpipe"

  assert_success
}
