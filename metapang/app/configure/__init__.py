import rich_click as click

from metapang.app.configure.edit import edit
from metapang.app.configure.show import show
from metapang.app.configure.template import template


@click.group()
def configure() -> None:
    """
    [bold]MetaPanG configuration[/]

    [bold]MetaPanG use a cascading configuration system, [i]i.e.[/] the configuration\n
    can be defined at different levels, and each level overrides the previous one.[/]\n\n

    Various format are supported for configuration files, including: TOML, JSON, and YAML.\n
    \n
    The configuration levels are:\n
    - [bold]system[/]: Located at ~/.config/metapang-config.*\n
    - [bold]local[/]: Located at .metapang-config.* in the current working directory.\n
    - [bold]cli[/]: Path passed to main MetaPanG command, metapang --config /path/to/config.*.\n
    - [bold]environment[/]: Environment variables, using METAPANG_CMD_SUBCMD_PARAM=X.\n
    - [bold]option[/]: Command line options, using --param X.\n
    \n

    Use '[i]metapang configure show -s[/]' to show the current state of the configuration,\n
    including the source of each value (system, env, ...)
    """


configure.add_command(template)
configure.add_command(show)
configure.add_command(edit)
