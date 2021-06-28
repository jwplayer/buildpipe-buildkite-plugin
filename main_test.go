package main

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestProjectsFromBuildProjects(t *testing.T) {
	assert := assert.New(t)
	p1 := Project{Label: "project1", Path: []string{"project1/"}, Skip: []string{}}
	p2 := Project{Label: "project2", Path: []string{"project2/"}, Skip: []string{}}
	p3 := Project{Label: "project3", Path: []string{"project3/"}, Skip: []string{}}

	projects := []Project{p1, p2, p3}
	projectNames := "project1,project3"

	filteredList := projectsFromBuildProjects(projectNames, projects)

	assert.Equal(filteredList, []Project{p1, p3})
}

func TestAllProjectsFromBuildProjects(t *testing.T) {
	assert := assert.New(t)
	p1 := Project{Label: "project1", Path: []string{"project1/"}, Skip: []string{}}
	p2 := Project{Label: "project2", Path: []string{"project2/"}, Skip: []string{}}
	p3 := Project{Label: "project3", Path: []string{"project3/"}, Skip: []string{}}

	projects := []Project{p1, p2, p3}
	projectNames := "*"
	filteredList := projectsFromBuildProjects(projectNames, projects)

	assert.Equal(filteredList, []Project{p1, p2, p3})
}
