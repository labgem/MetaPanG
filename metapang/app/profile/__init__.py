import csv
import dataclasses
import json
import pickle
import sys
from dataclasses import dataclass, field
from pathlib import Path

import rich_click as click
from sourmash import load_one_signature
from sourmash.save_load import SaveSignaturesToLocation

from metapang.core.graph import PWGraph, PWGraphAnnotator
from metapang.core.index.dbg import (
    MetagraphCLI,
    MetagraphQueryOptions,
    ensure_metagraph,
)
from metapang.core.index.search import IndexBuilder, IndexSearch, IndexType
from metapang.core.profile.strains import (
    StrainProfile,
    StrainProfileConfig,
    profile_strains,
)
from metapang.logger import log_indent, metapang_add_log_file, mp_log
from metapang.pg import compat
from metapang.pg.api import PanGBank_Cache, parse_collection_name_version
from metapang.pg.local import (
    LOCAL_COLLECTION,
    LocalCacheProxy,
    PangenomeSource,
    is_built,
    local_dir,
)
from metapang.report.profile import write_profile_report
from metapang.utils.time import timer


def _peak_rss_str() -> str:
    import resource

    maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    b = float(maxrss if sys.platform == "darwin" else maxrss * 1024)
    unit = "B"
    for unit in ("B", "KiB", "MiB", "GiB"):  # noqa: B007
        if b < 1024:
            break
        b /= 1024
    return f"{b:.1f} {unit}"


@dataclass
class ProfileState:
    """Resumable checkpoint tracking which profiling steps have completed."""

    path: Path | None = None
    _signature_ok: bool = False
    _pan_search_ok: bool = False
    _gen_search_ok: bool = False

    _mapping_ok: dict[str, bool] = field(default_factory=dict)

    _annotation_ok: dict[str, bool] = field(default_factory=dict)
    _reads_mapped: dict[str, int] = field(default_factory=dict)
    _reads_total: dict[str, int] = field(default_factory=dict)

    def signature_ok(self) -> None:
        """Mark the query signature step as complete and persist the state."""
        self._signature_ok = True
        self.write()

    @property
    def signature(self) -> bool:
        mp_log.debug(f"Signature ok: {self._signature_ok}")
        return self._signature_ok

    def pan_search_ok(self) -> None:
        """Mark the pangenome search step as complete and persist the state."""
        self._pan_search_ok = True
        self.write()

    @property
    def pan_search(self) -> bool:
        mp_log.debug(f"Pangenome search ok: {self._pan_search_ok}")
        return self._pan_search_ok

    def gen_search_ok(self) -> None:
        """Mark the genome search step as complete and persist the state."""
        self._gen_search_ok = True
        self.write()

    @property
    def gen_search(self) -> bool:
        mp_log.debug(f"Genome search ok: {self._gen_search_ok}")
        return self._gen_search_ok

    def mapping_ok(self, candidate: str) -> None:
        """Mark read mapping for the given candidate as complete and persist the state."""
        self._mapping_ok[candidate] = True
        self.write()

    def mapping(self, candidate: str) -> bool:
        """Return whether read mapping has completed for the given candidate."""
        mp_log.debug(
            f"Mapping ok for '{candidate}': {self._mapping_ok.get(candidate, False)}"
        )
        return self._mapping_ok.get(candidate, False)

    def annotation_ok(
        self, candidate: str, reads_mapped: int = 0, reads_total: int = 0
    ) -> None:
        """Mark graph annotation as complete, record the mapped-read counts, and persist."""
        self._annotation_ok[candidate] = True
        self._reads_mapped[candidate] = reads_mapped
        self._reads_total[candidate] = reads_total
        self.write()

    def annotation(self, candidate: str) -> bool:
        """Return whether graph annotation has completed for the given candidate."""
        mp_log.debug(
            f"Annotation ok for '{candidate}': {self._annotation_ok.get(candidate, False)}"
        )
        return self._annotation_ok.get(candidate, False)

    def reads(self, candidate: str) -> tuple[int, int]:
        """Return the (mapped, total) query reads recorded during annotation."""
        return self._reads_mapped.get(candidate, 0), self._reads_total.get(candidate, 0)

    def write(self) -> None:
        """Persist the current state to its pickle file."""
        assert self.path is not None
        with open(self.path, "wb") as sf:
            pickle.dump(self, sf)

    @classmethod
    def load(cls, filepath: Path) -> "ProfileState":
        """Load state from the given file, or create a fresh state if none exists."""
        if filepath.exists():
            mp_log.info(f"Resuming from previous run, loading state from '{filepath}'")
            with open(filepath, "rb") as sf:
                return pickle.load(sf)
        else:
            mp_log.info(f"Creating new state file at '{filepath}'")
            obj = cls()
            obj.path = filepath
            obj.write()
            return obj


