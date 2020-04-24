package main

import (
	"io/ioutil"
    "gopkg.in/yaml.v2"
    log "github.com/sirupsen/logrus"
)

type Pipeline struct {
	steps		[]*Step    `yaml:"steps"`
}


type Step struct {
    label       string                `yaml:"label"`
    env         map[string]string     `yaml:"env"`
    command     []string              `yaml:"command"`
}


func (p *Pipeline) fromFile(filename string) *Pipeline {
	yamlFile, err := ioutil.ReadFile(filename)
	if err != nil {
		log.Fatalf("Error reading file %s: %s\n", filename, err)
    }
    err = yaml.Unmarshal(yamlFile, p)

    if err != nil {
		log.Fatalf("Error reading file %s: %s\n", filename, err)
    }

    return p
}


func (p *Pipeline) upload() {
    outfile := "pipeline_output.yaml"
    data, err := yaml.Marshal(&p)
    if err != nil {
        log.Fatalf("Error writing outfile: %s\n", err)
    }
    err = ioutil.WriteFile(outfile, data, 0644)
    execCommand("buildkite-agent", []string{"pipeline", "upload", outfile})
}


func (p *Pipeline) generateDynamicPipeline(projects []Project) *Pipeline {
    generatedSteps := make([]*Step, 0)
    for _, step := range p.steps {
        if step.env != nil {
            if val, ok := step.env["BUILDPIPE_SCOPE"]; ok {
                if val == "project" {
                    projectSteps := generateProjectSteps(step, projects)
                    generatedSteps = append(generatedSteps, projectSteps...)
                }
            }
        } else {
            generatedSteps = append(generatedSteps, step)
        }
    }

    return &Pipeline{
        steps: generatedSteps,
    }
}


func enrichStep(project Project, step *Step) *Step {
    return &Step{
        env: step.env,
        label: step.label,
        command: step.command,
    }
}


func generateProjectSteps(step *Step, projects []Project) []*Step {
    projectSteps := make([]*Step, 0)
    for _, project := range projects {
        if project.checkStepAgainstRules(step) {
            newStep := enrichStep(project, step)
            projectSteps = append(projectSteps, newStep)
        }
    }
    return projectSteps
}
