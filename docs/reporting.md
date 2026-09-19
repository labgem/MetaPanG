# Reporting a bug

`MetaPanG` provides a helper command that collects everything needed for a bug
report. Run it and paste its output into the issue. It gathers the `MetaPanG` and
dependency versions, your OS, installation method, and the `metapang checkhealth`
output:

```
metapang issue
```

If the problem is with `metapang profile`, pass the run output directory to also
include `run.toml`, the step status, and `logs.txt`:

```
metapang issue path/to/output_dir
```

You can write the report to a file instead of the terminal, and attach it to the
issue:

```
metapang issue path/to/output -o report.md
```

Please also add the exact command you ran and what you expected to happen.

:::{note}
`metapang issue` tries to hide sensitive information from `run.toml` and `logs.txt`, but please review the output before
posting.
:::

If `metapang` does not run at all (for example an installation problem), include the
information manually: your OS (Linux x86_64 / macOS Intel / macOS Apple Silicon),
your installation method (conda / pixi / Docker / source), and the full error
message.

Then open a new issue on [GitHub](https://github.com/LABGeM/MetaPanG/issues/new).
