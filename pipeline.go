package main

import (
	"fmt"

	"github.com/mohae/deepcopy"
)

type Pipeline struct {
	Steps []interface{} `yaml:"steps"`
}

func generateProjectSteps(step interface{}, projects []Project) []interface{} {
	projectSteps := make([]interface{}, 0)
	for _, project := range projects {
		stepCopy := deepcopy.Copy(step)
		stepCopyMap := stepCopy.(map[interface{}]interface{})

		if project.checkProjectRules(stepCopyMap) {
			stepCopyMap["label"] = fmt.Sprintf("%s %s", stepCopyMap["label"], project.Label)
			env := stepCopyMap["env"].(map[interface{}]interface{})
			env["BUILDPIPE_PROJECT_LABEL"] = project.Label
			env["BUILDPIPE_PROJECT_PATH"] = project.getMainPath()

			projectSteps = append(projectSteps, stepCopy)
		}
	}

	return projectSteps
}

func generatePipeline(steps []interface{}, projects []Project) *Pipeline {
	generatedSteps := make([]interface{}, 0)

	for _, step := range steps {
		stepMap, ok := step.(map[interface{}]interface{})
		if !ok {
			generatedSteps = append(generatedSteps, step)
			continue
		}

		env, ok := stepMap["env"].(map[interface{}]interface{})
		if !ok {
			generatedSteps = append(generatedSteps, step)
			continue
		}

		value, ok := env["BUILDPIPE_SCOPE"]
		if ok && value == "project" {
			projectSteps := generateProjectSteps(step, projects)
			generatedSteps = append(generatedSteps, projectSteps...)
		} else {
			generatedSteps = append(generatedSteps, step)
		}
	}

	return &Pipeline{
		Steps: generatedSteps,
	}
}