def phase1(
    state: ProfileState,
    cache: PanGBank_Cache.CollectionCacheProxy,
    output_directory: Path,
    query: list[Path],
    sample_name: str,
    threads: int,
    gtime,
    discarded: dict[str, str],
):
    """Compute the query signature and gather candidate species from the genome index.

    Species in `discarded` are excluded from the gather so they never claim k-mers.
    """

    mp_log.info("Detecting candidate species")

    if not (bank_index := cache.has_index()):
        mp_log.debug("Bank index not cached; downloading")
        bank_index = cache.get_index()
    mp_log.debug(f"Bank index: '{bank_index}'")

    search = IndexSearch(bank_index, to_load=IndexType.genome)

    def compute_query_signature():
        with timer() as signature_time:
            signature_file = output_directory / f"{sample_name}.sig"

            if state.signature and signature_file.exists():
                signature = load_one_signature(str(signature_file))
                mp_log.info(
                    f"Reusing cached query signature for '{sample_name}' ('{signature_file}')"
                )
            else:
                mp_log.info(f"⏳ Computing query signature for '{sample_name}'")
                mp_log.debug(
                    f"  k={search.info.kmer_size}, scaled={search.info.scaled}, "
                    f"from {len(query)} file(s)"
                )
                signature = IndexBuilder.file_batch_signature(
                    query,
                    search.info.kmer_size,
                    search.info.scaled,
                    search.info.n,
                    True,
                    threads,
                    threads * 10,
                    10_000,
                )

                with SaveSignaturesToLocation(str(signature_file)) as ssl:
                    ssl.add(signature)

                state.signature_ok()
                mp_log.debug(f"  {len(signature.minhash)} hashes")

        mp_log.info(
            f"✅ Query signature for '{sample_name}' - "
            f"step: {signature_time.format()}, total: {gtime.format()}"
        )
        return signature

    with log_indent():
        signature = compute_query_signature()

    def gather_candidates():
        with timer() as gather_time:
            gather_file = output_directory / f"{sample_name}_gather.pkl"
            if state.gen_search and gather_file.exists():
                with open(gather_file, "rb") as gf:
                    gather_results = pickle.load(gf)
                mp_log.info(f"Reusing cached gather results ('{gather_file}')")
            else:
                mp_log.info("⏳ Searching genome index")
                gather_results = search.gather_signature(
                    signature,
                    IndexType.genome,
                    threshold=0.05,
                    exclude=(
                        (lambda name: name.split("@")[0] in discarded)
                        if discarded
                        else None
                    ),
                )
                with open(gather_file, "wb") as gf:
                    pickle.dump(gather_results, gf)
                state.gen_search_ok()
        mp_log.info(
            f"✅ Searching genome index - "
            f"step: {gather_time.format()}, total: {gtime.format()}"
        )
        mp_log.debug(f"Gather matched {len(gather_results)} genome(s)")
        for name, f_query, f_match in gather_results:
            mp_log.trace(f"  gather: {name}  f_query={f_query}  f_match={f_match}")
        return gather_results

    with log_indent():
        gather_results = gather_candidates()

    candidates: list[str] = []
    seen: set[str] = set()
    for name, _f_query, _f_match in gather_results:
        species = name.split("@")[0]
        if species not in seen:
            seen.add(species)
            candidates.append(species)
            mp_log.trace(f"  candidate species '{species}' (from genome '{name}')")

    if candidates:
        mp_log.info(f"{len(candidates)} candidate species: {', '.join(candidates)}")
    else:
        mp_log.warning("No candidate species passed the gather threshold")
    return candidates


