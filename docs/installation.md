# Installation

`MetaPanG` is supported on Linux x86_64, macOS x86_64, and macOS arm64. Linux
arm64 (aarch64) is not supported at the moment.

## 1. With `pixi global` (recommended)

Install the `metapang` and `metagraph` commands globally with
[pixi](https://pixi.sh).

```
pixi global install -c conda-forge -c bioconda --git https://github.com/LABGeM/MetaPanG.git
pixi global install -c conda-forge -c bioconda metagraph
```

They are installed as **two separate** global environments: `graph-tool` (a
`metapang` dependency) and `metagraph` link incompatible Boost libraries and cannot
coexist in one environment. Both binaries are located at `~/.pixi/bin`, so `metapang`
finds `metagraph` automatically. Check the setup with `metapang checkhealth`.

## 2. With `Docker`

The docker image bundles all dependencies.

```
docker run --rm -t -v /path/to/data:/data -w /data \
  -v metapang-cache:/cache -e METAPANG_PANGBANK_CACHE_DIRECTORY=/cache \
  ghcr.io/labgem/metapang:latest profile reads.fastq.gz -b GTDB_refseq@2.0.0
```

:::{important}
`MetaPanG` caches the pangenomes and databases it downloads (see
[Cache location](configuration.md#cache-location)). By default the cache is
`.metapang-cache` relative to the working directory. Inside a container, anything
written to the filesystem is lost when using `--rm`, so an unmounted cache is
re-downloaded on every run. Set an explicit cache path with
`METAPANG_PANGBANK_CACHE_DIRECTORY` and back it with a persistent volume (a named
volume as above, or a host path with `-v /path/on/host:/cache`). This persists
downloads across runs and lets several runs share a single cache.
:::

An Apptainer/Singularity image can be built from the same image:

```
apptainer build metapang.sif docker://ghcr.io/labgem/metapang:latest
```

## 3. From source

Clone the repository, then set it up with `pixi` (recommended) or `conda`.

### A. With `pixi`

```
git clone https://github.com/LABGeM/MetaPanG.git
cd MetaPanG
pixi run setup
pixi run metapang profile reads.fastq.gz -b GTDB_refseq@2.0.0
```

`pixi run setup` provisions required environments. Use `pixi run metapang ...`, or
`pixi shell` to call `metapang` directly.

### B. With `conda`

`MetaPanG` depends on `graph-tool`, which is not available on PyPI. A conda
environment file is provided at the repository root:

```
git clone https://github.com/LABGeM/MetaPanG.git
cd MetaPanG
conda env create -f environment.yaml
conda activate metapang-env
```

This installs `graph-tool` from conda and the remaining dependencies, declared in
`pyproject.toml`, with pip.

:::{warning}
`MetaPanG` also requires `metagraph >= 0.5.1`. Install it from its
[documentation](https://github.com/ratschlab/metagraph). `metagraph` is not part of
the conda environment above: it currently cannot share an environment with
`graph-tool`, because the two link incompatible versions of the Boost libraries. Make
`metagraph` available on the `PATH` (the default is the `metagraph` executable), or
point `MetaPanG` at it with `metapang profile --metagraph-path /path/to/metagraph`.
:::
