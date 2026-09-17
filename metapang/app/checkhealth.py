import subprocess

import rich_click as click
from metapang.config import PanGBank_Config
from metapang.pg.api import PanGBank_API
from metapang.utils.execution import find_executable, MetaPanG_MissingTool
from rich.console import Console

check_success = "[[green] ok [/]]"
check_warning = "[[yellow]warn[/]]"

def check_dependencies(tools: list[tuple[str, str, int | None]]) -> list[str]:
    """Check that each external tool is found and executable, returning status messages."""
    res = []
    for tool, req, eret in tools:
        try:
            find_executable(tool)
        except MetaPanG_MissingTool:
            res.append(f"{check_warning} '{tool}' not found. Required by: {req}")
            continue
        res.append(f"{check_success} '{tool}' found.")
        try:
            rc = subprocess.run([tool], capture_output=True).returncode
        except OSError:
            res.append(f"{check_warning} '{tool}' is not executable.")
            continue
        if rc == 0 or (eret is not None and rc == eret):
            res.append(f"{check_success} '{tool}' is executable (retcode={rc}).")
        else:
            res.append(f"{check_warning} '{tool}' is not executable (retcode={rc}).")
    return res


@click.command(context_settings={'show_default': False})
def checkhealth():
    """
    [bold]Check MetaPanG environment[/]
    """
    console = Console(stderr=True)

    console.print("> Checking external dependencies")

    dep_warnings = check_dependencies([
        ("metagraph", "'metapang index pangenome', 'metapang profile'", 255)
    ])

    for w in dep_warnings:
        console.print(w)

    console.print("> Checking external (non pip) library dependencies")
    try:
        import graph_tool.all as gt
        console.print(f"{check_success} 'graph-tool' library found.")
    except ImportError:
        console.print(f"{check_warning} 'graph-tool' library not found. The library is included in the following 'MetaPanG' distribution: bioconda, docker and apptainer. If you use 'MetaPanG' from sources, you need to install 'graph-tool' manually. See https://graph-tool.skewed.de/installation.html for instructions.")


    console.print("> Checking 'PanGBank API' connection")

    c = PanGBank_Config(
        api_endpoint="https://pangbank-api.genoscope.cns.fr",
        with_tty_log=False
    )

    api = PanGBank_API(c)
    try:
        cs = api.get_collections()
        cs = sorted(cs, key=lambda x: len(x.name))
        console.print(f"{check_success} PanGBank API reachable, available collections:")
        for c in cs:
            for r in c.releases:
                console.print(f"- [bold]{c.name}@{r.version}[/] \t (taxonomy: {r.taxonomy} {r.taxonomy_version})")
    except:
        console.print(f"{check_warning} Failed to reach PanGBank API at {api.url}. Required by: 'metapang profile'")


