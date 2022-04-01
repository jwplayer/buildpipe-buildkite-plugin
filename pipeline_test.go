package main

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"gopkg.in/yaml.v2"
)

func TestNormaliseWorkspaceStep(t *testing.T) {
	projects := []Project{
		{
			Label: "projectA",
		},
		{
			Label: "projectB",
		},
	}

	testCases := map[string]struct {
		step         string
		steps        string
		expectedStep string
	}{
		"should do nothing when there is no depends_on": {
			step: `
label: tag
branches: "master"
command:
  - make tag-release`,
			steps: `
- label: build
  branches: "master"
  env:
    BUILDPIPE_SCOPE: project
    TEST_ENV_STEP: test-step
  command:
    - cd $$BUILDPIPE_PROJECT_PATH
    - make build
    - make publish-image
  agents:
    - queue=build
  depends_on:
    - bootstrap # the rendered template should not include the project name for a non-project step
    - test # the rendered template should include the project name for a project-scoped step
- wait
- label: tag
  branches: "master"
  command:
    - make tag-release`,
			expectedStep: `
label: tag
branches: "master"
command:
  - make tag-release`,
		},
		"should update depends_on when the dependant is a project step": {
			step: `
label: tag
branches: "master"
depends_on:
  - build
command:
  - make tag-release`,
			steps: `
- label: build
  key: build
  branches: "master"
  env:
    BUILDPIPE_SCOPE: project
    TEST_ENV_STEP: test-step
  command:
    - cd $$BUILDPIPE_PROJECT_PATH
    - make build
    - make publish-image
  agents:
    - queue=build
  depends_on:
    - bootstrap # the rendered template should not include the project name for a non-project step
    - test # the rendered template should include the project name for a project-scoped step
- wait
- label: tag
  branches: "master"
  command:
    - make tag-release`,
			expectedStep: `
label: tag
branches: "master"
depends_on:
  - build:projectA
  - build:projectB
command:
  - make tag-release`,
		},
		"should not update depends_on when the dependant is a workspace step": {
			step: `
label: tag
branches: "master"
depends_on:
  - build
command:
  - make tag-release`,
			steps: `
- label: build
  key: build
  branches: "master"
  env:
    TEST_ENV_STEP: test-step
  command:
    - cd $$BUILDPIPE_PROJECT_PATH
    - make build
    - make publish-image
  agents:
    - queue=build
  depends_on:
    - bootstrap # the rendered template should not include the project name for a non-project step
    - test # the rendered template should include the project name for a project-scoped step
- wait
- label: tag
  branches: "master"
  command:
    - make tag-release`,

			expectedStep: `
label: tag
branches: "master"
depends_on:
  - build
command:
  - make tag-release`,
		},
		"should not update depends_on when couldn't find a step for the dependent key": {
			step: `
label: tag
branches: "master"
depends_on:
  - non_exist_key
command:
  - make tag-release`,
			steps: `
- label: build
  key: build
  branches: "master"
  env:
    TEST_ENV_STEP: test-step
  command:
    - cd $$BUILDPIPE_PROJECT_PATH
    - make build
    - make publish-image
  agents:
    - queue=build
  depends_on:
    - bootstrap # the rendered template should not include the project name for a non-project step
    - test # the rendered template should include the project name for a project-scoped step
- wait
- label: tag
  branches: "master"
  command:
    - make tag-release`,

			expectedStep: `
label: tag
branches: "master"
depends_on:
  - non_exist_key
command:
  - make tag-release`,
		},
	}

	for name, tc := range testCases {
		tc := tc
		t.Run(name, func(t *testing.T) {
			step := map[interface{}]interface{}{}
			assert.NoError(t, yaml.Unmarshal([]byte(tc.step), step))

			steps := []interface{}{}
			assert.NoError(t, yaml.Unmarshal([]byte(tc.steps), &steps))

			expectedStep := map[interface{}]interface{}{}
			assert.NoError(t, yaml.Unmarshal([]byte(tc.expectedStep), expectedStep))

			normaliseWorkspaceStep(step, steps, projects)
			assert.Equal(t, expectedStep, step)
		})
	}
}
