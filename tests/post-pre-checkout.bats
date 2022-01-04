#!/usr/bin/env bats

load '/usr/local/lib/bats/load.bash'

@test "Test the pre-checkout hook" {
  run "$PWD/hooks/pre-checkout"
  assert_success
}
