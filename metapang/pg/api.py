import json
import typing as tp
from dataclasses import dataclass
from pathlib import Path

import httpx
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from metapang.config import PanGBank_Config
from metapang.exceptions import MetaPanG_Error
from metapang.logger import mp_log_trace
from metapang.utils import parse_version
from metapang.utils.filelock import FileLock


@dataclass(slots=True, frozen=True)
class CollectionRelease:
    """A single versioned release of a PanGBank collection."""

    name: str
    version: str
    latest: bool
    idx: int
    ppanggolin_version: str
    pangbank_wf_version: str
    taxonomy: str
    taxonomy_version: str
    nb_pangenomes: int

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.name}@{self.version}"


@dataclass(slots=True, frozen=True)
class CollectionReleases:
    """All releases of a PanGBank collection, sorted by version."""

    name: str
    releases: list[CollectionRelease]

    @classmethod
    def from_api_response(cls, collection: dict) -> tp.Self:
        """Build a CollectionReleases from a collection API response dict."""
        collection_releases = [
            CollectionRelease(
                name=collection["name"],
                idx=collection["id"],
                version=release["version"],
                latest=release["latest"],
                ppanggolin_version=release["ppanggolin_version"],
                pangbank_wf_version=release["pangbank_wf_version"],
                taxonomy=release["taxonomy_source"]["name"],
                taxonomy_version=release["taxonomy_source"]["version"],
                nb_pangenomes=release["pangenome_count"],
            )
            for release in collection["releases"]
        ]
        collection_releases = sorted(
            collection_releases, key=lambda r: parse_version(r.version)
        )
        return cls(name=collection["name"], releases=collection_releases)

    @property
    def latest(self) -> CollectionRelease:
        """The release flagged as latest."""
        return next(r for r in self.releases if r.latest)

    def __len__(self) -> int:
        return len(self.releases)


def parse_collection_name_version(collection: str) -> tuple[str, str, str | None]:
    """Parse a "name@version:pangenome" spec into (name, version or "latest", pangenome or None)."""
    s = collection.strip().split("@")
    if len(s) > 1:
        if ":" in s[1]:
            ver, pg = s[1].split(":")
            return s[0], ver, pg
        else:
            return s[0], s[1], None
    else:
        if ":" in collection:
            c, pg = collection.split(":")
            return c, "latest", pg
        else:
            return collection, "latest", None


class PanGBank_APIError(MetaPanG_Error):
    """Error raised for PanGBank API failures."""

    pass


