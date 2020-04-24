package main

import (
	"os"
	"testing"
	"github.com/stretchr/testify/assert"
)

func TestExtractProjectLabels(t *testing.T) {
	assert := assert.New(t)
	os.Setenv("FOO", "1")
	os.Setenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_LABEL", "A")
	os.Setenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_128371_LABEL", "C")

	labels := extractProjectLabels()
	assert.Contains(labels, "BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_LABEL")
	assert.Contains(labels, "BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_LABEL")
	assert.NotContains(labels, "FOO")

	os.Unsetenv("FOO")
	os.Unsetenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_LABEL")
	os.Unsetenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_128371_LABEL")
}


func TestExtractValues(t *testing.T) {
	os.Setenv("FOO", "1")
	os.Setenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH_A", "A")
	os.Setenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH_B", "B")
	os.Setenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH_C", "C")

	values := extractValues("1", "PATH")
	assert.Equal(t, []string{"A", "B", "C"}, values)

	os.Unsetenv("FOO")
	os.Unsetenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH_A")
	os.Unsetenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH_B")
	os.Unsetenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH_C")
}

func TestExtractProjectNumber(t *testing.T) {
	label := "BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1234_LABEL"
	result := extractProjectNumber(label)
	assert.Equal(t, "1234", result)
}


func TestGetProjectPath(t *testing.T) {
	os.Setenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH", "hey")
	os.Setenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_2_PATH_0", "there")

	initialFound := getProjectPath("1")
	useArray := getProjectPath("2")

	assert.Equal(t, "hey", initialFound)
	assert.Equal(t, "there", useArray)	

	os.Unsetenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH")
	os.Unsetenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_2_PATH_0")
}


func TestGetProjects(t *testing.T) {
	assert := assert.New(t)
	os.Setenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_LABEL", "thisisalabel")
	os.Setenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH_A", "a")
	os.Setenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH_B", "b")
	os.Setenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_SKIP_C", "c")
	os.Setenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_SKIP_D", "d")
	os.Setenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH", "/main/path")

	projects := getProjects()
	assert.Len(projects, 1)
	project := projects[0]
	assert.Equal("/main/path", project.mainPath)
	assert.Equal([]string{"a", "b", "/main/path"}, project.path)
	assert.Equal([]string{"c", "d"}, project.skip)
	assert.Equal("thisisalabel", project.label)

	os.Unsetenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_LABEL")
	os.Unsetenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH_A")
	os.Unsetenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH_B")
	os.Unsetenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_SKIP_C")
	os.Unsetenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_SKIP_D")
	os.Unsetenv("BUILDKITE_PLUGIN_BUILDPIPE_PROJECTS_1_PATH")
}
