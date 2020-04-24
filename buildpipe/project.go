package main

import (
	"os"
	"path"
	"path/filepath"
	"regexp"
	"reflect"
	"strings"
	log "github.com/sirupsen/logrus"
)


type Project struct {
	label		string
	mainPath 	string
	path		[]string
	skip		[]string
}


func newProject(label, mainPath string, path, skip []string) *Project {
	return &Project{
		label:		label,
		mainPath: 	mainPath,
		path:		path,
		skip:		skip,
	}
}


func (p *Project) checkStepAgainstRules(step *Step) bool {
    for _, pattern := range p.skip {
		matched, _ := filepath.Match(pattern, step.label)
		if matched {
			return false
		}
	}
	return true
}


func (p *Project) isAffected(changedFiles []string) bool {
	for _, filePath := range p.path {
		if filePath == "." {
			return true
		}
		normalizedPath := path.Clean(filePath)
		projectDirs := strings.Split(normalizedPath, "/")
		for _, changedFile := range changedFiles {
			changedDirs := strings.Split(changedFile, "/")
			if reflect.DeepEqual(changedDirs[:len(projectDirs)], projectDirs) {
				return true
			}
		}
	}
	return false
}


func getAffectedProjects(projects []Project) []Project {
	affectedProjects := make([]Project, 0)
	changedFiles := getChangedFiles()
	for _, project := range projects {
		if project.isAffected(changedFiles) {
			affectedProjects = append(affectedProjects, project)
		}
	}

	return affectedProjects
}


func getProjectPath(projNumber string) string {
	pathEnvVar := pluginPrefix + "PROJECTS_" + projNumber + "_PATH"
	mainPath := os.Getenv(pathEnvVar)
    if mainPath == "" {
        // path is an array so choose the first path as the main one
        pathEnvVar = pathEnvVar + "_0"
        mainPath = os.Getenv(pathEnvVar)
	}
	return mainPath
}


func projectFromEnv(key, label string) *Project {
	log.Debugf("Generating new project from '%s'", key)
    projNumber := extractProjectNumber(key)
    mainPath := getProjectPath(projNumber)
    pathValues := extractValues(projNumber, "PATH")
    log.Debugf("Found path values %s", pathValues)
    skipValues := extractValues(projNumber, "SKIP")
    log.Debugf("Found skip values %s", skipValues)   
	return newProject(label, mainPath, pathValues, skipValues)
}


func extractProjectLabels() map[string]string {
	regExpPattern := pluginPrefix + "PROJECTS_[0-9]*_LABEL"
	labelRegex := regexp.MustCompile(regExpPattern)
	projectLabels := make(map[string]string)

	for _, pair := range os.Environ() {
		splitVar := strings.Split(pair, "=")
		envVar := splitVar[0]
		if labelRegex.MatchString(envVar) {
			projectLabels[envVar] = splitVar[1]
		}
	}
	
	return projectLabels
}


func extractProjectNumber(key string) string {
	prefix := pluginPrefix + "PROJECTS_"
	suffix := "_LABEL"
	replaceWith := ""
	withoutPrefix := strings.Replace(key, prefix, replaceWith, -1)
	withoutSuffix := strings.Replace(withoutPrefix, suffix, replaceWith, -1)
	return withoutSuffix 
}


func extractValues(projectNumber, option string) []string {
	regExpPattern := pluginPrefix + "PROJECTS_" + projectNumber + "_" + option
	valueRegex := regexp.MustCompile(regExpPattern)
	values := make([]string, 0)
	for _, pair := range os.Environ() {
		splitVar := strings.Split(pair, "=")
		envVar := splitVar[0]
		if valueRegex.MatchString(envVar) {
			values = append(values, splitVar[1])
		}
	}
	return values
}


func getProjects() []Project {
	projectLabels := extractProjectLabels()
	projects := make([]Project, 0)
	for key, label := range projectLabels {
		project := projectFromEnv(key, label)
		projects = append(projects, *project)
	}
	return projects
}
