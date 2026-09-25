import warnings

warnings.filterwarnings("ignore")

__version__ = "0.1.1"


def _commit() -> str | None:
    """Return the git commit MetaPanG was built from (or is running from)."""
    try:
        from metapang._commit import COMMIT  # type: ignore[import-not-found]

        return COMMIT or None
    except Exception:
        pass
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    try:
        rev = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        return rev + ("-dirty" if dirty else "") if rev else None
    except Exception:
        return None


__commit__ = _commit()
