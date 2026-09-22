# `metapang profile`

Strain-level profiling of a metagenomic sample against a `PanGBank` pangenome
collection. This is the main `MetaPanG` command.

## Synopsis

```
metapang profile QUERIES... -b GTDB_refseq@2.0.0 [OPTIONS]
```

## How it works

`profile` runs a three-phase pipeline and writes one set of result files per
detected species.

1. **Species detection.** A MinHash signature is computed from the query reads and
   searched against the collection genome index with a min-set-cover (gather)
   procedure. The references that jointly explain the sample k-mers become the
   candidate species. This phase is skipped when species are named explicitly with
   the `:pangenomes` suffix of `-b`.
2. **Read mapping.** For each candidate species, the reads are mapped onto the
   species pangenome de Bruijn graph with `metagraph`, giving the per gene-family
   coverage of the sample.
3. **Strain resolution.** From the observed gene-family coverage, strains are
   selected greedily up to `--k-max`, and the number of strains is decided by a
   cross-validated stop rule (`--stop-rule`). Gene content is then reconciled per
   strain (each family marked `observed`, `reassigned`, or `imputed`) and, unless
   disabled, the strain depths are refit by non-negative least squares.

The run is **resumable**. A `state.pkl` checkpoint and the cached intermediate files
(query signature, read mapping, annotated graphs) are reused, so re-running the same
command in the same output directory continues where it stopped.

## Collection compatibility

