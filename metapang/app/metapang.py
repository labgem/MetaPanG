import sys
from collections import defaultdict
from pathlib import Path

import msgspec
import rich_click as click

from metapang import __version__ as metapang_version
from metapang.app.cache import cache
from metapang.app.checkhealth import checkhealth
from metapang.app.configure import configure
from metapang.app.index import index
from metapang.app.issue import issue
from metapang.app.list import list_
from metapang.app.profile import profile
from metapang.app.search import search
from metapang.app.tools import tools
from metapang.app.version import version
from metapang.config import configuration
from metapang.logger import metapang_setup_logger, mp_log

click.rich_click.TEXT_MARKUP = "rich"


def check_for_new_version() -> str:
    """Query GitHub for the latest release and report whether MetaPanG is up to date."""
    try:
        import semver
        from github import Github

        g = Github(timeout=0, retry=0)
        repo = g.get_repo("LABGeM/MetaPanG")
        latest_tag = repo.get_latest_release().tag_name
        if semver.compare(latest_tag, metapang_version) > 0:
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
    repo = "https://github.com/LABGeM/MetaPanG"
    pangbank = "https://pangbank.genoscope.cns.fr"
    return (
        f"[b]MetaPanG[/] [dim]v{metapang_version}[/] - [link={repo}]{repo}[/]\n\n"
        f"PanGBank - [link={pangbank}]{pangbank}[/]\n\n"
        f"Issues - [link={repo}/issues]{repo}/issues[/]"
    )


click.rich_click.COMMAND_GROUPS = {
    "metapang": [
        {
            "name": "Main command",
            "commands": [
                "profile",
            ],
        },
        {
            "name": "Data",
            "commands": ["list", "cache"],
        },
        {
            "name": "Setup",
            "commands": ["configure", "checkhealth"],
        },
        {
            "name": "About",
            "commands": ["version", "issue"],
        },
        {
            "name": "Advanced",
            "commands": [
                "search",
                "index",
                "tools",
            ],
        },
    ],
    "metapang cache": [
        {
            "name": "Commands",
            "commands": ["list", "path", "fetch", "clear"],
        },
    ],
}

click.rich_click.OPTION_GROUPS = {
    "metapang profile": [
        {
            "name": "Input / output",
            "options": [
                "--pangbank",
                "--output",
                "--threads",
                "--metagraph-path",
            ],
        },
        {
            "name": "Options",
            "options": ["--stop-rule", "--k-max"],
        },
        {
            "name": "Advanced options",
            "options": [
                "--merge-jaccard",
                "--cv-folds",
                "--cv-min-gain",
                "--refine-ra",
                "--impute-min-frac",
                "--reassign-max-residual",
            ],
        },
    ]
}

click.rich_click.MAX_WIDTH = None
click.rich_click.STYLE_OPTIONS_TABLE_LEADING = 1
click.rich_click.STYLE_OPTIONS_TABLE_BOX = "SIMPLE"

METAPANG_CONTEXT = dict(default_map=defaultdict(dict))


def fill_help_placeholder(command, param_name, default) -> None:
    """Replace `__placeholder__` in a command option's help with its default value."""
    if command is None:
        return
    for param in command.params:
        if (
            isinstance(param, click.Option)
            and param.name == param_name
            and param.help
            and "__placeholder__" in param.help
        ):
            msg = f"[gray42]\\[default: {default}][/]"
            param.help = param.help.replace("__placeholder__", msg)


def configure_help_and_defaults(command, config, sources, def_map):
    """Recursively apply config defaults and expand help placeholders on CLI commands."""
    for sub in command.commands.values():
        command_name = sub.name.replace("-", "_")
        if (
            isinstance(sub, click.Group)
            and command_name in sources
            and command_name in config
        ):
            if command_name not in def_map:
                def_map[command_name] = {}
            configure_help_and_defaults(
                sub,
                config[command_name],
                sources[command_name],
                def_map[command_name],
            )
        for param in sub.params:
            if command_name in config and param.name in config[command_name]:
                if command_name not in def_map:
                    def_map[command_name] = {}
                def_map[command_name][param.name] = config[command_name][param.name]
            if (
                isinstance(param, click.Option)
                and param.help
                and "__placeholder__" in param.help
            ):
                if command_name in sources and param.name in sources[command_name]:
                    msg = f"[gray42]\\[default: {sources[command_name][param.name]}][/]"
                    param.help = param.help.replace("__placeholder__", msg)
                param.help = param.help.replace("__placeholder__", "")


@click.group(epilog=metapang_epilog(), context_settings=METAPANG_CONTEXT)
@click.option("--config", "-c", type=click.Path(), help="Path to metapang config file")
@click.option("--log-file", "-l", type=click.Path(), help="Path to log file")
@click.option(
    "--verbosity",
    "-v",
    type=click.Choice(["trace", "debug", "info", "warning", "error", "critical"]),
    default="info",
    show_default=True,
    help="Set verbosity",
)
@click.version_option(message=f"MetaPanG v{metapang_version}", package_name="metapang")
@click.pass_context
def metapang(ctx, config: str | None, log_file: str | None, verbosity: str) -> None:
    """
    [bold]Metagenomic classification using pangenome graphs[/]
    """
    metapang_setup_logger(level=verbosity.upper(), log_file=log_file)
    cfg, sources = configuration(Path(config) if config else None)
    fill_help_placeholder(
        ctx.command.commands.get("cache"),
        "cache_path",
        cfg.pangbank.cache_directory,
    )
    configure_help_and_defaults(
        ctx.command,
        msgspec.to_builtins(cfg)["commands"],
        sources["commands"],
        ctx.default_map,
    )

    ctx.obj = {}
    ctx.obj["config"] = cfg
    ctx.obj["sources"] = sources
    ctx.obj["config_path"] = config


metapang.add_command(version)
metapang.add_command(profile)
metapang.add_command(index)
metapang.add_command(search)
metapang.add_command(tools)
metapang.add_command(configure)
metapang.add_command(checkhealth)
metapang.add_command(issue)
metapang.add_command(cache)
metapang.add_command(list_)
