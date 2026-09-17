import msgspec
import rich_click as click

@click.command(context_settings={'show_default': False})
@click.option(
    "--source", "-s",
    is_flag=True,
    help="Include the source of configuration values __placeholder__",
)
@click.option(
    "--format", "-f",
    type=click.Choice(["json", "yaml", "toml"], case_sensitive=False),
    help="Output format __placeholder__")
@click.pass_context
def show(ctx, source: bool, format: str) -> None:
    """
    [bold]Dump the current configuration in stdout[/]
    """
    c = ctx.obj["config"]
    sources = ctx.obj["sources"]
    
    if source:
        match format:
            case "yaml":
                print(msgspec.yaml.encode(sources).decode())
            case "toml":
                print(msgspec.toml.encode(sources).decode())
            case "json":
                print(msgspec.json.format(msgspec.json.encode(sources)).decode())
    else:
        match format:
            case "yaml":
                print(msgspec.yaml.encode(c).decode())
            case "toml":
                print(msgspec.toml.encode(c).decode())
            case "json":
                print(msgspec.json.format(msgspec.json.encode(c)).decode())
