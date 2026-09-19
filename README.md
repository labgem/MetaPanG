# MetaPanG

> [!NOTE]
> `MetaPanG` is under active development. A first release is coming soon.

`MetaPanG` is a tool for strain-level profiling of metagenomic samples against
bacterial pangenome graphs. Given sequencing reads and a collection of species
pangenomes, it detects the species present in a sample, maps the reads onto each
species pangenome, and resolves the mixture of strains together with their
relative abundances and per-strain gene content.

`MetaPanG` relies on `PanGBank`, a database of precomputed bacterial pangenomes
accessed through a web API. For each species, `PanGBank` provides the pangenome
together with the additional data structures that `MetaPanG` requires.

The files needed for a run are downloaded from `PanGBank` on demand and cached
locally, so each resource is retrieved only once and reused by later runs.

## Installation

### With `conda`

`MetaPanG` depends on `graph-tool`, which is not available on PyPI. A conda
environment file is provided at the repository root:

```
conda env create -f environment.yaml
conda activate metapang-env
```

This installs `graph-tool` from conda and the remaining dependencies, declared in
`pyproject.toml`, with pip.

> [!WARNING]
> `MetaPanG` also requires the `metagraph >= 0.5.1`. Install it from its [documentation](https://github.com/ratschlab/metagraph).
> `metagraph` is not part of the conda environment above: it currently cannot
> share an environment with `graph-tool`, because the two link incompatible
> versions of the Boost libraries. This is a temporary limitation and will be
> fixed. For now, make `metagraph` available on the `PATH` (the default is the
> `metagraph` executable), or point `MetaPanG` at it with
> `metapang profile --metagraph-path /path/to/metagraph`.

The environment can be checked with:

```
metapang checkhealth
```

### With `pixi`

Alternatively, [pixi](https://pixi.sh) installs both `graph-tool` and `metagraph`
for you, in two isolated environments wired together, so the manual `metagraph`
step above is not needed:

```
pixi install
pixi run metapang profile -q reads.fastq.gz -b GTDB_refseq@2.0.0
```

`pixi run` sets everything up on first use. Use `pixi shell` to enter the environment and call `metapang`
directly.

### With Docker

The docker image bundles all dependencies.

```
docker run --rm -t -v /path/to/data:/data -w /data \
  -v metapang-cache:/cache -e METAPANG_PANGBANK_CACHE_DIRECTORY=/cache \
  ghcr.io/labgem/metapang:latest profile -q reads.fastq.gz -b GTDB_refseq@2.0.0
```

> [!IMPORTANT]
> `MetaPanG` caches the pangenomes and databases it downloads (see
> [Cache location](#cache-location)). By default the cache is `.metapang-cache`
> relative to the working directory. Inside a container, anything written to the filesystem
> is lost when using `--rm`, so an unmounted cache is re-downloaded on every run. Set an explicit cache
> path with `METAPANG_PANGBANK_CACHE_DIRECTORY` and back it with a persistent volume
> (a named volume as above, or a host path with `-v /path/on/host:/cache`). This
> persists downloads across runs and lets several runs share a
> single cache.

An Apptainer/Singularity image can be built from the same image:

```
apptainer build metapang.sif docker://ghcr.io/labgem/metapang:latest
```

## Usage

> [!WARNING]
> Only the `GTDB_refseq@2.0.0` collection is supported at present. Other
> collections and versions are not yet compatible with `MetaPanG`.

Profile a sample against a pangenome collection:

```
metapang profile -q reads.fastq.gz -b GTDB_refseq@2.0.0
```

Several `-q` files (for example paired-end or split reads) are treated as a single
sample.

The `-b/--pangbank` argument accepts `collection[@version][:species]`. The optional
species suffix changes what is profiled:

- `GTDB_refseq@2.0.0` runs candidate species detection over the whole collection and
  profiles every species found in the sample.
- `GTDB_refseq@2.0.0:s__Klebsiella_pneumoniae` skips detection and profiles only the
  named species pangenome.

```
metapang profile -q reads.fastq.gz -b GTDB_refseq@2.0.0:s__Klebsiella_pneumoniae
```

## Configuration

`MetaPanG` uses a cascading configuration system so that stable defaults can be kept
in a file while individual runs, environments, or invocations override them without
editing that file. A parameter may be set at several levels; each level overrides the
previous one. From lowest to highest precedence:

1. **system** (`~/.config/metapang-config.*`): user-wide defaults shared by every run,
   for example the cache directory or the `PanGBank` endpoint.
2. **local** (`.metapang-config.*` in the current working directory): settings specific
   to an analysis directory, kept alongside its data.
3. **cli** (a file passed with `metapang --config <path>`): a configuration selected
   explicitly for a given run.
4. **environment** (variables of the form `METAPANG_<CMD>_<SUBCMD>_<PARAM>`): transient
   overrides, convenient in scripts, containers, or job schedulers.
5. **option** (a command-line option, `--param <value>`): a one-off override for a
   single invocation.

Configuration files may be written in TOML, JSON, or YAML. A template, or the
configuration schema, can be produced with:

```
metapang configure template            # commented template
metapang configure template --schema   # JSON schema
```

The resolved configuration, and the origin of each value, can be inspected with:

```
metapang configure show        # the effective configuration
metapang configure show -s     # the same, annotated with the source of each value
```

### Cache location

Downloaded pangenomes and indices are cached under `.metapang-cache` in the current
directory by default. The location is set by the `pangbank.cache_directory` parameter,
for example in a system configuration file:

```toml
[pangbank]
cache_directory = "/shared/metapang-cache"
```

or through the corresponding environment variable:

```
export METAPANG_PANGBANK_CACHE_DIRECTORY=/shared/metapang-cache
```

On a shared system, pointing several users at the same directory lets them share a
single cache. Downloads are file-locked, so concurrent runs may safely populate it.

## Output

Results are written to the output directory, one set of files per detected species:

| File | Content |
| --- | --- |
| `<species>.strains.tsv` | per-strain depth, relative abundance, and gene counts |
| `<species>.genes.tsv` | per-strain gene families with their reconciliation status |
| `<species>.selection.tsv` | the greedy selection trace and cross-validation errors |
| `<species>.profile.json` | the full result, including mapped-read counts and the trace |

In addition, the directory contains `report.html`, a self-contained summary of all
detected species, and `logs.txt`, the run log. Intermediate files (the query sketch,
the read mapping, and the annotated graphs) are cached so that a run can be resumed.

## License

`MetaPanG` is distributed under the CeCILL-C license; see `LICENSE`.
