import io
import os
import platform
import sys
from pathlib import Path

import rich_click as click
from rich.console import Console

from metapang import __commit__ as metapang_commit
from metapang import __version__ as metapang_version
from metapang.app.checkhealth import run_health_checks


def _os_label() -> str:
    machine = platform.machine()
    if sys.platform.startswith("linux"):
        return f"Linux {machine}"
    if sys.platform == "darwin":
        if machine == "arm64":
            return "macOS Apple Silicon (arm64)"
        return f"macOS Intel ({machine})"
    return f"{platform.system()} {machine}"


def _install_label() -> str:
    if Path("/.dockerenv").exists():
        return "Docker"
    if (
        os.environ.get("PIXI_PROJECT_ROOT")
        or f"{os.sep}.pixi{os.sep}envs{os.sep}" in sys.prefix
    ):
        return "pixi"
    if os.environ.get("CONDA_PREFIX"):
        return "conda"
    return "source"


def _code_block(text: str, lang: str = "") -> str:
    return f"```{lang}\n{text.rstrip()}\n```"


def _read(path: Path) -> str | None:
    try:
        return path.read_text()
    except OSError:
        return None


def _parse_toml(text: str) -> dict | None:
    import tomllib

    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None


def _hide_run_toml(data: dict) -> str:
    """Hide private fields (query paths, sample, output, refit dir, metagraph path)."""
    import msgspec

    data = dict(data)
    if "sample" in data:
        data["sample"] = "<sample>"
    if "output" in data:
        data["output"] = "<output>"
    if "refit_from" in data:
        data["refit_from"] = "<refit>"
    if isinstance(data.get("query"), list):
        data["query"] = ["<query file>"] * len(data["query"])
    if "metagraph_path" in data:
        data["metagraph_path"] = (
            "metagraph" if data["metagraph_path"] == "metagraph" else "<custom>"
        )
    return msgspec.toml.encode(data).decode()


def _scrub(text: str, data: dict) -> str:
    """Replace the run query paths, sample and output names found in free text."""
    pairs: list[tuple[str, str]] = []
    query = data.get("query")
    if isinstance(query, list):
        pairs += [(q, "<query file>") for q in query if isinstance(q, str) and q]
    for key, placeholder in (
        ("sample", "<sample>"),
        ("output", "<output>"),
        ("refit_from", "<refit>"),
    ):
        value = data.get(key)
        if isinstance(value, str) and value:
            pairs.append((value, placeholder))
    for value, placeholder in sorted(pairs, key=lambda p: len(p[0]), reverse=True):
        text = text.replace(value, placeholder)
    return text


def _state_summary(path: Path) -> str | None:
    """Human-readable summary of which profile steps completed, from state.pkl."""
    if not path.exists():
        return None
    try:
        import pickle

        with open(path, "rb") as f:
            state = pickle.load(f)
    except Exception as e:
        return f"could not read state: {e}"

    def mark(done: bool) -> str:
        return "done" if done else "pending"

    lines = [
        f"signature:         {mark(getattr(state, '_signature_ok', False))}",
        f"species detection: {mark(getattr(state, '_gen_search_ok', False))}",
    ]
    mapping = getattr(state, "_mapping_ok", {}) or {}
    annotation = getattr(state, "_annotation_ok", {}) or {}
    reads_mapped = getattr(state, "_reads_mapped", {}) or {}
    reads_total = getattr(state, "_reads_total", {}) or {}
    for cand in sorted(set(mapping) | set(annotation)):
        total = reads_total.get(cand)
        reads = f", reads mapped {reads_mapped.get(cand, 0)}/{total}" if total else ""
        lines.append(
            f"- {cand}: mapping {mark(mapping.get(cand, False))}, "
            f"annotation {mark(annotation.get(cand, False))}{reads}"
        )
    return "\n".join(lines)


def _dep_versions() -> list[tuple[str, str]]:
    """Versions of dependencies."""
    versions: list[tuple[str, str]] = []

    try:
        from importlib.metadata import version

        versions.append(("sourmash", version("sourmash")))
    except Exception:
        versions.append(("sourmash", "not found"))

    try:
        import graph_tool

        versions.append(("graph-tool", getattr(graph_tool, "__version__", "unknown")))
    except Exception:
        versions.append(("graph-tool", "not found"))

    try:
        from metapang.core.index.dbg import MetagraphCLI

        versions.append(("metagraph", MetagraphCLI().version()))
    except Exception:
        versions.append(("metagraph", "not found"))

    return versions


@click.command()
@click.argument(
    "output_dir",
    required=False,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Write the report to a file instead of stdout.",
)
def issue(output_dir, output) -> None:
    """
    [bold]Collect environment info as a Markdown bug report[/]

    \b
    Gathers the version, OS, installation method and 'checkhealth' output.
    Pass a 'metapang profile' output directory to also include its 'run.toml'
    and 'logs.txt'.
    """
    console = Console(record=True, width=100, file=io.StringIO())
    run_health_checks(console)
    health = console.export_text()

    commit = f" ({metapang_commit})" if metapang_commit else ""
    dep_lines = [f"- **{name}**: {ver}" for name, ver in _dep_versions()]

    parts = [
        "## MetaPanG issue report",
        "",
        f"- **Version**: MetaPanG v{metapang_version}{commit}",
        f"- **Python**: {platform.python_version()}",
        *dep_lines,
        f"- **OS**: {_os_label()}",
        f"- **Installation**: {_install_label()} (detected, please correct if wrong)",
        "",
        "### metapang checkhealth",
        "",
        _code_block(health),
    ]

    if output_dir is not None:
        run_toml = _read(output_dir / "run.toml")
        data = _parse_toml(run_toml) if run_toml is not None else None

        parts += ["", "### run.toml", ""]
        if run_toml is None:
            parts.append(f"_not found in `{output_dir}`_")
        elif data is None:
            parts.append(_code_block(run_toml, "toml"))
        else:
            parts.append(_code_block(_hide_run_toml(data), "toml"))

        steps = _state_summary(output_dir / "state.pkl")
        parts += ["", "### state.pkl (steps)", ""]
        parts.append(
            _code_block(steps)
            if steps is not None
            else f"_not found in `{output_dir}`_"
        )

        logs = _read(output_dir / "logs.txt")
        parts += ["", "### logs.txt", ""]
        if logs is None:
            parts.append(f"_not found in `{output_dir}`_")
        else:
            if data is not None:
                logs = _scrub(logs, data)
            parts.append(_code_block(logs))

    report = "\n".join(parts) + "\n"

    if output is not None:
        output.write_text(report)
        Console(stderr=True).print(f"Wrote issue report to '{output}'")
    else:
        click.echo(report, nl=False)
