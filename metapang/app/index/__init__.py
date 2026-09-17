import rich_click as click

from metapang.app.index.bank import bank
from metapang.app.index.pangenome import pangenome

@click.group()
def index() -> None:
    """
    [bold]MetaPanG index construction[/]
    """

index.add_command(bank)
index.add_command(pangenome)