import rich_click as click

from metapang.app.tools.pg_dump import pg_dump


@click.group()
def tools() -> None:
    """
    [bold]MetaPanG tools[/]
    """
    pass


tools.add_command(pg_dump)
