package main

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"strings"

	log "github.com/sirupsen/logrus"
)

func getEnv(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}

func dedupe(list []string) []string {
	unique := make([]string, 0)
	set := make(map[string]bool)

	for _, item := range list {
		_, ok := set[item]
		if !ok {
			set[item] = true
			unique = append(unique, item)
		}
	}
	return unique
}

func execCommand(program string, args []string) string {
	cmd := exec.Command(program, args...)
	var out bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		log.Fatalf(fmt.Sprint(err) + ": " + stderr.String())
	}
	return out.String()
}

func getGitBranch() string {
	branch := os.Getenv("BUILDKITE_BRANCH")
	if branch == "" {
		branch = execCommand("git", []string{"rev-parse", "--abbrev-ref", "HEAD"})
	}
	return strings.TrimSpace(branch)
}

func determineGitArgs(branch string, defaultBranch string) []string {
	var command string
	if branch == defaultBranch {
		commit := getEnv("BUILDKITE_COMMIT", branch)
		command = getEnv(pluginPrefix+"DIFF_DEFAULT", "log -m -1 --name-only --pretty=format: "+commit)
	} else {
		command = getEnv(pluginPrefix+"DIFF_PR", "log --name-only --no-merges --pretty=format: origin..HEAD")
	}
	log.Debugf("Running command args: %s", command)
	return strings.Split(command, " ")
}

func index(slice []string, item string) int {
	for i := range slice {
		if slice[i] == item {
			return i
		}
	}
	return -1
}

func getChangedFiles() []string {
	branch := getGitBranch()
	log.Debugf("Current branch: %s", branch)
	defaultBranch := getEnv(pluginPrefix+"DEFAULT_BRANCH", "master")

	cmdArgs := determineGitArgs(branch, defaultBranch)
	changedFiles := strings.Split(execCommand("git", cmdArgs), "\n")

	if branch == defaultBranch {
		firstMergeBreak := index(changedFiles, "")
		changedFiles = changedFiles[:firstMergeBreak]
	}

	log.Debugf("changedFiles: %s", changedFiles)
	uniqueFiles := dedupe(changedFiles)
	return uniqueFiles
}