`MetaPanG` only profiles against collection versions it supports, and discards a
few unreliable species by default. Naming a discarded species explicitly (through
the `:pangenomes` suffix of `-b`, or `--include-discarded`) profiles it anyway. The
full policy and how to override it are described in
[Managing pangenome data](data.md#collection-compatibility).

## Inputs

`QUERIES...` (required, positional)
: Sequence files to profile (fasta/fastq, gzipped ok). Pass one or
  several, for example paired-end or split reads, or a shell glob such as
  `*.fastq.gz`. Stem of the first file is used as the sample name.

`-b`, `--pangbank` (default `GTDB_refseq`)
: The collection to profile against, as `collection[@version][:pangenomes]`.

  - `version` is optional and defaults to `latest`.
  - `pangenomes` is optional: a comma-separated list, each item either a species
    name or a numeric `PanGBank` id. Give one or more to profile exactly those and
    skip species detection. Omit it to profile every detected species.

  ```
  # detect and profile every species found in the sample
  metapang profile reads.fastq.gz -b GTDB_refseq@2.0.0

  # profile one named species, skipping detection
  metapang profile reads.fastq.gz -b GTDB_refseq@2.0.0:s__Klebsiella_pneumoniae

  # profile several targets (names and/or numeric ids)
  metapang profile reads.fastq.gz \
    -b GTDB_refseq@2.0.0:s__Klebsiella_pneumoniae,s__Abiotrophia_defectiva,10805
  ```

## Options

### Input / output

| Option | Default | Description |
| --- | --- | --- |
| `-o`, `--output` | `{query}_{collection}_profile` | Output directory. `{query}` and `{collection}` are substituted with the sample name and the collection name. |
| `-t`, `--threads` | `1` | Threads used for the read signature and the read-to-graph mapping. |
| `--metagraph-path` | `metagraph` | Path to the `metagraph` binary. |

### Strain selection

| Option | Default | Description |
| --- | --- | --- |
| `--stop-rule` | `cv_paired` | How the number of strains is decided by cross-validation. `cv` uses the one-standard-error rule (the fewest strains within one standard error of the best CV error, which can under-select on flat curves). `cv_paired` keeps a strain only if it significantly lowers the paired held-out error. |
| `-k`, `--k-max` | `12` | Upper bound on the greedy search. The reported count is chosen by `--stop-rule` and is usually well below this cap. |

### Advanced

| Option | Default | Description |
| --- | --- | --- |
| `--merge-jaccard` | `0.95` | Collapse near-identical references before selection. References whose gene-content Jaccard similarity is at least this value are merged into one resolvable strain, since near-clones cannot be told apart from coverage alone. |
| `--cv-folds` | `5` | Number of cross-validation folds used to compute the held-out error for `--stop-rule`. |
| `--cv-min-gain` | `0.02` | Minimum gain to keep a strain (`--stop-rule cv_paired` only). A candidate is kept only if it lowers the cross-validated error by at least this fraction. Guards against adding near-duplicate strains. |
| `--refine-ra` / `--no-refine-ra` | `--refine-ra` | Refit abundances after gene reconciliation. Once genes are reassigned or imputed, re-solve the strain depths (NNLS) on the corrected gene content. |
| `--impute-min-frac` | `0.5` | Dropout imputation threshold. A gene a strain should carry but with zero coverage is kept (status `imputed`) only if at least this fraction of its neighbouring genes in that strain are covered. |
| `--reassign-max-residual` | `0.5` | Orphan-gene reassignment tolerance. An observed gene carried by none of the selected strains is attached to the strain subset `T` whose summed depth best matches the gene coverage `y`, and kept only when `|y - sum(depth of T)| / max(y, sum(depth of T))` is at most this value. Otherwise the gene is dropped. |
| `--include-discarded` | off | Include species discarded by the compatibility policy (see [Collection compatibility](#collection-compatibility)). The bare flag includes all. `--include-discarded=s__A,s__B` includes only those, the rest stay excluded. |
| `--refit` | | Re-run only strain resolution from a previous run's cached mapping (see [Reoptimizing an existing run](#reoptimizing-an-existing-run)). |

## Reoptimizing an existing run

Strain resolution is cheap and tunable. `--refit` re-runs
**only** strain resolution, reusing a previous run, so
you can try different [strain-selection](#strain-selection) and
[advanced](#advanced) parameters without recomputing anything.

```
metapang profile --refit OLD -o NEW [options]
```

- `--refit OLD` names a completed run directory.
- `QUERIES` / `-b/--pangbank` are not needed.
- `-o NEW` is required

```
# full run once
metapang profile reads.fastq.gz -b GTDB_refseq@2.0.0 -o base

# sweep strain parameters, reusing base
metapang profile --refit base -o base_k16 --k-max 16
metapang profile --refit base -o base_cv  --stop-rule cv
metapang profile --refit base -o base_min --cv-min-gain 0.01
```

## Output

Results are written to the output directory, one set of files per detected species.

| File | Content |
| --- | --- |
| `<species>.strains.tsv` | per-strain depth, relative abundance, and gene counts |
| `<species>.genes.tsv` | per-strain gene families with their reconciliation status |
| `<species>.selection.tsv` | the greedy selection trace and cross-validation errors |
| `<species>.profile.json` | the full result, including mapped-read counts and the trace |
| `report.html` | a self-contained summary of all detected species |
| `logs.txt` | the run log |
| `run.toml` | the `MetaPanG` version and the options used for the run |

Intermediate files (`state.pkl`, the query signature, the read mapping, and the
annotated graphs under `annotations/`) are cached so that a run can be resumed.

### `<species>.strains.tsv`

One row per resolved strain, sorted by relative abundance.

`anchor`
: the reference genome that names the strain.

`members`
: the reference genomes merged into this strain (see `--merge-jaccard`),
  semicolon-separated.

`abundance`
: the strain depth.

`ra`
: the relative abundance among the strains of this species.

`n_genes`
: number of gene families assigned to the strain.

`n_observed`, `n_reassigned`, `n_imputed`
: gene families by reconciliation status.

### `<species>.genes.tsv`

One row per (strain, gene family): the strain `anchor`, the `family_id`, its
`abundance`, and its `status` (`observed`, `reassigned`, or `imputed`).

### `<species>.selection.tsv`

The greedy selection trace, one row per step: the `step` index, the `candidate`
reference added, the `residual` and cross-validated `cv_error` at that step, whether
the step was `accepted`, and the `stop_reason` when selection stopped.

### `<species>.profile.json`

The full machine-readable result: the `candidate` species, the selected strain count
`k`, the fit quality (`r_squared`, `residual`), the `reads_mapped` and `reads_total`
counts, the per-strain `components`, and the selection `trace`.

## Examples

```
# whole-sample profiling with 8 threads
metapang profile reads_1.fastq.gz reads_2.fastq.gz \
  -b GTDB_refseq@2.0.0 -t 8 -o sample_profile

# target one species and allow more strains
metapang profile reads.fastq.gz \
  -b GTDB_refseq@2.0.0:s__Klebsiella_pneumoniae -k 20
```
