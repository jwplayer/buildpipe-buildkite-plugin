# Changelog

0.10.0 (boyntoni)
-----------------

1. Add support for manually specifying build projects.

0.9.4 (TBoshoven)
-----------------

1. Fix space-separation in step keys.
2. Fix parsing when `depends_on` is a string instead of an array.

0.9.3 (boyntoni)
----------------

1. Generate unique keys for project steps, and add support for `depends_on`.


0.9.2 (mowies)
--------------
1. Add option to set pipeline and project scoped environment variables.


0.9.1 (ksindi)
--------------

1. Capture and log stderr on Buildkite pipeline upload failure.

0.9.0 (ksindi)
--------------

1. Rewrite plugin in Go
2. Change license to Apache 2

0.8.0 (ksindi)
--------------

1. Projects are now defined in the dynamic_pipeline.yml file and not the initial pipeline. This allow define most configuration changes in one file.
2. The diff command has been split into two commands to give more flexibility on whether you are specifying the default branch or a non-default branch.

0.7.0 (ksindi)
--------------

This is a complete rewrite to a Buildkite plugin. Other changes:

The schema of the pipeline has changed.
The tag rules removed to just skipping based on labels.
Please read the README.md carefully before migrating. Also please use 0.7.4+ as the prior release has some issues with the command hook.
