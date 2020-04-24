package main

import (
	"os"
	log "github.com/sirupsen/logrus"
)

const pluginPrefix = "BUILDKITE_PLUGIN_BUILDPIPE_"


func main() {
	projects := getProjects()
	affectedProjects := getAffectedProjects(projects)
	if len(affectedProjects) == 0 {
		log.Info("No project was affected from changes")
		os.Exit(0)
	}
	pipelineFile := os.Getenv(pluginPrefix + "DYNAMIC_PIPELINE")
	var pipeline Pipeline
	pipeline.fromFile(pipelineFile)
	dynamicPipeline := pipeline.generateDynamicPipeline(affectedProjects)
	dynamicPipeline.upload()
}