def phase2_mapping(
    state: ProfileState,
    candidate: str,
    cache: PangenomeSource,
    output: Path,
    query: list[Path],
    threads: int,
    metagraph_path: str,
    gtime,
):
    """Map the query reads to the candidate's de Bruijn graph via metagraph."""

    anno_output_directory = output / "annotations"
    anno_output_directory.mkdir(parents=True, exist_ok=True)

    dbg_directory = cache.get_dbg(candidate)
    dbg_file = dbg_directory / f"{candidate}.dbg"
    dbg_family_anno = dbg_directory / f"{candidate}.family.row_diff_brwt.annodbg"

    output_file_family_anno = anno_output_directory / f"{candidate}_family_map.tsv"
    output_file_genome_anno = anno_output_directory / f"{candidate}_genome_map.tsv"
    mp_log.debug(f"DBG directory for '{candidate}': '{dbg_directory}'")
    mp_log.trace(f"  dbg='{dbg_file}' family_anno='{dbg_family_anno}'")

    with timer() as mapping_time:
        if state.mapping(candidate) and output_file_family_anno.exists():
            mp_log.info(
                f"Reusing cached read mapping for '{candidate}' ('{output_file_family_anno}')"
            )
        else:
            metagraph = MetagraphCLI(metagraph_path)
            metagraph_version = metagraph.version()
            mp_log.debug(f"metagraph version: {metagraph_version}")
            query_opt = MetagraphQueryOptions(
                i=dbg_file,
                a=dbg_family_anno,
                query_file=query,
                output_file=output_file_family_anno,
                parallel=threads,
                query_mode="matches",
                min_kmers_fraction_label=0.15,
            )
            mp_log.info(f"⏳ Mapping reads to DBG for '{candidate}'")
            mp_log.trace(
                f"  metagraph query: parallel={threads}, query_mode=matches, "
                f"min_kmers_fraction_label=0.15"
            )
            metagraph.query(query_opt)
            state.mapping_ok(candidate)
    mp_log.info(
        f"✅ Mapping reads to DBG for '{candidate}' - step: {mapping_time.format()}, total: {gtime.format()}"
    )

    return output_file_family_anno, output_file_genome_anno


def log_strain_profile(candidate: str, profile: StrainProfile) -> None:
    """Log a per-strain summary (abundance, relative abundance, gene counts) for a candidate."""
    if not profile.components:
        mp_log.info("no strains detected")
        return
    for comp in sorted(profile.components, key=lambda c: c.ra, reverse=True):
        anchor = comp.anchor_refs[0] if comp.anchor_refs else f"comp{comp.component_id}"
        if len(comp.anchor_refs) > 1:
            anchor = f"{anchor} (+{len(comp.anchor_refs) - 1})"
        st = comp.family_status or {}
        n_obs = sum(1 for v in st.values() if v == "observed")
        n_re = sum(1 for v in st.values() if v == "reassigned")
        n_imp = sum(1 for v in st.values() if v == "imputed")
        mp_log.info(
            f"{anchor:<32} RA={comp.ra * 100:6.2f}%  depth={comp.abundance:.3f}  "
            f"genes={len(comp.family_ids)} (obs {n_obs} / reasg {n_re} / imp {n_imp})"
        )


