# Usage

:::{warning}
Only the `GTDB_refseq@2.0.0` collection is supported at present. Other
collections and versions are not yet compatible with `MetaPanG`.
:::

`MetaPanG` exposes three user-facing commands. Tha main one is `profile`. The two
`search` commands are lower-level tools that expose the matching steps `profile`
performs internally.

## Global options

A few options belong to the top-level `metapang` command rather than to a
subcommand, so they are given **before** the command name:

```
metapang [GLOBAL OPTIONS] COMMAND [COMMAND OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `-v`, `--verbosity` | `info` | Log verbosity, one of `trace`, `debug`, `info`, `warning`, `error`, `critical`. |
| `-c`, `--config` | | Path to a configuration file for this run (see [Configuration](configuration.md)). |
| `-l`, `--log-file` | | Also write the log to this file. |
| `--version` | | Show the `MetaPanG` version and exit. |
| `--help` | | Show help and exit. Works on any command, for example `metapang profile --help`. |

```
# more verbose profiling
metapang -v debug profile -q reads.fastq.gz -b GTDB_refseq@2.0.0

# use a specific configuration file
metapang -c config.toml profile -q reads.fastq.gz -b GTDB_refseq@2.0.0

# combine global options
metapang -v debug -l run.log profile -q reads.fastq.gz -b GTDB_refseq@2.0.0
```

:::{note}
Putting these after the command, for example `metapang profile -v debug ...`, is an
error: `-v`, `-c`, and `-l` are options of `metapang`, not of `profile`.
:::

`metapang profile`
: The main command. Given metagenomic reads and a pangenome collection, it detects
  the species present, maps the reads onto each species pangenome, and resolves the
  mixture of strains with their abundances and gene content. See
  [`metapang profile`](profile.md).

`metapang search bank`
: Match a query (a genome or reads) against a whole collection to find which
  genomes and pangenomes it resembles. This is the
  species-detection step, on its own. See [`metapang search bank`](search-bank.md).

`metapang search pangenome`
: Match a query against a single species pangenome de Bruijn graph to find which
  gene families it contains, using exact k-mer lookup. See
  [`metapang search pangenome`](search-pangenome.md).

:::{toctree}
:maxdepth: 1
:hidden:

profile
search-bank
search-pangenome
:::
