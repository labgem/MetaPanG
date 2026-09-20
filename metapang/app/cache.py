import shutil
from collections.abc import Callable
from pathlib import Path

import msgspec
import rich_click as click
from rich.console import Console
from rich.table import Table

from metapang.logger import mp_log
from metapang.pg import compat
from metapang.pg.api import PanGBank_Cache, parse_collection_name_version


def _cache(ctx) -> PanGBank_Cache:
    pangbank = ctx.obj.get("config").pangbank
    override = ctx.obj.get("cache_path")
    if override is not None:
        pangbank = msgspec.structs.replace(pangbank, cache_directory=str(override))
    return PanGBank_Cache(pangbank)


def _dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def _human(n: int) -> str:
    size = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PiB"


def _dbg_complete(dbg_dir: Path) -> bool:
    name = dbg_dir.name
    required = [
        f"{name}.dbg",
        f"{name}.family.row_diff_brwt.annodbg",
        f"{name}.genome.row_diff_brwt.annodbg",
        f"{name}.gt",
    ]
    return all((dbg_dir / f).exists() for f in required)


@click.group()
@click.option(
    "--path",
    "cache_path",
    type=click.Path(path_type=Path),
    help="Override the cache directory for this command __placeholder__",
)
@click.pass_context
def cache(ctx, cache_path) -> None:
    """
    [bold]Manage the PanGBank download cache[/]
    """
    if cache_path is not None:
        ctx.obj["cache_path"] = cache_path


@cache.command()
@click.pass_context
def path(ctx) -> None:
    """Print the cache directory."""
    click.echo(str(_cache(ctx).directory))


@cache.command(name="list")
@click.pass_context
def list_(ctx) -> None:
    """List cached collections and their contents."""
    store = _cache(ctx)
    root = store.collection_directory
    console = Console()

    if not root.exists() or not any(root.iterdir()):
        console.print(f"Cache is empty ({store.directory})")
        return

    table = Table("collection", "version", "item", "kind", "status", "size")
    for coll in sorted(p for p in root.iterdir() if p.is_dir()):
        for ver in sorted(p for p in coll.iterdir() if p.is_dir()):
            if (ver / "bank_index").exists():
                table.add_row(
                    coll.name,
                    ver.name,
                    "bank_index",
                    "index",
                    "-",
                    _human(_dir_size(ver / "bank_index")),
                )
            pangenomes = ver / "pangenomes"
            if pangenomes.exists():
                for h5 in sorted(pangenomes.glob("*.h5")):
                    table.add_row(
                        coll.name,
                        ver.name,
                        h5.stem,
                        "pangenome",
                        "-",
                        _human(h5.stat().st_size),
                    )
            dbg = ver / "dbg"
            if dbg.exists():
                for d in sorted(p for p in dbg.iterdir() if p.is_dir()):
                    status = "complete" if _dbg_complete(d) else "partial"
                    table.add_row(
                        coll.name, ver.name, d.name, "dbg", status, _human(_dir_size(d))
                    )
    console.print(table)
    console.print(f"Total: {_human(_dir_size(store.directory))}  ({store.directory})")


@cache.command()
@click.argument("target", required=False)
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@click.pass_context
def clear(ctx, target, yes) -> None:
    """
    Remove the whole cache, or a specific collection[@version][:name].

    \b
    Examples:
      metapang cache clear
      metapang cache clear GTDB_refseq
      metapang cache clear GTDB_refseq@2.0.0
      metapang cache clear GTDB_refseq@2.0.0:s__Abiotrophia_defectiva
    """
    store = _cache(ctx)

    if target is None:
        to_remove = [store.directory]
        label = f"the entire cache ({store.directory})"
    else:
        name, version, pangenome = parse_collection_name_version(target)
        base = store.collection_directory / name
        if version != "latest":
            base = base / version

        if pangenome:
            if version == "latest":
                raise click.UsageError(
                    "clearing a single pangenome needs an explicit version, "
                    "e.g. GTDB_refseq@2.0.0:name"
                )
            to_remove = [
                base / "pangenomes" / f"{pangenome}.h5",
                base / "dbg" / pangenome,
            ]
            label = f"'{pangenome}' from {name}@{version}"
        else:
            to_remove = [base]
            label = name if version == "latest" else f"{name}@{version}"

    existing = [p for p in to_remove if p.exists()]
    if not existing:
        click.echo("Nothing to remove.")
        return

    if not yes and not click.confirm(f"Remove {label}?"):
        click.echo("Aborted.")
        return

    for p in existing:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
    click.echo(f"Removed {label}.")


