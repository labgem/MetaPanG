import gzip
from pathlib import Path

import pytest

from metapang.exceptions import MetaPanG_IoError
from metapang.utils.io import (
    convert,
    get_files_from_directory,
    get_files_from_fof,
    is_fastx,
    zopen,
)


def test_convert_int():
    result = convert("42")
    assert result == 42
    assert isinstance(result, int)


def test_convert_float():
    assert convert("3.14") == pytest.approx(3.14)


def test_convert_str():
    assert convert("abc") == "abc"


def test_is_fastx_true():
    assert is_fastx("x.fa")
    assert is_fastx("x.fasta.gz")
    assert is_fastx("x.fastq")
    assert is_fastx("reads.fq.gz")


def test_is_fastx_false():
    assert not is_fastx("x.gbff")
    assert not is_fastx("x.txt")
    assert not is_fastx("x.gz")


def test_zopen_roundtrip_plain(tmp_path):
    p = tmp_path / "f.txt"
    with zopen(p, "w") as fh:
        fh.write("hello")
    with zopen(p) as fh:
        assert fh.read() == "hello"


def test_zopen_roundtrip_gzip(tmp_path):
    p = tmp_path / "f.txt"
    with zopen(p, "wt", compress=True) as fh:
        fh.write("hello")
    with gzip.open(str(p) + ".gz", "rt") as fh:
        assert fh.read() == "hello"


def test_get_files_from_directory_recursive(tmp_path):
    (tmp_path / "a.fa").write_text("x")
    (tmp_path / "b.txt").write_text("y")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.fa").write_text("z")
    found = get_files_from_directory(tmp_path, glob="*.fa", path_type=str)
    names = sorted(Path(f).name for f in found)
    assert names == ["a.fa", "c.fa"]


def test_get_files_from_directory_non_recursive(tmp_path):
    (tmp_path / "a.fa").write_text("x")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.fa").write_text("z")
    found = get_files_from_directory(tmp_path, glob="*.fa", recursive=False)
    assert len(found) == 1


def test_get_files_from_fof(tmp_path):
    a = tmp_path / "a.fa"
    a.write_text("x")
    fof = tmp_path / "list.txt"
    fof.write_text(f"{a}\n\n")
    assert get_files_from_fof(fof, path_type=str) == [str(a.absolute())]


def test_get_files_from_fof_missing_fof(tmp_path):
    with pytest.raises(MetaPanG_IoError):
        get_files_from_fof(tmp_path / "nope.txt")


def test_get_files_from_fof_missing_listed(tmp_path):
    fof = tmp_path / "list.txt"
    fof.write_text(str(tmp_path / "nope.fa") + "\n")
    with pytest.raises(MetaPanG_IoError):
        get_files_from_fof(fof)
