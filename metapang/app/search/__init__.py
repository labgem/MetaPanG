import rich_click as click

from metapang.app.search.bank import bank
from metapang.app.search.pangenome import pangenome


@click.group()
def search() -> None:
    """
    [bold]Search a genome into a genome/pangenome index[/]
    """
    pass


search.add_command(bank)
search.add_command(pangenome)