def write_run_manifest(out_dir: Path, info: dict) -> Path:
    """Write run.toml recording the MetaPanG version and the options used for the run."""
    from datetime import datetime

    import msgspec

    from metapang import __commit__ as metapang_commit
    from metapang import __version__ as metapang_version

    payload = {
        "metapang_version": metapang_version,
        "metapang_commit": metapang_commit,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **info,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    path = out_dir / "run.toml"
    path.write_bytes(msgspec.toml.encode(payload))
    return path


def write_profile_outputs(
    candidate: str,
    profile: StrainProfile,
    out_dir: Path,
    reads_mapped: int = 0,
    reads_total: int = 0,
) -> list[Path]:
    """Write the strains, genes, selection, and profile output files for a candidate."""
    comps = sorted(profile.components, key=lambda c: c.ra, reverse=True)

    def status_counts(comp):
        st = comp.family_status or {}
        return (
            sum(1 for v in st.values() if v == "observed"),
            sum(1 for v in st.values() if v == "reassigned"),
            sum(1 for v in st.values() if v == "imputed"),
        )

    strains_tsv = out_dir / f"{candidate}.strains.tsv"
    with open(strains_tsv, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(
            [
                "anchor",
                "members",
                "abundance",
                "ra",
                "n_genes",
                "n_observed",
                "n_reassigned",
                "n_imputed",
            ]
        )
        for c in comps:
            anchor = c.anchor_refs[0] if c.anchor_refs else f"comp{c.component_id}"
            n_obs, n_re, n_imp = status_counts(c)
            w.writerow(
                [
                    anchor,
                    ";".join(c.anchor_refs),
                    f"{c.abundance:.6f}",
                    f"{c.ra:.6f}",
                    len(c.family_ids),
                    n_obs,
                    n_re,
                    n_imp,
                ]
            )

    genes_tsv = out_dir / f"{candidate}.genes.tsv"
    with open(genes_tsv, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["strain", "family_id", "abundance", "status"])
        for c in comps:
            anchor = c.anchor_refs[0] if c.anchor_refs else f"comp{c.component_id}"
            ab = c.family_abundances or {}
            st = c.family_status or {}
            for fid in c.family_ids:
                w.writerow(
                    [
                        anchor,
                        fid,
                        f"{ab.get(fid, c.abundance):.6f}",
                        st.get(fid, "observed"),
                    ]
                )

    selection_tsv = out_dir / f"{candidate}.selection.tsv"
    with open(selection_tsv, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(
            ["step", "candidate", "residual", "cv_error", "accepted", "stop_reason"]
        )
        for i, s in enumerate(profile.selection.trace, 1):
            w.writerow(
                [
                    i,
                    s.added_label,
                    f"{s.residual:.6f}",
                    f"{s.cv_error:.6f}",
                    s.accepted,
                    s.stop_reason or "",
                ]
            )

    profile_json = out_dir / f"{candidate}.profile.json"
    payload = {
        "candidate": candidate,
        "k": profile.k,
        "r_squared": profile.r_squared,
        "residual": profile.residual,
        "reads_mapped": reads_mapped,
        "reads_total": reads_total,
        "components": [dataclasses.asdict(c) for c in comps],
        "trace": [dataclasses.asdict(s) for s in profile.selection.trace],
    }
    with open(profile_json, "w") as f:
        json.dump(payload, f, indent=2)

    return [strains_tsv, genes_tsv, selection_tsv, profile_json]


def _load_reads(refit_dir: Path):
    """Load a previous ProfileState read-only, or None if absent."""
    state_file = refit_dir / "state.pkl"
    if not state_file.exists():
        return None
    with open(state_file, "rb") as sf:
        return pickle.load(sf)


def profile_refit(
    refit_dir: Path,
    output_directory: Path,
    config: StrainProfileConfig,
    manifest_opts: dict,
) -> None:
    """Re-run only strain resolution from a previous cached run.

    Reuses the per-species annotated graphs under `refit_dir/annotations` and writes
    a fresh, standard profile output to `output_directory`, without touching
    `refit_dir`.
    """
    import msgspec

    anno_dir = refit_dir / "annotations"
    graphs = sorted(anno_dir.glob("*.profile.gt")) if anno_dir.exists() else []
    if not graphs:
        raise click.UsageError(
            f"no annotated graphs found under '{anno_dir}'; "
            "--refit needs a completed profile run"
        )

    old_manifest: dict = {}
    old_run = refit_dir / "run.toml"
    if old_run.exists():
        old_manifest = msgspec.toml.decode(old_run.read_bytes())
    sample_name = old_manifest.get("sample", refit_dir.name)
    collection = old_manifest.get("collection", "unknown")

    output_directory.mkdir(parents=True, exist_ok=True)
    metapang_add_log_file(output_directory / "logs.txt")
    write_run_manifest(
        output_directory,
        {
            "sample": sample_name,
            "collection": collection,
            "refit_from": str(refit_dir),
            "output": str(output_directory),
            **manifest_opts,
        },
    )

    old_state = _load_reads(refit_dir)

    mp_log.info(f"MetaPanG profile (refit) - sample '{sample_name}' from '{refit_dir}'")

    with timer() as gtime:
        n = len(graphs)
        results: list[tuple[str, StrainProfile, int, int]] = []
        for i, graph in enumerate(graphs, 1):
            candidate = graph.name.removesuffix(".profile.gt")
            mp_log.info(f"[{i}/{n}] Refitting species '{candidate}'")
            with timer() as ctime, log_indent():
                pwg = PWGraph(graph)
                with timer() as fit_time:
                    mp_log.info(f"⏳ Fitting strain mixture for '{candidate}'")
                    profile = profile_strains(pwg, config=config)
                mp_log.info(
                    f"✅ Fitting strain mixture for '{candidate}' - "
                    f"step: {fit_time.format()}, total: {gtime.format()}"
                )
                reads_mapped, reads_total = (
                    old_state.reads(candidate) if old_state else (0, 0)
                )
                mp_log.info(
                    f"Species '{candidate}': k={profile.k}, "
                    f"residual={profile.residual:.4f}"
                )
                log_strain_profile(candidate, profile)
                written = write_profile_outputs(
                    candidate, profile, output_directory, reads_mapped, reads_total
                )
                for path in written:
                    mp_log.info(f"Wrote {path}")
                results.append((candidate, profile, reads_mapped, reads_total))
            mp_log.debug(f"[{i}/{n}] '{candidate}' completed - step: {ctime.format()}")

        if results:
            report = write_profile_report(
                output_directory, sample_name, collection, results
            )
            mp_log.info(f"Wrote {report}")

    mp_log.info(
        f"✅ Refit complete - {n} species - total: {gtime.format()}, "
        f"peak memory: {_peak_rss_str()}"
    )


@click.command()
@click.argument(
    "query_args",
    nargs=-1,
    type=click.Path(exists=True, readable=True, path_type=Path),
    metavar="QUERIES...",
)
@click.option(
    "--query",
    "-q",
    "query",
    multiple=True,
    type=click.Path(exists=True, readable=True, path_type=Path),
    hidden=True,
    help="Deprecated: pass query files as positional arguments instead.",
)
@click.option(
    "--pangbank",
    "-b",
    type=str,
    help="""
        \b
        PanGBank collection, or a local pangenome, to profile against __placeholder__\n
        \b
        > Format: [bold]collection[/]\\[@version]\\[:pangenomes], or [bold]local:name[/]
            - [i]version[/] is optional ('latest' by default)
            - [i]pangenomes[/] is optional: a comma-separated list, each item a
              species name or a numeric PanGBank id. Give one or more to profile
              exactly those, otherwise every detected species is profiled.
            - [i]local:name[/] profiles a pangenome built with 'metapang cache add'.

        \b
        > Examples:
            [bold]GTDB_refseq@2.0.0:s__Klebsiella_pneumoniae[/]
            [bold]GTDB_refseq@2.0.0:s__Klebsiella_pneumoniae,s__Abiotrophia defectiva,10805[/]
            [bold]local:my_pangenome[/]
    """,
)
@click.option(
    "--output",
    "-o",
    type=str,
    help="""
        \b
        Output directory __placeholder__\n
        \b
        [bold]{query}[/] and [bold]{collection}[/] are substituted with the sample
        name (the first -q file) and the collection name.
    """,
)
@click.option(
    "--threads",
    "-t",
    type=int,
    help="""
        \b
        Number of threads __placeholder__\n
        \b
        Used for the read signature and the read-to-graph mapping.
    """,
)
@click.option(
    "--metagraph-path",
    "metagraph_path",
    type=str,
    help="""
        \b
        Path to the metagraph binary __placeholder__\n
        \b
        metagraph is not bundled with MetaPanG (it cannot share a conda
        environment with graph-tool). It must be on the PATH, or its path
        given here.
    """,
)
@click.option(
    "--stop-rule",
    type=click.Choice(["cv", "cv_paired"]),
    help="""
        \b
        How the number of strains is decided (by cross-validation) __placeholder__\n
        \b
        Gene families are hidden fold by fold and predicted from the rest: a real
        strain generalises to the hidden families, noise does not.
        \b
        > [bold]cv[/]        : one-standard-error rule, the fewest strains within one
          standard error of the best CV error. Can under-select on flat CV curves.
        > [bold]cv_paired[/] : keep a strain only if it [i]significantly[/] lowers the paired held-out error.
    """,
)
@click.option(
    "--k-max",
    "-k",
    type=int,
    help="""
        \b
        Maximum number of strains to consider __placeholder__\n
        \b
        Upper bound on the greedy search. The reported count is chosen by
        [bold]--stop-rule[/] and is usually well below this cap.
    """,
)
@click.option(
    "--merge-jaccard",
    type=float,
    help="""
        \b
        Collapse near-identical references before selection __placeholder__\n
        \b
        References whose gene-content Jaccard similarity is >= this value are merged
        into one "resolvable" strain, since near-clones cannot be told apart from
        coverage alone.
    """,
)
@click.option(
    "--cv-folds",
    type=int,
    help="""
        \b
        Number of cross-validation folds __placeholder__\n
        \b
        Gene families are split into this many folds to compute the held-out error
        used by [bold]--stop-rule[/].
    """,
)
@click.option(
    "--cv-min-gain",
    "cv_min_rel_reduction",
    type=float,
    help="""
        \b
        Minimum gain to keep a strain ([bold]--stop-rule cv_paired[/] only) __placeholder__\n
        \b
        A candidate strain is kept only if it lowers the cross-validated error by at
        least this fraction. Guards against adding near-duplicate strains.
    """,
)
@click.option(
    "--refine-ra/--no-refine-ra",
    help="""
        \b
        Refit abundances after gene reconciliation __placeholder__\n
        \b
        Once genes are reassigned/imputed to strains, re-solve the strain depths
        (NNLS) on the corrected gene content.
    """,
)
@click.option(
    "--impute-min-frac",
    "impute_min_neighbour_frac",
    type=float,
    help="""
        \b
        Dropout imputation threshold __placeholder__\n
        \b
        A gene a strain should carry but with zero coverage is kept (status
        [i]imputed[/]) only if at least this fraction of its neighbouring genes in
        that strain ARE covered.
    """,
)
@click.option(
    "--reassign-max-residual",
    "reassign_max_rel_residual",
    type=float,
    help="""
        \b
        Orphan-gene reassignment tolerance __placeholder__\n
        \b
        An observed gene carried by none of the selected strains is attached to the
        strain subset [i]T[/] whose summed depth best matches the gene's observed
        coverage [i]y[/]. It is kept only when the relative gap
        \b
            [i]|y - sum(depth of T)| / max(y, sum(depth of T))[/]
        \b
        is <= this value. Otherwise the gene is dropped.
    """,
)
@click.option(
    "--include-discarded",
    is_flag=False,
    flag_value="*",
    default=None,
    help=(
        "Include species MetaPanG discards by default. Bare flag includes all. "
        "--include-discarded=s__A,s__B includes only those."
    ),
)
@click.option(
    "--refit",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help=(
        "Re-run strain resolution (the optimization step) using a previous cached"
        "run in this directory. It writes a fresh run to -o. QUERIES and -b are not needed."
    ),
)
@click.pass_context
def profile(
    ctx,
    query_args,
    query,
    pangbank,
    output,
    threads,
    metagraph_path,
    stop_rule,
    k_max,
    merge_jaccard,
    cv_folds,
    cv_min_rel_reduction,
    refine_ra,
    impute_min_neighbour_frac,
    reassign_max_rel_residual,
    include_discarded,
    refit,
) -> None:
    """
    [bold]Strain-level metagenomic profiling against a pangenome collection[/]

    \b
    [bold]QUERIES[/] are the sequence files to profile (fasta/q, gzipped ok).
    Pass one or several (e.g. paired-end or split reads, or a glob like *.fastq.gz).

    \b
    [bold]Output[/] (per detected species, under the output directory)
      <species>.strains.tsv     per-strain abundance / RA / gene counts
      <species>.genes.tsv       per-strain gene family + status (observed/reassigned/imputed)
      <species>.profile.json    full result incl. the selection trace
      <species>.selection.tsv   the greedy selection trace and cross-validation errors
      report.html
    """
    config = StrainProfileConfig(
        merge_jaccard=merge_jaccard,
        k_max=k_max,
        stop_rule=stop_rule,
        cv_folds=cv_folds,
        cv_min_rel_reduction=cv_min_rel_reduction,
        refine_ra=refine_ra,
        impute_min_neighbour_frac=impute_min_neighbour_frac,
        reassign_max_rel_residual=reassign_max_rel_residual,
    )

    if refit is not None:
        if "{" in output:
            raise click.UsageError("--refit requires an explicit -o/--output directory")
        profile_refit(
            Path(refit),
            Path(output),
            config,
            {
                "stop_rule": stop_rule,
                "k_max": k_max,
                "merge_jaccard": merge_jaccard,
                "cv_folds": cv_folds,
                "cv_min_rel_reduction": cv_min_rel_reduction,
                "refine_ra": refine_ra,
                "impute_min_neighbour_frac": impute_min_neighbour_frac,
                "reassign_max_rel_residual": reassign_max_rel_residual,
            },
        )
        return

    ensure_metagraph(metagraph_path)

    collection, collection_version, pangenome = parse_collection_name_version(pangbank)

    if collection == LOCAL_COLLECTION:
        name = (pangenome or "").strip()
        if not name:
            raise click.UsageError("'-b local:<name>' requires a pangenome name")
        store = PanGBank_Cache(ctx.obj.get("config").pangbank)
        if not is_built(store.directory, name):
            raise click.UsageError(
                f"local pangenome '{name}' is not in the cache. Build it with "
                f"'metapang cache add <pangenome.h5> --name {name}'"
            )
        collection_proxy = LocalCacheProxy(local_dir(store.directory, name))
        requested_pangenomes: list[str] = [name]
        collection = f"{LOCAL_COLLECTION}:{name}"
        collection_version = LOCAL_COLLECTION
    else:
        pangbank_cache = PanGBank_Cache(ctx.obj.get("config").pangbank)

        if not pangbank_cache.api.has_collection(collection, collection_version):
            mp_log.error(
                f"Collection '{collection}@{collection_version}' not found in PanGBank."
            )
            sys.exit(1)

        collection_release = pangbank_cache.api.get_collection(
            collection, collection_version
        )

        compat.check_supported(collection_release.name, collection_release.version)

        requested_pangenomes = []
        for token in pangenome.split(",") if pangenome else []:
            name = token.strip()
            if not name:
                continue
            if name.isdigit():
                resolved = pangbank_cache.api.get_pangenome_name(
                    collection_release, int(name)
                )
                mp_log.info(f"Resolved pangenome id {name} to '{resolved}'")
                name = resolved
            if not pangbank_cache.api.has_pangenome(collection_release, name):
                mp_log.error(
                    f"Pangenome '{name}' not found in {collection_release.full_name}"
                )
                sys.exit(1)
            reason = compat.discard_reason(
                collection_release.name, collection_release.version, name
            )
            if reason:
                mp_log.warning(
                    f"Pangenome '{name}' is discarded for "
                    f"{collection_release.full_name} ({reason}). Profiling it anyway."
                )
            if name not in requested_pangenomes:
                requested_pangenomes.append(name)

        collection_proxy = pangbank_cache.proxy(collection_release)

    queries = list(query_args) + list(query)
    if not queries:
        raise click.UsageError(
            "provide at least one query file, e.g. "
            "'metapang profile reads.fastq.gz -b GTDB_refseq@2.0.0'"
        )
    sample_name = queries[0].stem
    output_directory = Path(output.format(query=sample_name, collection=collection))
    output_directory.mkdir(parents=True, exist_ok=True)
    metapang_add_log_file(output_directory / "logs.txt")

    write_run_manifest(
        output_directory,
        {
            "sample": sample_name,
            "collection": collection,
            "collection_version": collection_version,
            "pangenomes": requested_pangenomes,
            "query": [str(q) for q in queries],
            "output": str(output_directory),
            "threads": threads,
            "metagraph_path": metagraph_path,
            "stop_rule": stop_rule,
            "k_max": k_max,
            "merge_jaccard": merge_jaccard,
            "cv_folds": cv_folds,
            "cv_min_rel_reduction": cv_min_rel_reduction,
            "refine_ra": refine_ra,
            "impute_min_neighbour_frac": impute_min_neighbour_frac,
            "reassign_max_rel_residual": reassign_max_rel_residual,
        },
    )

    state = ProfileState.load(output_directory / "state.pkl")

    mp_log.info(
        f"MetaPanG profile - sample '{sample_name}' vs collection '{collection}'"
    )
    mp_log.debug(f"Output directory: '{output_directory}'")
    mp_log.debug(
        f"Selection: stop_rule={stop_rule}, k_max={k_max}, cv_folds={cv_folds}, "
        f"merge_jaccard={merge_jaccard}; refine_ra={refine_ra}; threads={threads}"
    )
    mp_log.trace(f"Query files: {[str(q) for q in queries]}")

    with timer() as gtime:
        if requested_pangenomes:
            candidates = requested_pangenomes
            mp_log.info(
                f"Profiling {len(candidates)} requested pangenome(s): "
                f"{', '.join(candidates)}"
            )
        else:
            all_discarded = compat.discarded_species(
                collection_release.name, collection_release.version
            )
            if include_discarded == "*":
                included = set(all_discarded)
            elif include_discarded is None:
                included = set()
            else:
                included = {
                    s.strip() for s in include_discarded.split(",") if s.strip()
                }
            discarded = {s: r for s, r in all_discarded.items() if s not in included}
            if discarded:
                mp_log.info(
                    f"Excluding {len(discarded)} discarded species from detection "
                    "(use --include-discarded to include them):"
                )
                for species, reason in sorted(discarded.items()):
                    mp_log.info(f"  - {species}: {reason}")
            assert isinstance(collection_proxy, PanGBank_Cache.CollectionCacheProxy)
            candidates = phase1(
                state,
                collection_proxy,
                output_directory,
                queries,
                sample_name,
                threads,
                gtime,
                discarded,
            )

        anno_output_directory = output_directory / "annotations"
        anno_output_directory.mkdir(parents=True, exist_ok=True)

        n = len(candidates)
        results: list[tuple[str, StrainProfile, int, int]] = []
        for i, candidate in enumerate(candidates, 1):
            mp_log.info(f"[{i}/{n}] Profiling species '{candidate}'")
            with timer() as ctime, log_indent():
                out_fam, _out_gen = phase2_mapping(
                    state,
                    candidate,
                    collection_proxy,
                    output_directory,
                    queries,
                    threads,
                    metagraph_path,
                    gtime,
                )

                annotated_gt = anno_output_directory / f"{candidate}.profile.gt"

                if state.annotation(candidate) and annotated_gt.exists():
                    mp_log.info(
                        f"Reusing cached annotated graph for '{candidate}' ('{annotated_gt}')"
                    )
                    pwg = PWGraph(annotated_gt)
                else:
                    with timer() as anno_time:
                        mp_log.info(f"⏳ Annotating pangenome graph for '{candidate}'")
                        dbg_path = collection_proxy.get_dbg(candidate)
                        pangenome_gt = dbg_path / f"{candidate}.gt"
                        pwg = PWGraph(pangenome_gt)
                        report = PWGraphAnnotator(pwg, out_fam).annotate()
                        ratio = (
                            f" ({100 * report.total_seq_mapped / report.total_seq:.1f}%)"
                            if report.total_seq
                            else ""
                        )
                        mp_log.debug(
                            f"  {pwg.graph.num_vertices()} families; reads mapped: "
                            f"{report.total_seq_mapped}/{report.total_seq}{ratio}"
                        )
                        pwg.save(annotated_gt)
                        state.annotation_ok(
                            candidate, report.total_seq_mapped, report.total_seq
                        )
                        mp_log.trace(f"  saved annotated graph '{annotated_gt}'")
                    mp_log.info(
                        f"✅ Annotating pangenome graph for '{candidate}' - "
                        f"step: {anno_time.format()}, total: {gtime.format()}"
                    )

                with timer() as fit_time:
                    mp_log.info(
                        f"⏳ Fitting strain mixture for '{candidate}' (NNLS + {stop_rule} selection)"
                    )
                    profile = profile_strains(pwg, config=config)
                mp_log.info(
                    f"✅ Fitting strain mixture for '{candidate}' - "
                    f"step: {fit_time.format()}, total: {gtime.format()}"
                )
                reads_mapped, reads_total = state.reads(candidate)
                pct = (
                    f" ({100 * reads_mapped / reads_total:.1f}%)" if reads_total else ""
                )
                mp_log.info(
                    f"Species '{candidate}': k={profile.k}, residual={profile.residual:.4f}, "
                    f"reads mapped={reads_mapped}/{reads_total}{pct}"
                )
                log_strain_profile(candidate, profile)

                written = write_profile_outputs(
                    candidate, profile, output_directory, reads_mapped, reads_total
                )
                for path in written:
                    mp_log.info(f"Wrote {path}")
                results.append((candidate, profile, reads_mapped, reads_total))
            mp_log.debug(
                f"[{i}/{n}] '{candidate}' completed - step: {ctime.format()}, total: {gtime.format()}"
            )

        if results:
            report = write_profile_report(
                output_directory, sample_name, collection, results
            )
            mp_log.info(f"Wrote {report}")

    mp_log.info(
        f"✅ Profiling complete - {n} species - total: {gtime.format()}, peak memory: {_peak_rss_str()}"
    )