def _remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


@cache.command()
@click.argument("target")
@click.option(
    "--index/--no-index", "do_index", default=True, help="Fetch the release bank index."
)
@click.option(
    "--dbg/--no-dbg",
    "do_dbg",
    default=True,
    help="Fetch the de Bruijn graph of each named species.",
)
@click.option(
    "--pangenome/--no-pangenome",
    "do_pangenome",
    default=True,
    help="Fetch the .h5 pangenome of each named species.",
)
@click.option("--force", "-f", is_flag=True, help="Re-download even if already cached.")
@click.pass_context
def fetch(ctx, target, do_index, do_dbg, do_pangenome, force) -> None:
    """
    Populate the cache.

    \b
    TARGET is collection[@version][:species[,species,...]].
      - without :species, the release bank index is fetched
      - with :species, each species graph is also fetched

    \b
    Examples:
      metapang cache fetch GTDB_refseq@2.0.0
      metapang cache fetch GTDB_refseq@2.0.0:s__Abiotrophia_defectiva
      metapang cache fetch GTDB_refseq@2.0.0:s__A,s__B --no-index
    """
    store = _cache(ctx)
    api = store.api

    name, version, pangenomes = parse_collection_name_version(target)
    species = [s.strip() for s in pangenomes.split(",")] if pangenomes else []
    species = [s for s in species if s]

    compat.check_supported(name, version)

    release = api.get_collection(name, version)
    proxy = store.proxy(release)

    unknown = [s for s in species if not api.has_pangenome(release, s)]
    if unknown:
        raise click.ClickException(
            f"Unknown species in {release.full_name}: {', '.join(unknown)}"
        )

    plan: list[tuple[str, Path, Callable[[], object], Callable[[], object]]] = []
    if do_index:
        plan.append(
            ("bank_index", store.index_path(release), proxy.has_index, proxy.get_index)
        )
    for s in species:
        if do_dbg:
            plan.append(
                (
                    f"{s} (dbg)",
                    store.dbg_path(release, s),
                    lambda s=s: proxy.has_dbg(s),
                    lambda s=s: proxy.get_dbg(s),
                )
            )
        if do_pangenome:
            plan.append(
                (
                    f"{s} (pangenome)",
                    store.pangenome_path(release, s),
                    lambda s=s: proxy.has_pangenome(s),
                    lambda s=s: proxy.get_pangenome(s),
                )
            )

    if not plan:
        click.echo("Nothing to fetch (no index and no species selected).")
        return

    mp_log.info(f"Fetching {len(plan)} artifact(s) for {release.full_name}")
    fetched, present, failed = [], [], []
    for label, path, has_fn, get_fn in plan:
        if force:
            _remove(path)
        elif has_fn():
            mp_log.info(f"present: {label}")
            present.append(label)
            continue
        try:
            get_fn()
            mp_log.info(f"fetched: {label}")
            fetched.append(label)
        except Exception as e:
            mp_log.error(f"failed: {label}: {e}")
            failed.append(label)

    click.echo(
        f"Done: {len(fetched)} fetched, {len(present)} already present, "
        f"{len(failed)} failed."
    )
    if failed:
        raise click.ClickException(f"Failed to fetch: {', '.join(failed)}")
