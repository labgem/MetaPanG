import rich_click as click
from pathlib import Path
from metapang.logger import mp_log
from metapang.pg.api import PanGBank_Cache, parse_collection_name_version
from metapang.core.index.dbg import MetagraphCLI, MetagraphQueryOptions
from metapang.utils.time import timer
import sys

@click.command()
@click.option(
    "--dbg", "-g",
    type=click.Path(exists=True, readable=True, path_type=Path),
    help="The pangenome dbg"
)
@click.option(
    "--annotations", "-a",
    type=click.Path(exists=True, readable=True, path_type=Path),
    help="The pangenome annotations"
)
@click.option(
    "--pangbank", "-p",
    type=str,
    help="""
        Use a pangenome dbg from PanGBank (format: collection[@version]:name)\n
        e.g. GTDB_refseq:s__Abiotrophia_defectiva, GTDB_refseq@v1.0.0:s__Abiotrophia_defectiva
    """
)
@click.option(
    "--query", "-q",
    type=click.Path(exists=True, readable=True, path_type=Path), required=True,
    help="The query file, in fasta/q format, possibly gzipped"
)
@click.option(
    "--threads", "-t",
    type=int,
    help="Number of threads to use for indexing __placeholder__.",
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=str),
    help="Output file ('stdout' or '-' for standard output) __placeholder__.",
)
@click.pass_context
def pangenome(ctx, dbg, annotations, pangbank, query, threads, output) -> None:
    """
    [bold]Search a in a MetaPanG pangenome index[/bold]

    \b
    [bold][u]INPUT[/u]: The pangenome dbg directory (i.e. the output of 'metapang index bank')
    [u]QUERY[/u]: The query genome, in fasta format, possibly gzipped
    \b
    It outputs a TSV file with the following columns:
    - query_name: name of the query
    - name: name of the pangenome
    - score: score of the match
        - with mode 'containment': query containment in the match
        - with mode 'jaccard': jaccard index between the query and the match
    - coverage: coverage of the match, match containment in the query[/]
    """
    with timer() as t:
        if pangbank:
            if dbg or annotations:
                raise click.UsageError("You must provide either --pangbank OR (--dbg AND --annotations), not both.")
        else:
            if not (dbg and annotations):
                raise click.UsageError("You must provide either --pangbank OR (--dbg AND --annotations).")

        config = ctx.obj.get("config")

        if pangbank:
            pangbank_cache = PanGBank_Cache(config.pangbank)
            collection, collection_version, pangenome_name = parse_collection_name_version(pangbank)

            if not pangenome_name:
                mp_log.error(f"Invalid pangbank format: '{pangbank}', expected 'collection[@version]:name'")
                sys.exit(1)

            if not pangbank_cache.api.has_collection(collection, collection_version):
                mp_log.error(f"Collection '{collection}@{collection_version}' not found in PanGBank.")
                sys.exit(1)

            collection_release = pangbank_cache.api.get_collection(collection, collection_version)

            if not pangbank_cache.api.has_pangenome(collection_release, pangenome_name):
                mp_log.error(f"Pangenome '{pangenome_name}' not found in {collection_release.full_name}")
                sys.exit(1)

            proxy = pangbank_cache.proxy(collection_release)
            mp_log.info(f"Using pangenome: '{collection_release.full_name}:{pangenome_name}' from PanGBank")
            dbg_directory = proxy.get_dbg(pangenome_name)
            dbg_file = dbg_directory / f"{pangenome_name}.dbg"
            annotations_file = dbg_directory / f"{pangenome_name}.row_diff_brwt.annodbg"
        else:
            dbg_file = dbg
            annotations_file = annotations

        mcli = MetagraphCLI()

        if output not in ("stdout", "-"):
            output = output.format(pangenome_name = dbg_file.stem, query_file_name = query.stem)

        query_opt = MetagraphQueryOptions(
            i = dbg_file,
            a = annotations_file,
            query_file = query,
            output_file = output,
            parallel = threads,
            query_mode = "matches"
        )

        mp_log.info(f"Searching for '{query.stem}' in pangenome dbg '{dbg_file.name}'")

        mcli.query(query_opt)

        mp_log.info(f"Done ({t.format()})")

        if output not in ("stdout", "-"):
            mp_log.info(f"Output available at '{output}'")



