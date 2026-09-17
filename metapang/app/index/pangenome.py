import os
from pathlib import Path

import rich_click as click

from metapang.logger import mp_log
from metapang.utils.time import timer
from metapang.pg.dump import pg_fam_from_h5
from metapang.core.index.dbg import MetagraphCLI
from metapang.core.index.dbg import MetagraphBuildPipeline, MetagraphBuildPipelineOptions
from metapang.utils.io import get_files_from_directory, get_files_from_fof, FASTA_GLOB, is_fastx
from metapang.core.graph import PWGraph

click.rich_click.OPTION_GROUPS["metapang index pangenome"] = [
    {
        "name": "Required",
        "options": [
            "--pangenome", "--genomes", "--name", "--output"
        ]
    },
    {
        "name": "Options",
        "options": [
            "--tmp", "--genome-name-from-parent-dir", "--threads", "--help"
        ]
    },
    {
        "name": "Advanced",
        "options": [
            "--kmer-size", "--annotation-type", "--filter"
        ]
    }
]

def as_fasta(input_files: list[str], temp_dir: Path, use_parent: bool=False) -> list[str]:
    """Return the input files as fasta paths, converting non-fastx files as needed."""
    from metapang.utils.io import gbff_to_fasta

    res = []
    out_dir = temp_dir.absolute() / "genomes_fasta"
    os.makedirs(out_dir, exist_ok=True)

    for file in input_files:
        if is_fastx(file):
            res.append(file)
        else:
            out_fasta = out_dir / f"{Path(file).name if not use_parent else Path(file).parent.name}.fa"
            mp_log.warning(f"Converting '{Path(file).parent.name}/{Path(file).name}' to fasta: '{out_fasta.parent.name}/{out_fasta.name}'")
            gbff_to_fasta(file, out_fasta)
            res.append(str(out_fasta))
    return res

def construct_pwg(pangenome: Path, output_directory: Path, name: str):
    """Build and save the graph_tool representation of a pangenome."""
    with timer() as t:
        mp_log.info(f"Constructing graph_tool graph from '{pangenome}'")
        pg = PWGraph(pangenome)
        out = output_directory / f"{name}.gt"
        pg.save(out)
        mp_log.info(f"Done - {t.format()}")

def prepare_pipeline_input(pangenome, genomes, name: str, temp_dir: Path, filter: str, genome_name_from_parent_dir: bool):
    """Extract pangenome sequences and gather genome fasta inputs for the build pipeline."""
    mp_log.info(f"Input genomes: '{genomes}'")

    with timer() as t:
        mp_log.info(f"Extracting sequences from '{pangenome}' (partition='{filter}')")
        output_path = temp_dir / f"{name}.fa"
        pg_fam_from_h5(pangenome, output_path, compress=False, split=False, filter=filter)
        mp_log.info(f"Done - {t.format()}")

    if genomes.is_file():
        pipeline_input = get_files_from_fof(genomes, path_type=str)
    else:
        pipeline_input = get_files_from_directory(genomes, glob=FASTA_GLOB, path_type=str, recursive=True)

    pipeline_input = as_fasta(pipeline_input, temp_dir, use_parent=genome_name_from_parent_dir)

    annotation_input = [temp_dir / f"{name}.fa"]

    return pipeline_input, annotation_input

