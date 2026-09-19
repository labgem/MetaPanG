import rich_click as click

from metapang.config import configuration_schema, configuration_template
from metapang.utils.io import smart_io


@click.command()
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json", "yaml", "toml"], case_sensitive=False),
    help="Output format __placeholder__",
)
@click.option(
    "--output",
    "-o",
    type=str,
    help="Path to output file __placeholder__",
)
@click.option(
    "--schema",
    "-s",
    is_flag=True,
    help="Output schema instead of template __placeholder__",
)
def template(format: str, output: str, schema: bool = False) -> None:
    """
    [bold]Dump configuration template and schema[/]
    """
    with smart_io(output) as out:
        if schema:
            out.write(configuration_schema())
        else:
            out.write(configuration_template(format))
