from pathlib import Path


class MetaPanG_Error(Exception):
    """Base class for all MetaPanG errors."""

    ...


class MetaPanG_InvalidPangenome(MetaPanG_Error):
    """Raised when a pangenome is malformed or invalid."""

    ...


class MetaPanG_ExternalError(MetaPanG_Error):
    """Raised when an external command fails."""

    ...


class MetaPanG_MissingTool(MetaPanG_Error):
    """Raised when a required external executable cannot be found."""

    ...


class MetaPanG_MissingResource(MetaPanG_Error):
    """Raised when a bundled MetaPanG resource cannot be found."""

    ...


class MetaPanG_IoError(MetaPanG_Error):
    """Raised when a filesystem path or I/O operation fails."""

    ...


class MetaPanG_ConfigError(MetaPanG_Error):
    """Raised when configuration loading or validation fails."""

    ...


def check_paths_exist(paths: list[Path] | Path):
    """Raise MetaPanG_IoError if any of the given paths does not exist."""
    if isinstance(paths, Path):
        paths = [paths]

    for path in paths:
        if not path.exists():
            raise MetaPanG_IoError(f"Path '{path}' does not exist")
