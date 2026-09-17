import rich_click as click

from metapang.logger import metapang_setup_logger, mp_log
from metapang import __version__ as metapang_version
from metapang.app.version import version
from metapang.app.index import index
from metapang.app.tools import tools
from metapang.app.search import search
from metapang.app.configure import configure
from metapang.app.profile import profile
from metapang.app.checkhealth import checkhealth

from metapang.config import configuration
from collections import defaultdict

import sys
import signal
import msgspec

click.rich_click.USE_RICH_MARKUP = True

def check_for_new_version() -> str:
    """Query GitHub for the latest release and report whether MetaPanG is up to date."""
    try:
        from github import Github
        import semver
        g = Github(timeout=0, retry=0)
        repo = g.get_repo("LABGeM/MetaPanG")
        latest_tag = repo.get_latest_release().tag_name
        if semver.parse(latest_tag) > semver.parse(metapang_version):
            return f"(⚠️ Latest version is '{latest_tag}')"
        return "(✅ up-to-date)"
    except Exception:
        return ""

def signal_interrupt_handler(signal, _):
    """Log the interrupting signal and exit with a non-zero status."""
    mp_log.error(f"Interrupted by user ({signal})")
    sys.exit(1)

def metapang_epilog() -> str:
    """Return the CLI help epilog with version and project links."""
    return f"""
    ---\n
    MetaPanG v{metapang_version}\n
    Github: [link=https://github.com/LABGeM/MetaPanG]LABGeM/MetaPanG[/]\n
    Documentation: [link=https://github.com/LABGeM/MetaPanG]MetaPanG[/]\n
    Issues: [link=https://github.com/LABGeM/MetaPanG/issues]MetaPanG/issues[/]\n
    ---\n
    """

click.rich_click.COMMAND_GROUPS = {
    "metapang": [
        {
            "name": "Main command",
            "commands": [
                "profile",
            ]
        },
        {
            "name": "Advanced commands",
            "commands": [
                "search",
                "index",
                "tools",
            ]
        },
        {
            "name": "Utilities",
            "commands": [
                "configure",
                "version",
                "checkhealth"
            ]
        }
    ]
}

click.rich_click.OPTION_GROUPS = {
    "metapang profile": [
        {
            "name": "Input / output",
            "options": ["--query", "--pangbank", "--output", "--threads"],
        },
        {
            "name": "Options",
            "options": ["--stop-rule", "--k-max"],
        },
        {
            "name": "Advanced options",
            "options": [
                "--merge-jaccard", "--cv-folds", "--cv-min-gain", "--refine-ra",
                "--impute-min-frac", "--reassign-max-residual",
            ],
        },
    ]
}

click.rich_click.MAX_WIDTH = None
click.rich_click.STYLE_OPTIONS_TABLE_LEADING = 1
click.rich_click.STYLE_OPTIONS_TABLE_BOX = "SIMPLE"

METAPANG_CONTEXT = dict(
    default_map = defaultdict(dict)
)

def configure_help_and_defaults(command, config, sources, def_map):
    """Recursively apply config defaults and expand help placeholders on CLI commands."""
    for command in command.commands.values():
        command_name = command.name.replace("-", "_")
        if isinstance(command, click.Group) and command_name in sources and command_name in config:
            if command_name not in def_map:
                def_map[command_name] = {}
            configure_help_and_defaults(command, config[command_name], sources[command_name], def_map[command_name])
        for param in command.params:
            if command_name in config and param.name in config[command_name]:
                if command_name not in def_map:
                    def_map[command_name] = {}
                def_map[command_name][param.name] = config[command_name][param.name]
            if hasattr(param, "help") and param.help and "__placeholder__" in param.help:
                if command_name in sources and param.name in sources[command_name]:
                    msg = f"[gray42]\\[default: {sources[command_name][param.name]}][/]"
                    param.help = param.help.replace("__placeholder__", msg)
                param.help = param.help.replace("__placeholder__", "")

@click.group(epilog=metapang_epilog(), context_settings=METAPANG_CONTEXT)
@click.option(
    "--config", "-c",
    type=click.Path(),
    help="Path to metapang config file"
)
@click.option(
    "--log-file", "-l",
    type=click.Path(),
    help="Path to log file"
)
@click.option(
    "--verbosity", "-v",
    type=click.Choice(["trace", "debug", "info", "warning", "error", "critical"]), default="info", show_default=True,
    help="Set verbosity",
)
@click.version_option(message=f"MetaPanG v{metapang_version}", package_name="metapang")
@click.pass_context
def metapang(ctx, config: str | None, log_file: str | None, verbosity: str) -> None:
    """
    [bold]Metagenomic classification using pangenome graphs[/]
    """
    metapang_setup_logger(level=verbosity.upper(), log_file=log_file)
    config, sources = configuration(config or None)
    configure_help_and_defaults(ctx.command, msgspec.to_builtins(config)["commands"], sources["commands"], ctx.default_map)

    ctx.obj = {}
    ctx.obj["config"] = config
    ctx.obj["sources"] = sources


metapang.add_command(version)
metapang.add_command(profile)
metapang.add_command(index)
metapang.add_command(search)
metapang.add_command(tools)
metapang.add_command(configure)
metapang.add_command(checkhealth)
