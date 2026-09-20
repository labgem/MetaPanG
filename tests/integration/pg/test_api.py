import pytest

from metapang.config import PanGBank_Config
from metapang.pg.api import PanGBank_API


@pytest.fixture(scope="module")
def api():
    client = PanGBank_API(PanGBank_Config(with_tty_log=False))
    try:
        client.get_collections()
    except Exception as e:
        pytest.skip(f"PanGBank API not reachable: {e}")
    return client


def test_get_collections_non_empty(api):
    collections = api.get_collections()
    assert len(collections) > 0
    assert all(c.name for c in collections)


def test_has_known_collection(api):
    assert api.has_collection("GTDB_refseq") is True


def test_has_unknown_collection(api):
    assert api.has_collection("not_a_real_collection_xyz") is False


def test_get_collection_releases_latest(api):
    releases = api.get_collection_releases("GTDB_refseq")
    assert len(releases) > 0
    assert releases.latest.name == "GTDB_refseq"


def test_get_collection_defaults_to_latest(api):
    release = api.get_collection("GTDB_refseq")
    assert release.name == "GTDB_refseq"
    assert release.version
    assert release.latest is True