class PanGBank_API:
    """PanGBank API wrapper, limited to the routes MetaPanG needs."""

    PROGRESS_COLUMNS = [
        BarColumn(),
        "[progress.description]{task.description}",
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ]

    def __init__(self, config: PanGBank_Config):
        self._config = config
        self._info = None

    @property
    def url(self) -> str:
        return self._config.api_endpoint

    def _fetch_file(self, url: str, out: Path, info: str = "") -> Path:
        with httpx.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()
            with (
                open(out, "wb") as f,
                Progress(*PanGBank_API.PROGRESS_COLUMNS, transient=True) as progress,
            ):
                task = progress.add_task(
                    f"{out.name}{info}",
                    total=int(response.headers.get("Content-Length", 0)),
                )
                for chunk in response.iter_bytes():
                    f.write(chunk)
                    progress.update(task, advance=len(chunk))
        return out

    def _fetch_file_locked(self, url: str, out: Path, info: str = "") -> Path:
        with FileLock(out) as fl:
            return fl.download(lambda tmp: self._fetch_file(url, tmp, info))[0]

    def _fetch_json_file(self, url: str) -> dict:
        data = ""
        with httpx.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                data += chunk.decode("utf-8")
        return json.loads(data)

    def _json_response(self, url: str, **kwargs) -> dict:
        resp = httpx.get(url, follow_redirects=True, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def _url(self, *args) -> str:
        return f"{self.url}/{'/'.join(args)}"

    def has_collection(self, collection_name: str, version: str = "latest") -> bool:
        """Return whether the collection (optionally at a given version) exists."""
        params = dict(collection_name=collection_name)
        data = self._json_response(self._url("collections"), params=params)

        if not data:
            return False

        releases = data[0]["releases"]

        if not version or version == "latest":
            return any(r["latest"] for r in releases)

        return any(r["version"] == version for r in releases)

    def get_collections(self) -> list[CollectionReleases]:
        """Return every collection with its releases."""
        data = self._json_response(self._url("collections"))
        return [CollectionReleases.from_api_response(collection) for collection in data]

    def get_collection_releases(self, collection: str) -> CollectionReleases:
        """Return all releases of a collection by name."""
        data = self._json_response(
            self._url("collections"), params=dict(collection_name=collection)
        )
        return CollectionReleases.from_api_response(data[0])

    def get_collection(self, collection: str, version: str = "") -> CollectionRelease:
        """Return a single collection release, defaulting to the latest."""
        releases = self.get_collection_releases(collection)

        if not version or version == "latest":
            return releases.latest

        release = next(r for r in releases.releases if r.version == version)

        return release

    def has_pangenome(self, collection: CollectionRelease, pangenome_name: str) -> bool:
        """Return whether a pangenome exists in the given collection release."""
        params = dict(
            collection_id=collection.idx,
            pangenome_name=pangenome_name,
            release_version=collection.version,
        )
        data = self._json_response(self._url("pangenomes"), params=params)
        return bool(data)

    def get_pangenome_id(
        self, collection: CollectionRelease, pangenome_name: str
    ) -> int:
        """Return the API id of a pangenome in the given collection release."""
        params = dict(
            collection_id=collection.idx,
            pangenome_name=pangenome_name,
            release_version=collection.version,
        )
        data = self._json_response(self._url("pangenomes"), params=params)
        return data[0]["id"]

    def get_pangenome_name(
        self, collection: CollectionRelease, pangenome_id: int
    ) -> str:
        """Return a pangenome's name for its id, checked against `collection`.

        Raises PanGBank_APIError if the id is unknown, or belongs to a different
        collection or release version.
        """
        try:
            data = self._json_response(self._url("pangenomes", str(pangenome_id)))
        except httpx.HTTPStatusError as e:
            raise PanGBank_APIError(
                f"Pangenome id {pangenome_id} not found in PanGBank"
            ) from e

        release = data.get("collection_release") or {}
        coll = release.get("collection") or {}
        if (
            coll.get("id") != collection.idx
            or release.get("version") != collection.version
        ):
            raise PanGBank_APIError(
                f"Pangenome id {pangenome_id} ('{data.get('name')}') belongs to "
                f"'{release.get('collection_name')}@{release.get('version')}', "
                f"not '{collection.name}@{collection.version}'"
            )
        return data["name"]

    def fetch_pangenome(
        self, collection: CollectionRelease, name: str, out: Path
    ) -> Path:
        """Download a pangenome file to out (with file locking)."""
        pangenome_id = self.get_pangenome_id(collection, name)

        with FileLock(out) as fl:
            return fl.download(
                lambda tmp: self._fetch_file(
                    self._url("pangenomes", str(pangenome_id), "file"),
                    tmp,
                    f"[{collection.full_name}]",
                )
            )[0]

    def fetch_index(self, collection: CollectionRelease, out: Path) -> Path:
        """Download the collection's index files (info, genome, pangenome) into out."""
        prefix = f"collections/{collection.idx}"

        self._fetch_file_locked(
            self._url(prefix, "index/info"),
            out / "index_info.json",
            f"[{collection.full_name}]",
        )
        self._fetch_file_locked(
            self._url(prefix, "index/genomes"),
            out / "genome_index.sbt.zip",
            f"[{collection.full_name}]",
        )
        self._fetch_file_locked(
            self._url(prefix, "index/pangenomes"),
            out / "pangenome_index.sbt.zip",
            f"[{collection.full_name}]",
        )

        return out

    def fetch_dbg(self, collection: CollectionRelease, name: str, out: Path) -> Path:
        """Download a pangenome's de Bruijn graph files (graph, annotations, graph_tool) into out."""
        prefix = f"pangenomes/{self.get_pangenome_id(collection, name)}"
        self._fetch_file_locked(self._url(prefix, "dbg/graph"), out / f"{name}.dbg")
        self._fetch_file_locked(
            self._url(prefix, "dbg/family_annotations"),
            out / f"{name}.family.row_diff_brwt.annodbg",
        )
        self._fetch_file_locked(
            self._url(prefix, "dbg/genome_annotations"),
            out / f"{name}.genome.row_diff_brwt.annodbg",
        )
        self._fetch_file_locked(self._url(prefix, "graph_tool"), out / f"{name}.gt")
        return out


class PanGBank_Cache:
    """Local on-disk cache fronting the PanGBank API."""

    def __init__(self, config: PanGBank_Config):
        self._config = config
        self._directory_path = Path(self._config.cache_directory).absolute()
        self._api = PanGBank_API(config)

    @staticmethod
    def from_config(config: PanGBank_Config) -> "PanGBank_Cache":
        """Build a PanGBank_Cache from a config."""
        return PanGBank_Cache(config)

    @property
    def directory(self) -> Path:
        return self._directory_path

    @property
    def api(self) -> PanGBank_API:
        return self._api

    @property
    def collection_directory(self) -> Path:
        return self.directory / "collections"

    class CollectionCacheProxy:
        """Cache view bound to a single collection release."""

        def __init__(self, cache: "PanGBank_Cache", collection: CollectionRelease):
            self._cache = cache
            self._collection = collection

        def get_pangenome(self, name: str) -> Path:
            """Return the cached pangenome path, fetching it if absent."""
            return self._cache.get_pangenome(self._collection, name)

        def get_dbg(self, name: str) -> Path:
            """Return the cached de Bruijn graph path, fetching it if absent."""
            return self._cache.get_dbg(self._collection, name)

        def get_index(self) -> Path:
            """Return the cached index path, fetching it if absent."""
            return self._cache.get_index(self._collection)

        def has_pangenome(self, name: str) -> Path | None:
            """Return the cached pangenome path if present, else None."""
            return self._cache.has_pangenome(self._collection, name)

        def has_dbg(self, name: str) -> Path | None:
            """Return the cached de Bruijn graph path if present, else None."""
            return self._cache.has_dbg(self._collection, name)

        def has_index(self) -> Path | None:
            """Return the cached index path if present, else None."""
            return self._cache.has_index(self._collection)

    def proxy(self, collection: CollectionRelease) -> CollectionCacheProxy:
        """Return a cache proxy bound to the given collection release."""
        return PanGBank_Cache.CollectionCacheProxy(self, collection)

    def create_tree(self):
        """Create the cache directory tree if it does not exist."""
        self.directory.mkdir(parents=True, exist_ok=True)
        self.collection_directory.mkdir(parents=True, exist_ok=True)

    def collection_path(self, collection: CollectionRelease) -> Path:
        """Return the cache directory for a collection release."""
        return self.collection_directory / collection.name / collection.version

    def pangenomes_path(self, collection: CollectionRelease) -> Path:
        """Return the pangenomes subdirectory for a collection release."""
        return self.collection_path(collection) / "pangenomes"

    def dbgs_path(self, collection: CollectionRelease) -> Path:
        """Return the de Bruijn graphs subdirectory for a collection release."""
        return self.collection_path(collection) / "dbg"

    def pangenome_path(self, collection: CollectionRelease, name: str) -> Path:
        """Return the cached file path for a named pangenome."""
        return self.pangenomes_path(collection) / f"{name}.h5"

    def dbg_path(self, collection: CollectionRelease, name: str) -> Path:
        """Return the cached directory path for a named de Bruijn graph."""
        return self.dbgs_path(collection) / name

    def index_path(self, collection: CollectionRelease) -> Path:
        """Return the cached index directory for a collection release."""
        return self.collection_path(collection) / "bank_index"

    def has_pangenome(self, collection: CollectionRelease, name: str) -> Path | None:
        """Return the cached pangenome path if present, else None."""
        p = self.pangenome_path(collection, name)
        return p if p.exists() else None

    def has_dbg(self, collection: CollectionRelease, name: str) -> Path | None:
        """Return the cached de Bruijn graph path if all its files are present, else None."""
        ok = all(
            (
                self.dbg_path(collection, name).exists(),
                self.dbg_path(collection, name).joinpath(f"{name}.dbg").exists(),
                self.dbg_path(collection, name)
                .joinpath(f"{name}.family.row_diff_brwt.annodbg")
                .exists(),
                self.dbg_path(collection, name)
                .joinpath(f"{name}.genome.row_diff_brwt.annodbg")
                .exists(),
                self.dbg_path(collection, name).joinpath(f"{name}.gt").exists(),
            )
        )
        return self.dbg_path(collection, name) if ok else None

    def has_index(self, collection: CollectionRelease) -> Path | None:
        """Return the cached index path if all its files are present, else None."""
        ok = all(
            (
                self.index_path(collection).exists(),
                self.index_path(collection).joinpath("genome_index.sbt.zip").exists(),
                self.index_path(collection)
                .joinpath("pangenome_index.sbt.zip")
                .exists(),
                self.index_path(collection).joinpath("index_info.json").exists(),
            )
        )
        return self.index_path(collection) if ok else None

    def get_pangenome(self, collection: CollectionRelease, name: str) -> Path:
        """Return the cached pangenome path, downloading it on a cache miss."""
        mp_log_trace(
            self._config.with_tty_log,
            "[PanGBank_Cache] get_pangenome(collection={collection}, name={name})",
            collection=collection,
            name=name,
        )
        if p := self.has_pangenome(collection, name):
            mp_log_trace(
                self._config.with_tty_log,
                "[PanGBank_Cache] Pangenome '{collection}:{name}' found in cache '{p}'",
                collection=collection,
                name=name,
                p=p,
            )
            return p
        else:
            self.pangenomes_path(collection).mkdir(parents=True, exist_ok=True)
            return self._api.fetch_pangenome(
                collection, name, self.pangenome_path(collection, name)
            )

    def get_dbg(self, collection: CollectionRelease, name: str) -> Path:
        """Return the cached de Bruijn graph path, downloading it on a cache miss."""
        mp_log_trace(
            self._config.with_tty_log,
            "[PanGBank_Cache] get_dbg(collection={collection}, name={name})",
            collection=collection,
            name=name,
        )
        if d := self.has_dbg(collection, name):
            mp_log_trace(
                self._config.with_tty_log,
                "[PanGBank_Cache] DBG '{collection}:{name}' found in cache '{d}'",
                collection=collection,
                name=name,
                d=d,
            )
            return d
        else:
            self.dbg_path(collection, name).mkdir(parents=True, exist_ok=True)
            return self._api.fetch_dbg(
                collection, name, self.dbg_path(collection, name)
            )

    def get_index(self, collection: CollectionRelease) -> Path:
        """Return the cached index path, downloading it on a cache miss."""
        mp_log_trace(
            self._config.with_tty_log,
            "[PanGBank_Cache] get_index(collection={})",
            collection,
        )
        if i := self.has_index(collection):
            mp_log_trace(
                self._config.with_tty_log,
                "[PanGBank_Cache] Index for collection '{collection}' found in cache '{i}'",
                collection=collection,
                i=i,
            )
            return i
        else:
            self.index_path(collection).mkdir(parents=True, exist_ok=True)
            return self._api.fetch_index(collection, self.index_path(collection))
