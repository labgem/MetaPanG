# MetaPanG

:::{note}
`MetaPanG` is under active development.
:::

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

See [Installation](installation.md) for the supported setups, and
[Usage](usage.md) for a walkthrough.

:::{toctree}
:maxdepth: 2
:hidden:

installation
configuration
usage
reporting
references
:::
