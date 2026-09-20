import pytest

from metapang.exceptions import MetaPanG_ConfigError
from metapang.pg import compat


def test_supported():
    assert compat.is_supported("GTDB_refseq", "2.0.0")


def test_unsupported_version():
    assert not compat.is_supported("GTDB_refseq", "1.0.0")


def test_unsupported_collection():
    assert not compat.is_supported("Nope", "2.0.0")


def test_check_supported_ok():
    compat.check_supported("GTDB_refseq", "2.0.0")


def test_check_supported_raises():
    with pytest.raises(MetaPanG_ConfigError):
        compat.check_supported("GTDB_refseq", "1.0.0")


def test_discard_policy(monkeypatch):
    monkeypatch.setitem(
        compat.DISCARDED, "GTDB_refseq@2.0.0", {"s__Bad": "low quality"}
    )
    assert compat.is_discarded("GTDB_refseq", "2.0.0", "s__Bad")
    assert compat.discard_reason("GTDB_refseq", "2.0.0", "s__Bad") == "low quality"
    assert compat.discarded_species("GTDB_refseq", "2.0.0") == {"s__Bad": "low quality"}


def test_not_discarded():
    assert not compat.is_discarded("GTDB_refseq", "2.0.0", "s__Foo")
    assert compat.discard_reason("GTDB_refseq", "2.0.0", "s__Foo") is None
