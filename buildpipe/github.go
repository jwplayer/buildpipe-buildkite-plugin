package main

import (
	"bytes"
	"os"
	"os/exec"
	"strings"
	log "github.com/sirupsen/logrus"
)


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


func getChangedFiles() []string {
	branch := getGitBranch()
	log.Debugf("Current branch: %s", branch)
	branchEnvVar := pluginPrefix + "DEPLOY_BRANCH"
	deployBranch := os.Getenv(branchEnvVar)
	if deployBranch == "" {
		deployBranch = "master"
	}

	gitCommand := buildDiffCommand(branch, deployBranch)
	cmdArgs := strings.Split(gitCommand, " ")

	changedFiles := strings.Split(execCommand("git", cmdArgs), "\n")
	uniqueFiles := convertToSet(changedFiles)
	return uniqueFiles
}


func buildDiffCommand(branch, deployBranch string) string {
	command := ""
	if branch == deployBranch {
		commit := os.Getenv("BUILDKITE_COMMIT")
		if commit == "" {
			commit = branch
		}
		command = "log -m -1 --name-only --pretty=format:" + commit
	} else {
		diff := os.Getenv(pluginPrefix + "DIFF")
        if diff != "" {
			command = diff
		} else {
            command = "log --name-only --no-merges --pretty=format:origin..HEAD"
		}
	}
	return command
}


func convertToSet(list []string) []string {
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
