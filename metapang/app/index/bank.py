import sys
from typing import List
from pathlib import Path
from itertools import chain

import rich_click as click

from metapang.logger import mp_log
from metapang.utils.time import timer
from metapang.exceptions import MetaPanG_IoError
from metapang.core.index.index import IndexBuilder, IndexBuildConfig

click.rich_click.OPTION_GROUPS["metapang index bank"] = [
    {
        "name": "Required",
        "options": [
            "--input", "--output"
        ]
    },
    {
        "name": "Options",
        "options": [
            "--kmer-size", "--scaled", "--nb-hash", "--threads", "--help"
        ]
    }
]

def check_path_exists(parent: str, paths: List[Path]):
    """Exit with an error if any of the given paths does not exist."""
    for path in paths:
        if not path.exists():
            mp_log.error(f"Path '{path}' does not exist (from: '{parent}')")
            sys.exit(1)

def search_input_files(input_path: str) -> list[tuple[str, list[str]]]:
    """Collect (pangenome_id, genome files) pairs from an input directory or TSV file."""
    pangenomes = []
    if input_path.is_dir():
        mp_log.info(f"Searching input files in directory '{input_path}'")
        for path in input_path.iterdir():
            if path.is_dir():
                fna = list(chain.from_iterable(path.rglob(ext) for ext in ["*.fna*", "*.fa*", "*.fasta*", "*.gb*", "*.gbff*"]))
                if not fna:
                    mp_log.warning(f"No fasta files found in '{path}', skipped")
                    continue
                pangenomes.append((path.name, fna))
    else:
        mp_log.info(f"Parsing input file '{input_path}'")
        idx = set()
        with open(input_path) as f:
            for n, line in enumerate(f):
                line = line.strip().split()
                if len(line) < 2:
                    raise MetaPanG_IoError(f"Invalid line in TSV file at line {n + 1} in {input_path}: '{line}'")
                if line[0] not in idx:
                    pangenomes.append((line[0], [Path(f) for f in line[1:]]))
                    check_path_exists(line[0], pangenomes[-1][1])
                    idx.add(line[0])
                else:
                    raise MetaPanG_IoError(f"Duplicate pangenome id '{line[0]}' at line {n + 1} in '{input_path}'")
    return pangenomes

@click.command()
@click.option(
    "--input", "-i",
    type=click.Path(exists=True), required=True,
    help=f"""
        \b
        Input directory or TSV file\n
        \b
        > A TSV file (space-separated) with the following format:
            [bold]pangenome_id_1[/] [i]genome_1.\\[fna|fa|fasta|gb|gbff]\\[.gz] genome_2.\\[fna|fa|fasta|gb|gbff][.gz][/] ...
            [bold]pangenome_id_2[/] [i]genome_1.\\[fna|fa|fasta|gb|gbff]\\[.gz] genome_2.\\[fna|fa|fasta|gb|gbff][.gz][/] ...
        \b
        > A path to a directory with the following structure:
            [bold]directory/[/]
            ├── [bold]pangenome_1/[/]
            │   ├── [i]genome_1.\\[fna|fa|fasta|gb|gbff]\\[.gz][/]
            │   └── [i]genome_2.\\[fna|fa|fasta|gb|gbff]\\[.gz][/]
            └── [bold]pangneome_2/[/]
                ├── [i]genome_1.\\[fna|fa|fasta|gb|gbff]\\[.gz][/]
                └── [i]genome_2.\\[fna|fa|fasta|gb|gbff]\\[.gz][/]
        
    """
)
@click.option(
    "--output", "-o",
    type=click.Path(), required=True,
    help="Output directory"
)
@click.option(
    "--kmer-size", "-k",
    type=int,
    help="Size of k-mers __placeholder__.",
)
@click.option(
    "--scaled", "-s",
    type=int,
    help="Scaled factor, ignored when --nb-hash is used __placeholder__.",
)
@click.option(
    "--nb-hash", "-n",
    type=int,
    help="Number of hash to sample __placeholder__.",
)
@click.option(
    "--genome-name-from-parent-dir", "-d",
    is_flag=True, default=False,
    help="Use the parent directory name as genome name instead of the file name __placeholder__.",
)
@click.option(
    "--threads", "-t",
    type=int,
    help="Number of threads to use for indexing __placeholder__.",
)
def bank(input, output, kmer_size, scaled, nb_hash, genome_name_from_parent_dir, threads) -> None:
    """
    [bold]Index a bank of pangenomes[/]
    
    \b
    [bold]Construct 2 sourmash-based indexes:
        - One at the [u]genome level[/u] (genome_index.sbt.zip), with one signature per genome
        - One at the [u]pangenome level[/u] (pangenome_index.sbt.zip), where each signature is a merge of all genome signatures from a pangenome[/]
    """

    with timer("Bank indexing") as t:
        input_path = Path(input)
        pangenomes = search_input_files(input_path)
        mp_log.info(f"Found {len(pangenomes)} pangenomes to index")

        config = IndexBuildConfig(
            kmer_size=kmer_size,
            scaled=scaled,
            n=nb_hash,
            pangenomes=pangenomes,
            output=Path(output),
            use_parent_directory_as_genome_id=genome_name_from_parent_dir
        )

        builder = IndexBuilder(config)

        mp_log.info(f"Index using k={kmer_size}, scaled={scaled}, and nb_hash={nb_hash} ({threads} threads)")
        builder.construct(threads)
        mp_log.info(f"Indexing done in {t.format()}")