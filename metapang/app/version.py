import rich_click as click
from metapang import __version__ as metapang_version

@click.command()
@click.option(
    "--no-prefix", "-p", is_flag=True,
    help="Show only numbers"
)
@click.option(
    "--no-name", "-n", is_flag=True,
    help="Show version only"
)
def version(no_prefix, no_name) -> None:
    """
    [bold]Display MetaPanG version[/]
    """
    name = "MetaPanG " if not no_name else ""
    prefix = "v" if not no_prefix else ""

    click.echo(f"{name}{prefix}{metapang_version}")
