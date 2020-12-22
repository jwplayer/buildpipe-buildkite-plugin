package main

import (
	"fmt"
	"io/ioutil"
	"os"

	"github.com/mohae/deepcopy"
	log "github.com/sirupsen/logrus"
	"gopkg.in/yaml.v2"
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

			for envVarName, envVarValue := range project.Env {
				env[envVarName] = envVarValue
			}

			projectSteps = append(projectSteps, stepCopy)
		}
	}

	return projectSteps
}

func generatePipeline(steps []interface{}, pipelineEnv map[string]string, projects []Project) *Pipeline {
	generatedSteps := make([]interface{}, 0)

	for _, step := range steps {
		stepMap, ok := step.(map[interface{}]interface{})
		if !ok {
			generatedSteps = append(generatedSteps, step)
			continue
		}

		env, foundEnv := stepMap["env"].(map[interface{}]interface{})
		_, foundBlockStep := stepMap["block"].(string)

		if !foundBlockStep {
			if !foundEnv {
				env = make(map[interface{}]interface{})
				stepMap["env"] = env
			}

			for envVarName, envVarValue := range pipelineEnv {
				env[envVarName] = envVarValue
			}
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

func uploadPipeline(pipeline Pipeline) {
	tmpFile, err := ioutil.TempFile(os.TempDir(), "buildpipe-")
	if err != nil {
		log.Fatalf("Cannot create temporary file: %s\n", err)
	}
	defer os.Remove(tmpFile.Name())

	data, err := yaml.Marshal(&pipeline)

	fmt.Printf("Pipeline:\n%s", string(data))

	err = ioutil.WriteFile(tmpFile.Name(), data, 0644)
	if err != nil {
		log.Fatalf("Error writing outfile: %s\n", err)
	}

	execCommand("buildkite-agent", []string{"pipeline", "upload", tmpFile.Name()})
}
