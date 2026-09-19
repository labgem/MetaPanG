# `metapang search bank`

Match a query against a whole bank (a `PanGBank` collection or a local index built
with `metapang index bank`) to find which genomes and pangenomes it resembles. This
is the species-detection step of [`metapang profile`](profile.md) exposed on its own.

Matching is done with `sourmash` MinHash sketches, so both the query and the index
are reduced to k-mer signatures and compared by containment or Jaccard similarity. A
bank holds two indexes, searched together: a **pangenome index** (one signature per
species pangenome) and a **genome index** (one signature per reference genome).

## Synopsis

```
metapang search bank -q query.fasta.gz -p GTDB_refseq@2.0.0 [OPTIONS]
metapang search bank -q query.fasta.gz -i path/to/index    [OPTIONS]
```

## Inputs

The query is required, and the bank is given in exactly one of two ways.

`-q`, `--query` (required)
: The query file (fasta/fastq, gzipped accepted). It may be a genome or metagenomic
  reads. All sequences are folded into a single signature.

`-p`, `--pangbank`
: Use an index from `PanGBank`, for example `GTDB_refseq`, `GTDB_refseq@v1.0.0`, or
  `GTDB_refseq@latest`. The index is downloaded and cached on first use.

`-i`, `--index`
: Use a local index directory (the output of `metapang index bank`).

:::{note}
Give either `--pangbank` or `--index`, not both.
:::

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-m`, `--mode` | | Search mode: `jaccard`, `containment`, or `max_containment`. Determines how `score` is computed (see below). |
| `-tg`, `--threshold-genome` | `0.5` | Minimum score to report a match in the genome index. |
| `-tp`, `--threshold-pangenome` | `0.05` | Minimum score to report a match in the pangenome index. |
| `-g`, `--gather` | off | Use gather (min-set-cover) on the genome index instead of independent containment search. It deconvolves shared k-mers so only references that explain new sample k-mers are reported. |
| `-o`, `--output` | `{query_file}_{index_type}.tsv` | Output file. One file per index (`_genome.tsv`, `_pangenome.tsv`), or a single `gather_genome.tsv` with `--gather`. |
| `--threads` | | Threads used to sketch the query. |

## Search modes

The `score` column depends on `--mode`:

`containment`
: the fraction of the query k-mers contained in the match. Good for asking "is the
  query part of this reference".

`max_containment`
: the larger of the two containments (query-in-match and match-in-query).

`jaccard`
: the Jaccard index between the query and the match k-mer sets. Sensitive to size
  differences, so it is low when query and reference differ greatly in length.

## Output

A TSV with the following columns:

`query_name`
: name of the query.

`name`
: name of the matched genome or pangenome.

`score`
: score of the match, per `--mode` above.

`coverage`
: coverage of the match, that is the containment of the match in the query.

By default two files are written, one for the pangenome index and one for the genome
index, and the results are also shown as tables in the terminal.

With `--gather`, a single min-set-cover result is written for the genome index with
columns `name`, `f_query` (fraction of the query explained by this reference),
`f_match`, and `cum_f_query` (cumulative fraction of the query explained).

## Examples

```
# search a genome against a PanGBank collection, by containment
metapang search bank -q genome.fasta.gz -p GTDB_refseq@2.0.0 -m containment

# detect species in reads with min-set-cover on the genome index
metapang search bank -q reads.fastq.gz -p GTDB_refseq@2.0.0 --gather -t 8

# search a locally built index and raise the genome threshold
metapang search bank -q genome.fasta.gz -i ./my_index -tg 0.7
```
