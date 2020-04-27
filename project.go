package main

import (
	"path"
	"path/filepath"
	"reflect"
	"strings"
)

// https://github.com/go-yaml/yaml/issues/100
type StringArray []string

func (a *StringArray) UnmarshalYAML(unmarshal func(interface{}) error) error {
	var multi []string
	err := unmarshal(&multi)
	if err != nil {
		var single string
		err := unmarshal(&single)
		if err != nil {
			return err
		}
		*a = []string{single}
	} else {
		*a = multi
	}
	return nil
}

type Project struct {
	Label string
	Path  StringArray
	Skip  StringArray
}

func (p *Project) getMainPath() string {
	return p.Path[0]
}

func (p *Project) checkProjectRules(step map[interface{}]interface{}) bool {
	for _, pattern := range p.Skip {
		label := step["label"].(string)
		if matched, _ := filepath.Match(pattern, label); matched {
			return false
		}
	}
	return true
}

func (p *Project) checkAffected(changedFiles []string) bool {
	for _, filePath := range p.Path {
		if filePath == "." {
			return true
		}
		normalizedPath := path.Clean(filePath)
		projectDirs := strings.Split(normalizedPath, "/")
		for _, changedFile := range changedFiles {
			if changedFile == "" {
				continue
			}
			changedDirs := strings.Split(changedFile, "/")
			if reflect.DeepEqual(changedDirs[:len(projectDirs)], projectDirs) {
				return true
			}
		}
	}
	return false
}
