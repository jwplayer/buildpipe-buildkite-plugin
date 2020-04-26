# Changelog

0.9.0 (ksindi)
--------------

* Rewrite plugin in Go
* Change license to Apache 2

0.8.0 (ksindi)
--------------

* Projects are now defined in the dynamic_pipeline.yml file and not the initial pipeline. This allow define most configuration changes in one file.
* The diff command has been split into two commands to give more flexibility on whether you are specifying the default branch or a non-default branch.

0.7.0 (ksindi)
--------------

This is a complete rewrite to a Buildkite plugin. Other changes:

The schema of the pipeline has changed.
The tag rules removed to just skipping based on labels.
Please read the README.md carefully before migrating. Also please use 0.7.4+ as the prior release has some issues with the command hook.
