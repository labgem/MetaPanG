from pathlib import Path

import rich_click as click

from metapang.config import (
    METAPANG_CONFIG_DECODERS,
    METAPANG_CONFIG_PATHS,
    configuration_template,
)

_SCOPES = {
    "system": METAPANG_CONFIG_PATHS[0],
    "local": METAPANG_CONFIG_PATHS[1],
}


def _existing(base: Path) -> list[Path]:
    return [
        base.with_suffix(ext)
        for ext in METAPANG_CONFIG_DECODERS
        if base.with_suffix(ext).exists()
    ]


def _create(path: Path, format_: str, scope: str) -> None:
    click.confirm(f"[{scope}] {path} does not exist. Create it?", abort=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(configuration_template(format_))
    click.echo(f"Created {path}")


@click.command()
@click.option(
    "--scope",
    type=click.Choice(["system", "local"]),
    default="local",
    show_default=True,
    help="Which configuration file to edit.",
)
@click.option(
    "--format",
    "-f",
    "format_",
    type=click.Choice(["toml", "json", "yaml"], case_sensitive=False),
    default="toml",
    show_default=True,
    help="Format used if the file must be created.",
)
@click.pass_context
def edit(ctx, scope, format_) -> None:
    """
    Open a configuration file in your editor ($EDITOR).

    Edits the file given with 'metapang --config' if any, otherwise the system or
    local file selected by --scope. If the file does not exist, you are asked
    whether to create it from the template.
    """
    cli_path = ctx.obj.get("config_path") if ctx.obj else None

    if cli_path:
        path = Path(cli_path)
        if not path.exists():
            _create(path, format_, "cli")
    else:
        base = _SCOPES[scope]
        found = _existing(base)
        if len(found) > 1:
            names = ", ".join(str(p) for p in found)
            raise click.ClickException(
                f"Multiple {scope} configuration files exist ({names}); "
                "keep only one, then edit it."
            )
        if found:
            path = found[0]
        else:
            path = base.with_suffix(f".{format_.lower()}")
            _create(path, format_, scope)

    click.edit(filename=str(path))
