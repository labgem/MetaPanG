# MetaPanG

[![CI](https://github.com/LABGeM/MetaPanG/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/LABGeM/MetaPanG/actions/workflows/ci.yml)
[![Lint](https://github.com/LABGeM/MetaPanG/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/LABGeM/MetaPanG/actions/workflows/lint.yml)
[![Typecheck](https://github.com/LABGeM/MetaPanG/actions/workflows/typecheck.yml/badge.svg?branch=main)](https://github.com/LABGeM/MetaPanG/actions/workflows/typecheck.yml)
[![Version](https://img.shields.io/github/v/tag/LABGeM/MetaPanG?label=version&sort=semver)](https://github.com/LABGeM/MetaPanG/tags)
[![Container](https://img.shields.io/badge/ghcr.io-labgem%2Fmetapang-2496ED?logo=docker&logoColor=white)](https://github.com/LABGeM/MetaPanG/pkgs/container/metapang)
[![License: CeCILL-C](https://img.shields.io/badge/license-CeCILL--C-blue.svg)](https://cecill.info/licences/Licence_CeCILL-C_V1-en.html)
[![Docs](https://readthedocs.org/projects/metapang/badge/?version=latest)](https://metapang.readthedocs.io)

> [!NOTE]
> `MetaPanG` is under active development. Usage and results may change.

`MetaPanG` is a tool for strain-level profiling of metagenomic samples against
prokaryotic pangenome graphs. Given sequencing reads and a collection of species
pangenomes, it detects the species present in a sample, maps the reads onto each
species pangenome, and resolves the mixture of strains together with their
relative abundances and per-strain gene content.

`MetaPanG` relies on `PanGBank`, a database of precomputed pangenomes
accessed through a web API. For each species, `PanGBank` provides the pangenome
together with the additional data structures that `MetaPanG` requires.

The files needed for a run are downloaded from `PanGBank` on demand and cached
locally, so each resource is retrieved only once and reused by later runs.

📖 **Full documentation:** [metapang.readthedocs.io](https://metapang.readthedocs.io)
covers usage, managing pangenome data, configuration, and the output format.

## Installation

`MetaPanG` is supported on Linux x86_64, macOS x86_64/arm64. Linux arm64 is not supported at the moment.

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
pixi install --all
pixi run metapang profile -q reads.fastq.gz -b GTDB_refseq@2.0.0
```

`pixi install --all` sets up both environments. You can also use `pixi shell` to enter
the environment and call `metapang` directly.

### With Docker

The docker image bundles all dependencies.

```
docker run --rm -t -v /path/to/data:/data -w /data \
  -v metapang-cache:/cache -e METAPANG_PANGBANK_CACHE_DIRECTORY=/cache \
  ghcr.io/labgem/metapang:latest profile -q reads.fastq.gz -b GTDB_refseq@2.0.0
```

> [!IMPORTANT]
> `MetaPanG` caches the pangenomes and databases it downloads. By default the cache
> is `.metapang-cache` relative to the working directory. Inside a container, anything
> written to the filesystem is lost when using `--rm`, so an unmounted cache is
> re-downloaded on every run. Set an explicit cache path with
> `METAPANG_PANGBANK_CACHE_DIRECTORY` and back it with a persistent volume (a named
> volume as above, or a host path with `-v /path/on/host:/cache`). This persists
> downloads across runs and lets several runs share a single cache.

An Apptainer/Singularity image can be built from the same image:

```
apptainer build metapang.sif docker://ghcr.io/labgem/metapang:latest
```

## Quick start

> [!WARNING]
> Only the `GTDB_refseq@2.0.0` collection is supported at present. Other
> collections and versions are not yet compatible with `MetaPanG`.

Profile a sample against a pangenome collection:

```
metapang profile -q reads.fastq.gz -b GTDB_refseq@2.0.0
```

Several `-q` files (for example paired-end or split reads) are treated as a single
sample. The `-b/--pangbank` argument accepts `collection[@version][:species]`; adding
a species suffix skips detection and profiles only that species:

```
metapang profile -q reads.fastq.gz -b GTDB_refseq@2.0.0:s__Klebsiella_pneumoniae
```

See the [documentation](https://metapang.readthedocs.io) for the full usage guide.

## Getting help

Found a bug or need help? See [how to report a bug](https://github.com/LABGeM/MetaPanG/issues/1)
for what to include, then open an issue.

## License

`MetaPanG` is distributed under the CeCILL-C license; see `LICENSE`.
