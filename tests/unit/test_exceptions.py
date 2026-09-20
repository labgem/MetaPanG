import pytest

from metapang.exceptions import (
    MetaPanG_ConfigError,
    MetaPanG_Error,
    MetaPanG_IoError,
    check_paths_exist,
)


def test_error_hierarchy():
    assert issubclass(MetaPanG_IoError, MetaPanG_Error)
    assert issubclass(MetaPanG_ConfigError, MetaPanG_Error)


def test_check_paths_exist_single(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    check_paths_exist(f)


def test_check_paths_exist_list(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.write_text("x")
    b.write_text("y")
    check_paths_exist([a, b])


def test_check_paths_exist_missing(tmp_path):
    with pytest.raises(MetaPanG_IoError):
        check_paths_exist(tmp_path / "nope")


def test_check_paths_exist_one_missing_in_list(tmp_path):
    a = tmp_path / "a"
    a.write_text("x")
    with pytest.raises(MetaPanG_IoError):
        check_paths_exist([a, tmp_path / "nope"])
