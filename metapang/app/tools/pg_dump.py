import logging
from pathlib import Path
import rich_click as click

from metapang.logger import mp_log
from metapang.pg.dump import pg_gene_from_h5, pg_repr_from_h5, pg_fam_from_h5


@click.group()
def pg_dump():
    """
    [bold]Dump sequences from PPanGGoLiN pangenome file[/]
    """
    pass


@click.command()
@click.argument("pangenome", type=click.Path(exists=True))
@click.option(
    "--output", "-o", type=click.Path(), required=True, help="Output fasta file"
)
@click.option(
    "--compress", "-c", is_flag=True, help="Compress output (gzip) __placeholder__"
)
@click.option(
    "--filter",
    "-f",
    type=click.Choice(["persistent", "shell", "cloud", "all"]),
    help="Partition filter __placeholder__",
)
def genes(pangenome, compress, filter, output) -> None:
    """
    [bold]Dump gene sequences from ppanggolin pangenome file[/]
    """
    pangenome = Path(pangenome)
    output = Path(output)
    logging.getLogger("PPanGGoLiN").setLevel(logging.ERROR)
    mp_log.info(f"Dumping all gene sequences with filter '{filter}'")
    pg_gene_from_h5(pangenome, output, compress, filter)
    mp_log.info(f"Gene sequences dumped to {output}")


@click.command()
@click.argument("pangenome", type=click.Path(exists=True))
@click.option(
    "--output", "-o", type=click.Path(), required=True, help="Output fasta file"
)
@click.option(
    "--compress", "-c", is_flag=True, help="Compress output (gzip) __placeholder__"
)
@click.option(
    "--filter",
    "-f",
    type=click.Choice(["persistent", "shell", "cloud", "all"]),
    help="Partition filter __placeholder__",
)
def reprs(pangenome, compress, filter, output) -> None:
    """
    [bold]Dump representative sequences from ppanggolin pangenome file[/]
    """
    pangenome = Path(pangenome)
    output = Path(output)
    logging.getLogger("PPanGGoLiN").setLevel(logging.ERROR)

    mp_log.info(f"Dumping representative familiy sequences with filter '{filter}'")
    pg_repr_from_h5(pangenome, output, compress, filter)
    mp_log.info(f"Representative sequences dumped to {output}")


@click.command()
@click.argument("pangenome", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    required=True,
    help="Output fasta file or directory if --split is used",
)
@click.option(
    "--filter",
    "-f",
    type=click.Choice(["persistent", "shell", "cloud", "all"]),
    help="Partition filter __placeholder__",
)
@click.option(
    "--compress", "-c", is_flag=True, help="Compress output (gzip) __placeholder__"
)
@click.option(
    "--split",
    "-s",
    is_flag=True,
    help="Split output, one fasta file per family __placeholder__",
)
def fams(pangenome, compress, filter, output, split) -> None:
    """
    [bold]Dump familiy sequences from PPanGGoLiN pangenome file[/]
    """
    pangenome = Path(pangenome)
    output = Path(output)
    logging.getLogger("PPanGGoLiN").setLevel(logging.ERROR)
    mp_log.info(f"Dumping family sequences with filter '{filter}'")
    pg_fam_from_h5(pangenome, output, compress, split, filter)
    mp_log.info(f"Family sequences dumped to {output}")


pg_dump.add_command(genes)
pg_dump.add_command(reprs)
pg_dump.add_command(fams)

