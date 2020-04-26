package main

import (
	"github.com/stretchr/testify/assert"
	"testing"
)

func TestConvertToSet(t *testing.T) {
	nonUniqueFiles := []string{"a", "a", "b"}
	unique := convertToSet(nonUniqueFiles)
	assert.Equal(t, []string{"a", "b"}, unique)
}
