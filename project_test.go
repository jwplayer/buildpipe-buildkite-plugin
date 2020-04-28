package main

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestCheckAffected(t *testing.T) {
	assert := assert.New(t)

	changedFiles := []string{"project1/app.py", "project2/README.md", "", "README.md"}

	p1 := Project{Label: "project1", Path: []string{"project1/"}, Skip: []string{}}
	assert.Equal(true, p1.checkAffected(changedFiles))

	p2 := Project{Label: "project2", Path: []string{"project2"}, Skip: []string{"somelabel"}}
	assert.Equal(true, p2.checkAffected(changedFiles))

	p3 := Project{Label: "project3", Path: []string{"project3/", "project2/foo/"}, Skip: []string{"project1"}}
	assert.Equal(false, p3.checkAffected(changedFiles))

	// test no changes
	assert.Equal(false, p3.checkAffected([]string{}))

}
