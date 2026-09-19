# `metapang search pangenome`

Match a query against a single species pangenome de Bruijn graph to find which gene
families it contains. This is the read-mapping step of
[`metapang profile`](profile.md) exposed on its own, for one pangenome.

Unlike [`metapang search bank`](search-bank.md), which compares MinHash sketches
across a whole collection, this command uses `metagraph` to look up exact k-mers in
one pangenome graph and report, for each query sequence, the gene-family labels it
matches.

## Synopsis

```
metapang search pangenome -q query.fasta.gz -p GTDB_refseq@2.0.0:s__Abiotrophia_defectiva [OPTIONS]
metapang search pangenome -q query.fasta.gz -g pangenome.dbg -a pangenome.annodbg      [OPTIONS]
```

## Inputs

The query is required, and the pangenome is given in exactly one of two ways: from
`PanGBank`, or as a local de Bruijn graph plus its annotations.

`-q`, `--query` (required)
: The query file (fasta/fastq, gzipped accepted), a genome or reads.

`-p`, `--pangbank`
: Use a pangenome from `PanGBank`, as `collection[@version]:name`, for example
  `GTDB_refseq:s__Abiotrophia_defectiva` or
  `GTDB_refseq@v1.0.0:s__Abiotrophia_defectiva`. The graph is downloaded and cached
  on first use.

`-g`, `--dbg`
: A local pangenome de Bruijn graph (the `.dbg` file).

`-a`, `--annotations`
: The annotations for that graph (the `.annodbg` file).

:::{note}
Give either `--pangbank`, or both `--dbg` and `--annotations`. The `--dbg` /
`--annotations` pair is the per-pangenome output of `metapang index bank`.
:::

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-t`, `--threads` | `1` | Threads used by `metagraph` for the query. |
| `--metagraph-path` | `metagraph` | Path to the `metagraph` binary. |
| `-o`, `--output` | `{pangenome_name}_{query_file_name}.tsv` | Output file. Use `stdout` or `-` to write to standard output. |
| `--annotate` | | Also write a `graph_tool` annotated pangenome graph (`.gt`) to this path, with per-family read and k-mer counts, as `metapang profile` produces. |

## Output

A TSV produced by `metagraph`: for each query sequence, the pangenome gene families
(labels) whose k-mers it matches. This is the same per-family mapping that `profile`
uses internally to derive gene-family coverage.

### Annotated graph (`--annotate`)

With `--annotate graph.gt`, the query result is projected back onto the pangenome
graph: the prebuilt `.gt` for the species is loaded and each gene family is annotated
with its read and k-mer counts, then saved to the given path. This is the same
annotated graph `metapang profile` builds internally.

:::{note}
`--annotate` requires `--pangbank`, because it needs the prebuilt `.gt` graph
downloaded from `PanGBank` (the local `--dbg` / `--annotations` inputs do not include
it). It also needs the query results in a file, so it cannot be combined with
`--output stdout`.
:::

## Examples

```
# search a genome against one PanGBank pangenome
metapang search pangenome -q genome.fasta.gz \
  -p GTDB_refseq@2.0.0:s__Abiotrophia_defectiva -t 8

# search a locally indexed pangenome and print to stdout
metapang search pangenome -q genome.fasta.gz \
  -g s__Abiotrophia_defectiva.dbg -a s__Abiotrophia_defectiva.annodbg -o -
```
