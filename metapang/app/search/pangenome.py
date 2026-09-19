import sys
from pathlib import Path

import rich_click as click

from metapang.core.graph import PWGraph, PWGraphAnnotator
from metapang.core.index.dbg import MetagraphCLI, MetagraphQueryOptions
from metapang.logger import mp_log
from metapang.pg.api import PanGBank_Cache, parse_collection_name_version
from metapang.utils.time import timer


@click.command()
@click.option(
    "--dbg",
    "-g",
    type=click.Path(exists=True, readable=True, path_type=Path),
    help="The pangenome dbg",
)
@click.option(
    "--annotations",
    "-a",
    type=click.Path(exists=True, readable=True, path_type=Path),
    help="The pangenome annotations",
)
@click.option(
    "--pangbank",
    "-p",
    type=str,
    help="""
        Use a pangenome dbg from PanGBank (format: collection[@version]:name)\n
        e.g. GTDB_refseq:s__Abiotrophia_defectiva, GTDB_refseq@v1.0.0:s__Abiotrophia_defectiva
    """,
)
@click.option(
    "--query",
    "-q",
    type=click.Path(exists=True, readable=True, path_type=Path),
    required=True,
    help="The query file, in fasta/q format, possibly gzipped",
)
@click.option(
    "--threads",
    "-t",
    type=int,
    help="Number of threads to use for indexing __placeholder__.",
)
@click.option(
    "--metagraph-path",
    "metagraph_path",
    type=str,
    help="Path to the metagraph binary (must be on the PATH otherwise) __placeholder__.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=str),
    help="Output file ('stdout' or '-' for standard output) __placeholder__.",
)
@click.option(
    "--annotate",
    type=click.Path(path_type=Path),
    help="Also write a graph_tool annotated pangenome graph (.gt) to this path,"
    "with per-family read and k-mer counts",
)
@click.pass_context
def pangenome(
    ctx, dbg, annotations, pangbank, query, threads, metagraph_path, output, annotate
) -> None:
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
                raise click.UsageError(
                    "You must provide either --pangbank OR (--dbg AND --annotations), not both."
                )
        else:
            if not (dbg and annotations):
                raise click.UsageError(
                    "You must provide either --pangbank OR (--dbg AND --annotations)."
                )

        if annotate and not pangbank:
            raise click.UsageError(
                "--annotate requires --pangbank: the annotated graph is built on the prebuilt .gt downloaded from PanGBank"
            )
        if annotate and output in ("stdout", "-"):
            raise click.UsageError(
                "--annotate needs the query results in a file. Set --output to a file, not stdout"
            )

        config = ctx.obj.get("config")

        if pangbank:
            pangbank_cache = PanGBank_Cache(config.pangbank)
            collection, collection_version, pangenome_name = (
                parse_collection_name_version(pangbank)
            )

            if not pangenome_name:
                mp_log.error(
                    f"Invalid pangbank format: '{pangbank}', expected 'collection[@version]:name'"
                )
                sys.exit(1)

            if not pangbank_cache.api.has_collection(collection, collection_version):
                mp_log.error(
                    f"Collection '{collection}@{collection_version}' not found in PanGBank."
                )
                sys.exit(1)

            collection_release = pangbank_cache.api.get_collection(
                collection, collection_version
            )

            if not pangbank_cache.api.has_pangenome(collection_release, pangenome_name):
                mp_log.error(
                    f"Pangenome '{pangenome_name}' not found in {collection_release.full_name}"
                )
                sys.exit(1)

            proxy = pangbank_cache.proxy(collection_release)
            mp_log.info(
                f"Using pangenome: '{collection_release.full_name}:{pangenome_name}' from PanGBank"
            )
            dbg_directory = proxy.get_dbg(pangenome_name)
            dbg_file = dbg_directory / f"{pangenome_name}.dbg"
            annotations_file = dbg_directory / f"{pangenome_name}.row_diff_brwt.annodbg"
            pangenome_gt = dbg_directory / f"{pangenome_name}.gt"
        else:
            dbg_file = dbg
            annotations_file = annotations
            pangenome_gt = None

        mcli = MetagraphCLI(metagraph_path)

        if output not in ("stdout", "-"):
            output = output.format(
                pangenome_name=dbg_file.stem, query_file_name=query.stem
            )

        query_opt = MetagraphQueryOptions(
            i=dbg_file,
            a=annotations_file,
            query_file=query,
            output_file=output,
            parallel=threads,
            query_mode="matches",
        )

        mp_log.info(f"Searching for '{query.stem}' in pangenome dbg '{dbg_file.name}'")

        mcli.query(query_opt)

        if annotate:
            assert pangenome_gt is not None
            if not pangenome_gt.exists():
                mp_log.error(
                    f"Cannot annotate: pangenome graph '{pangenome_gt}' not found"
                )
                sys.exit(1)
            mp_log.info(f"Annotating pangenome graph '{pangenome_gt.name}'")
            pwg = PWGraph(pangenome_gt)
            report = PWGraphAnnotator(pwg, Path(output)).annotate()
            ratio = (
                f" ({100 * report.total_seq_mapped / report.total_seq:.1f}%)"
                if report.total_seq
                else ""
            )
            pwg.save(annotate)
            mp_log.info(
                f"Reads mapped: {report.total_seq_mapped}/{report.total_seq}{ratio}"
            )

        mp_log.info(f"Done ({t.format()})")

        if output not in ("stdout", "-"):
            mp_log.info(f"Output available at '{output}'")
        if annotate:
            mp_log.info(f"Annotated graph available at '{annotate}'")
