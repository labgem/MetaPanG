import rich_click as click
from rich.console import Console
from rich.table import Table

from metapang.pg import compat
from metapang.pg.api import (
    PanGBank_APIError,
    PanGBank_Cache,
    parse_collection_name_version,
)


def _cache(ctx) -> PanGBank_Cache:
    return PanGBank_Cache(ctx.obj.get("config").pangbank)


def _list_collections(api, console: Console) -> None:
    collections = api.get_collections()
    if not collections:
        console.print("No collections available.")
        return

    table = Table(
        "collection", "version", "pangenomes", "supported", "discarded", "link"
    )
    for coll in sorted(collections, key=lambda c: c.name):
        for release in coll.releases:
            supported = compat.is_supported(coll.name, release.version)
            n_discarded = len(compat.discarded_species(coll.name, release.version))
            url = _web_url(api, release)
            table.add_row(
                coll.name,
                release.version,
                str(release.nb_pangenomes),
                "[green]yes[/]" if supported else "[red]no[/]",
                str(n_discarded) if n_discarded else "-",
                f"[link={url}]{url}[/]",
            )
    console.print(table)


def _web_url(api, release) -> str:
    base = api.url.replace("-api", "", 1)
    return f"{base}/collection/{release.idx}/{release.version}"


def _list_release(api, console: Console, name: str, version: str) -> None:
    release = api.get_collection(name, version)
    supported = compat.is_supported(release.name, release.version)
    console.print(
        f"[bold]{release.full_name}[/]  "
        f"pangenomes: {release.nb_pangenomes}  "
        f"supported: {'[green]yes[/]' if supported else '[red]no[/]'}"
    )
    url = _web_url(api, release)
    console.print(f"Browse species: [link={url}]{url}[/]")

    discarded = compat.discarded_species(release.name, release.version)
    if not discarded:
        console.print("No species discarded by default.")
        return

    console.print(
        f"[yellow]{len(discarded)} species discarded by default "
        "(include with 'metapang profile --include-discarded'):[/]"
    )
    table = Table("discarded species", "reason")
    for species, reason in sorted(discarded.items()):
        table.add_row(species, reason)
    console.print(table)


@click.command(name="list")
@click.argument("collection", required=False)
@click.pass_context
def list_(ctx, collection) -> None:
    """
    List PanGBank collections, or one collection release in detail.

    \b
    Examples:
      metapang list
      metapang list GTDB_refseq
      metapang list GTDB_refseq@2.0.0
    """
    console = Console()
    api = _cache(ctx).api
    try:
        if collection is None:
            _list_collections(api, console)
        else:
            name, version, _ = parse_collection_name_version(collection)
            _list_release(api, console, name, version)
    except PanGBank_APIError as e:
        raise click.ClickException(str(e)) from e