@click.command()
@click.option(
    "--pangenome", "-p",
    type=click.Path(path_type=Path, exists=True, readable=True), required=True,
    help="Path to the pangenome file (.h5)."
)
@click.option(
    "--output", "-o",
    type=click.Path(dir_okay=True, path_type=Path, writable=True), required=True,
    help="Path to output directory"
)
@click.option(
    "--name", "-n", required=True,
    type=str,
    help="Name of the pangenome to index"
)
@click.option(
    "--kmer-size", "-k",
    type=int,
    help="K-mer size to use for indexing __placeholder__."
)
@click.option(
    "--annotation-type", "-a",
    type=click.Choice(["rainbowfish", "rd_brwt", "rd_sparse"]),
    help="""
        \b
        Data-structure used for graph annotation __placeholder__.\n
        \b
        ▪ Available options, by query time perf (at the cost of index size):
            - [bold]rainbowfish[/]
            - [bold]rd_brwt[/]
            - [bold]rd_sparse[/]
        \b
        ▪ See [link=https://metagraph.ethz.ch/static/docs/quick_start.html#annotate-graph]Metagraph annotation[/] for details.
    """
)
@click.option(
    "--threads", "-t",
    type=int,
    help="Number of threads to use __placeholder__."
)
@click.option(
    "--tmp", "-d",
    type=click.Path(dir_okay=True, path_type=Path, writable=True),
    help="Temporary directory for intermediate files __placeholder__."
)
@click.option(
    "--filter", "-f",
    type=click.Choice(["persistent", "shell", "cloud", "all"]),
    help="Pangenome partition filter __placeholder__.",
)
@click.option(
    "--genome-name-from-parent-dir",
    is_flag=True, default=False,
    help="Use the parent directory name as genome name instead of the file name __placeholder__.",
)
@click.option(
    "--genomes", "-g",
    type=click.Path(path_type=Path, exists=True, readable=True), required=True,
    help="""
        \b
        File of files or a directory path.\n
        \b
        > A file of files with one genome path per line:
            [bold]genome_1.\\[fna|fa|fasta|gbff]\\[.gz][/]
            [bold]genome_2.\\[fna|fa|fasta|gbff]\\[.gz][/]
        \b
        > A directory path containing genome files:
            [bold]genome_directory/[/]
            ├── [bold]genome_1.\\[fna|fa|fasta|gbff]\\[.gz][/]
            └── [bold]genome_2.\\[fna|fa|fasta|gbff]\\[.gz][/]
    """
)
@click.option(
    "--construct-graph",
    is_flag=True, default=False,
    help="Construct the graph_tool graph representation"
)
def pangenome(pangenome: Path, name: str, output: Path,
              kmer_size: int, annotation_type: str, threads: int,
              tmp: Path, filter: str,
              genome_name_from_parent_dir: bool, genomes: Path, construct_graph: bool) -> None:
    """
    [bold]Index a pangenome as a colored DBG (using [link=https://metagraph.ethz.ch/static/docs/index.html]Metagraph[/]).[/]

    The graph is built from all the reference sequences (using --genomes).
    Each k-mer in the graph is annotated with families ID that it belongs to.
    """

    with timer() as tt:
        metagraph = MetagraphCLI()

        temp_dir = tmp / name
        os.makedirs(temp_dir, exist_ok=True)
        temp_dir = temp_dir.absolute()
        os.makedirs(output, exist_ok=True)

        mp_log.info(f"Starting indexing of '{name}'")

        if construct_graph:
            construct_pwg(pangenome, output, name)

        pipeline_input, annotation_input = prepare_pipeline_input(
            pangenome,
            genomes,
            name,
            temp_dir,
            filter,
            genome_name_from_parent_dir
        )

        pipeline = MetagraphBuildPipeline(metagraph)

        options = MetagraphBuildPipelineOptions(
            inputs=pipeline_input,
            annotation_inputs=annotation_input,
            name=name,
            tmp_dir=str(temp_dir),
            output_dir=str(output / name),
            kmer_size=kmer_size,
            parallel=threads,
            anno_header=True,
            annotation_type=annotation_type,
        )

        mp_log.info("Constructing family annotated DBG...")
        pipeline.run(options, move_graph=False)

        options.annotation_inputs = pipeline_input
        options.anno_filename = True
        options.anno_header = False
        options.suffix="_genomes"

        mp_log.info("Constructing genome annotated DBG...")
        pipeline.run(options, skip_graph=True, move_graph=True)


    mp_log.info(f"Indexing done, outputs are available at '{output / name}'")
    mp_log.info(f"Total time: {tt.format()}")
