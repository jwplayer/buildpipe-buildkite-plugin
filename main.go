package main

import (
	"io/ioutil"
	"os"

	log "github.com/sirupsen/logrus"
	"gopkg.in/yaml.v2"
)

const pluginPrefix = "BUILDKITE_PLUGIN_BUILDPIPE_"

type Config struct {
	Projects []Project     `yaml:"projects"`
	Steps    []interface{} `yaml:"steps"`
	Env      map[string]string `yaml:"env"`
}

func NewConfig(filename string) *Config {
	config := Config{}

	yamlFile, err := ioutil.ReadFile(filename)
	if err != nil {
		log.Fatalf("Error reading file %s: %s\n", filename, err)
	}

	if err = yaml.Unmarshal(yamlFile, &config); err != nil {
		log.Fatalf("Error unmarshalling: %s\n", err)
	}

	return &config
}

func getAffectedProjects(projects []Project, changedFiles []string) []Project {
	affectedProjects := make([]Project, 0)
	for _, project := range projects {
		if project.checkAffected(changedFiles) {
			affectedProjects = append(affectedProjects, project)
		}
	}

	return affectedProjects
}

func main() {
	logLevel := getEnv(pluginPrefix+"LOG_LEVEL", "info")
	ll, err := log.ParseLevel(logLevel)
	if err != nil {
		ll = log.InfoLevel
	}

	log.SetLevel(ll)

	config := NewConfig(os.Getenv(pluginPrefix + "DYNAMIC_PIPELINE"))
	changedFiles := getChangedFiles()
	if len(changedFiles) == 0 {
		log.Info("No files were changed")
		os.Exit(0)
	}

	affectedProjects := getAffectedProjects(config.Projects, changedFiles)
	if len(affectedProjects) == 0 {
		log.Info("No project was affected from git changes")
		os.Exit(0)
	}

	pipeline := generatePipeline(config.Steps, config.Env, affectedProjects)

	uploadPipeline(*pipeline)
}
