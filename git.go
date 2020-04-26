package main

import (
	"bytes"
	log "github.com/sirupsen/logrus"
	"os"
	"os/exec"
	"strings"
)

func dedupe(list []string) []string {
	unique := make([]string, 0)
	set := make(map[string]bool)

	for _, item := range list {
		_, ok := set[item]
		if ok == false {
			set[item] = true
			unique = append(unique, item)
		}
	}
	return unique
}

func execCommand(program string, args []string) string {
	cmd := exec.Command(program, args...)
	var out bytes.Buffer
	cmd.Stdout = &out
	if err := cmd.Run(); err != nil {
		log.Fatalf("Error running command: %s\n", err)
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
    for i, _ := range slice {
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
	out := execCommand("git", cmdArgs)
	changedFiles := strings.Split(strings.TrimSpace(out), "\n")

	if branch == defaultBranch {
		firstMergeBreak := index(changedFiles, "")
		changedFiles = changedFiles[:firstMergeBreak]
	}

	log.Debugf("changedFiles: %s", changedFiles)
	log.Debugf("len(changedFiles): %d", len(changedFiles))
	uniqueFiles := dedupe(changedFiles)
	return uniqueFiles
}
