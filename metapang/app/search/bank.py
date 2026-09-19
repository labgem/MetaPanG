import sys
from pathlib import Path

import rich_click as click

from metapang.app.utils import ClickEnum, show_df_in_rich
from metapang.core.index.search import (
    IndexBuilder,
    IndexSearch,
    IndexType,
    SearchMode,
    SearchResult,
)
from metapang.logger import mp_log
from metapang.pg.api import PanGBank_Cache, parse_collection_name_version


@click.command()
@click.option(
    "--index",
    "-i",
    type=click.Path(exists=True, readable=True, path_type=Path),
    help="The index directory (i.e. the output of 'metapang index bank')",
)
@click.option(
    "--pangbank",
    "-p",
    type=str,
    help="Use an index from PanGBank (e.g. GTDB_refseq, GTDB_refseq@v1.0.0, GTDB_refseq@latest)",
)
@click.option(
    "--query",
    "-q",
    type=click.Path(exists=True, readable=True, path_type=Path),
    required=True,
    help="The query file, in fasta/q format, possibly gzipped",
)
@click.option(
    "--threshold-pangenome",
    "-tp",
    type=float,
    help="Min threshold to consider a match in the pangenome index __placeholder__",
)
@click.option(
    "--threshold-genome",
    "-tg",
    type=float,
    help="Min threshold to consider a match in the genome index __placeholder__",
)
@click.option("--mode", "-m", type=ClickEnum(SearchMode), help="Search mode")
@click.option(
    "--gather",
    "-g",
    is_flag=True,
    default=False,
    help="Use gather (min-set-cover) on the genome index instead of independent "
    "containment search: deconvolves shared k-mers so only references that "
    "explain new sample k-mers are reported",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=str),
    default="{query_file}_{index_type}.tsv",
    help="Output file",
)
@click.option(
    "--threads",
    type=int,
    help="Number of threads to use for the search",
)
@click.pass_context
def bank(
    ctx,
    index,
    pangbank,
    query,
    threshold_pangenome,
    threshold_genome,
    mode,
    gather,
    output,
    threads,
) -> None:
    """
    [bold]Search a bank[/]

    \b
    [bold][u]INPUT[/u]:
    [u]QUERY[/u]:
    \b
    It outputs a TSV file with the following columns:
        - [i]query_name[/]: name of the query
        - [i]name[/]: name of the genome
        - [i]score[/]: score of the match
            - with mode 'containment': query containment in the match
            - with mode 'jaccard': jaccard index between the query and the match
        - [i]coverage[/]: coverage of the match, match containment in the query[/]
    """

    if pangbank:
        if index:
            raise click.UsageError("Cannot use both --index and --pangbank")
    else:
        if not index:
            raise click.UsageError("You must provide either --pangbank OR --index")

    config = ctx.obj.get("config")

    if pangbank:
        config.pangbank.cache_directory = Path(config.pangbank.cache_directory)
        pangbank_cache = PanGBank_Cache(config.pangbank)
        collection, collection_version, _ = parse_collection_name_version(pangbank)

        if not pangbank_cache.api.has_collection(collection, collection_version):
            mp_log.error(f"Collection '{pangbank}' not found in PanGBank")
            sys.exit(1)

        collection_release = pangbank_cache.api.get_collection(
            collection, collection_version
        )

        mp_log.info(f"Using collection: '{collection_release.full_name}' from PanGBank")
        index = pangbank_cache.get_index(collection_release)
    else:
        index = Path(index)

    query = Path(query)

    mp_log.info(f"Load index from '{index}'")
    search = IndexSearch(index, to_load=IndexType.all)
    mp_log.info(f"Searching for '{query.stem}'")

    signature = IndexBuilder.file_batch_signature(
        query,
        search.info.kmer_size,
        search.info.scaled,
        search.info.n,
        True,
        threads,
        threads * 10,
        1000,
    )

    if gather:
        import pandas as pd

        rows = search.gather_signature(
            signature, IndexType.genome, threshold=threshold_genome or 0.0
        )
        df = pd.DataFrame(rows, columns=["name", "f_query", "f_match"])  # type: ignore[arg-type]
        if not df.empty:
            df["cum_f_query"] = df["f_query"].cumsum().round(4)
        out_path = (
            f"{output.format(query_file=str(query), index_type='gather_genome')}.tsv"
        )
        df.to_csv(out_path, sep="\t", index=False)
        mp_log.info(f"Gather selected {len(df)} references, writing to '{out_path}'")
        show_df_in_rich(df, title="Gather (min-set-cover) on genome index")
        return

    pang_results = search.search_signature(
        signature, IndexType.pangenome, mode, threshold_pangenome
    )
    geno_results = search.search_signature(
        signature, IndexType.genome, mode, threshold_genome
    )

    pang_df = SearchResult.to_dataframe(pang_results)
    geno_df = SearchResult.to_dataframe(geno_results)

    pang_output = f"{output.format(query_file=str(query), index_type=IndexType.pangenome.name)}_pangenome.tsv"
    geno_output = f"{output.format(query_file=str(query), index_type=IndexType.genome.name)}_genome.tsv"

    mp_log.info(
        f"Found {len(pang_results)} matches in pangenome index, writing to '{pang_output}'"
    )
    mp_log.info(
        f"Found {len(geno_results)} matches in genome index, writing to '{geno_output}'"
    )

    show_df_in_rich(pang_df, title="Pangenome search results")
    show_df_in_rich(geno_df, title="Genome search results")
