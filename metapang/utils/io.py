import os
import sys
import gzip
import contextlib
from typing import Type
import typing as tp
from pathlib import Path
from itertools import chain
import gb_io
from metapang.exceptions import MetaPanG_IoError

FASTA_GLOB = [
    "*.fa",
    "*.fna",
    "*.fasta",
    "*.fa.gz",
    "*.fna.gz",
    "*.fasta.gz",
    "*.gbff",
    "*.gbff.gz"
]


@contextlib.contextmanager
def silence(stdout: bool=True, stderr: bool=True):
    """Context manager to suppress stdout and/or stderr."""
    if stdout and stderr:
        with (
            open(os.devnull, "w") as f,
            contextlib.redirect_stdout(f),
            contextlib.redirect_stderr(f),
        ):
            yield
    elif stdout:
        with open(os.devnull, "w") as f, contextlib.redirect_stdout(f):
            yield
    elif stderr:
        with open(os.devnull, "w") as f, contextlib.redirect_stderr(f):
            yield


@contextlib.contextmanager
def smart_io(filename: str = "") -> tp.Generator[tp.TextIO, None, None]:
    """Context manager to write to a file, stdout or stderr.

    Args:
        filename: File path, or one of '-', 'stdout', 'stderr'.
    """
    if filename and filename not in ("-", "stdout", "stderr"):
        with open(filename, "w") as f:
            yield f
    elif filename in ("-", "stdout"):
        yield sys.stdout
    elif filename == "stderr":
        yield sys.stderr
    else:
        yield sys.stdout


@contextlib.contextmanager
def zopen(
    filename: str | Path, mode: str = "r", compress: bool = False, ext: str = ".gz", **kwargs
) -> tp.Generator[tp.TextIO | tp.BinaryIO | gzip.GzipFile, None, None]:
    """Context manager like open() but with optional gzip compression.

    Args:
        compress: Use gzip compression.
        ext: Extension appended when compressing a write target.
        **kwargs: Passed through to open() or gzip.open().
    """
    filename = str(filename)
    if compress:
        if (
            ext
            and any(char in mode for char in ["w", "a", "x"])
            and not filename.endswith(ext)
        ):
            filename += ext
        file_obj = gzip.open(filename, mode, **kwargs)
    else:
        if filename.endswith(ext):
            file_obj = gzip.open(filename, mode, **kwargs)
        else:
            file_obj = open(filename, mode, **kwargs)

    try:
        yield file_obj
    finally:
        file_obj.close()


def get_files_from_directory(
    directory: str | Path,
    *,
    glob: str | list[str] = "*",
    path_type: Type = Path,
    recursive: bool = True,
) -> list[Path | str]:
    """List files in a directory matching one or more globs.

    Args:
        glob: Glob or list of globs, using Path.glob syntax.
        path_type: Return paths as Path or str objects.
        recursive: Search subdirectories recursively.
    """
    if isinstance(directory, str):
        directory = Path(directory)

    if isinstance(glob, str):
        glob = [glob]

    res = (
        [
            path_type(file.absolute())
            for file in chain(*(directory.glob(g) for g in glob))
            if file.is_file()
        ]
        if not recursive
        else [
            path_type(file.absolute())
            for file in chain(*(directory.rglob(g) for g in glob))
            if file.is_file()
        ]
    )

    return list(set(res))


def get_files_from_fof(path: str | Path, *, path_type: Type = Path) -> list[Path | str]:
    """Read file paths listed in a file of files.

    Args:
        path_type: Return paths as Path or str objects.
    Raises:
        MetaPanG_IoError: The file of files or a listed file does not exist.
    """
    if isinstance(path, str):
        path = Path(path)

    if not path.exists():
        raise MetaPanG_IoError(f"Path does not exist: {path}")

    res = []
    with open(path, "r") as f:
        for line in f.readlines():
            if not line.strip():
                continue
            p = Path(line.strip())
            if not p.exists():
                raise MetaPanG_IoError(f"File does not exist: {p}")
            res.append(path_type(p.absolute()))

    return res


def convert(value: str) -> int | float | str:
    """Convert a string to int or float, returning it unchanged on failure."""
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def is_fastx(path: str | Path) -> bool:
    """Check if a path has a fasta/fastq extension: .fa/.fasta/.fna/.fq/.fastq (.gz)."""
    p = Path(path)
    suffixes = [s.lower() for s in p.suffixes]
    ext = next((s for s in reversed(suffixes) if s != ".gz"), None)

    return ext in {".fa", ".fasta", ".fna", ".fq", ".fastq"}


def gbff_to_fasta(gbff: str | Path, fasta: str | Path) -> None:
    """Convert a gbff file to a fasta file."""
    gbff = Path(gbff)
    fasta = Path(fasta)

    with open(fasta, "w") as fout:
        with zopen(gbff, "rb") as fin:
            for record in gb_io.iter(fin):
                fout.write(f">{record.name}\n{record.sequence.decode('utf-8')}\n")
