"""Local pangenomes: add a user-provided ppanggolin .h5 into the cache."""

from pathlib import Path
from typing import Protocol

from metapang.core.graph import PWGraph
from metapang.core.index.dbg import (
    MetagraphBuildPipeline,
    MetagraphBuildPipelineOptions,
    MetagraphCLI,
)
from metapang.logger import mp_log
from metapang.pg.dump import pg_fam_from_h5
from metapang.utils.time import timer

DEFAULT_KMER_SIZE = 25

LOCAL_COLLECTION = "local"


class PangenomeSource(Protocol):
    """Satisfied by both PanGBank_Cache.CollectionCacheProxy and LocalCacheProxy."""

    def get_dbg(self, name: str) -> Path: ...


def local_root(cache_directory: Path) -> Path:
    """Return the directory holding all local pangenomes."""
    return cache_directory / LOCAL_COLLECTION


def local_dir(cache_directory: Path, name: str) -> Path:
    """Return the directory of a named local pangenome."""
    return local_root(cache_directory) / name


def is_built(cache_directory: Path, name: str) -> bool:
    """Return whether a local pangenome has all the files profile needs."""
    d = local_dir(cache_directory, name)
    required = (
        f"{name}.dbg",
        f"{name}.family.row_diff_brwt.annodbg",
        f"{name}.gt",
    )
    return all((d / f).exists() for f in required)


class LocalCacheProxy:
    """Cache proxy over a locally-built pangenome index."""

    def __init__(self, dbg_dir: Path):
        self._dbg_dir = dbg_dir

    def get_dbg(self, name: str) -> Path:
        """Return the directory with the local pangenome dbg, annotation and .gt."""
        return self._dbg_dir

    def has_dbg(self, name: str) -> Path:
        """Return the local pangenome directory (present once built)."""
        return self._dbg_dir


def build_local_pangenome(
    pangenome: Path,
    name: str,
    kmer_size: int,
    cache_directory: Path,
    tmp_dir: Path,
    threads: int,
    metagraph_path: str,
    force: bool = False,
) -> Path:
    """Build, or reuse from cache, the graphs profile needs for a local pangenome.

    Returns  `<cache>/local/<name>`, holding `<name>.dbg`,
    `<name>.family.row_diff_brwt.annodbg` and `<name>.gt`.
    """
    out_dir = local_dir(cache_directory, name)
    if not force and is_built(cache_directory, name):
        mp_log.info(f"Local pangenome '{name}' already built ('{out_dir}')")
        return out_dir

    out_dir.mkdir(parents=True, exist_ok=True)
    work = tmp_dir / name
    work.mkdir(parents=True, exist_ok=True)

    with timer() as t:
        mp_log.info(f"⏳ Building local index for '{name}' from '{pangenome}'")

        pwg = PWGraph(pangenome)
        pwg.save(out_dir / f"{name}.gt")

        family_fa = work / f"{name}.fa"
        pg_fam_from_h5(pangenome, family_fa, compress=False, split=False, filter="all")

        pipeline = MetagraphBuildPipeline(MetagraphCLI(metagraph_path))
        options = MetagraphBuildPipelineOptions(
            inputs=[str(family_fa)],
            annotation_inputs=[str(family_fa)],
            name=name,
            tmp_dir=str(work),
            output_dir=str(out_dir),
            kmer_size=kmer_size,
            parallel=threads,
            anno_header=True,
            annotation_type="rd_brwt",
        )
        pipeline.run(options, move_graph=True)

        built = out_dir / f"{name}.row_diff_brwt.annodbg"
        wanted = out_dir / f"{name}.family.row_diff_brwt.annodbg"
        if built.exists():
            built.replace(wanted)

    mp_log.info(f"✅ Built local index for '{name}' - {t.format()}")
    return out_dir
