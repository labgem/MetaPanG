import rich_click as click
from metapang import __version__ as metapang_version, __commit__ as metapang_commit

@click.command()
@click.option(
    "--no-prefix", "-p", is_flag=True,
    help="Show only numbers"
)
@click.option(
    "--no-name", "-n", is_flag=True,
    help="Show version only"
)
@click.option(
    "--with-commit", "-c", is_flag=True,
    help="Append the git commit MetaPanG was built from"
)
def version(no_prefix, no_name, with_commit) -> None:
    """
    [bold]Display MetaPanG version[/]
    """
    name = "MetaPanG " if not no_name else ""
    prefix = "v" if not no_prefix else ""
    commit = f" ({metapang_commit})" if with_commit and metapang_commit else ""

    click.echo(f"{name}{prefix}{metapang_version}{commit}")
