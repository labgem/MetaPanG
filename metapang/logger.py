import sys
from contextlib import contextmanager

from loguru import logger as mp_log

METAPANG_LOG_FORMAT = (
    "<blue>{time:YYYY-MM-DD HH:mm:ss.SSS}</blue> | "
    "<level>{level: <4}</level> | "
    "<white><bold>{extra[indent]}{message}</bold></white>"
)

_indent_depth = 0
_INDENT_UNIT = "  "


def _patch_indent(record) -> None:
    record["extra"]["indent"] = _INDENT_UNIT * _indent_depth


_current_level = "INFO"


def metapang_setup_logger(level: str = "INFO", log_file: str | None = None) -> None:
    """Initialize the MetaPanG logger, optionally writing to log_file."""
    global _current_level
    _current_level = level
    mp_log.remove()
    mp_log.configure(patcher=_patch_indent)
    mp_log.add(
        sys.stderr,
        format=METAPANG_LOG_FORMAT,
        level=level,
        diagnose=False,
        backtrace=level != "INFO",
    )
    mp_log.level("INFO", color="<green><bold>")
    if log_file:
        mp_log.add(log_file, format=METAPANG_LOG_FORMAT, level=level)


def metapang_add_log_file(log_file, level: str | None = None) -> int:
    """Add a file sink (plain text, no color) and return its handler id.

    Used by commands to keep a per-run log, e.g. profile writes to outdir/logs.txt.
    Defaults to the level chosen at setup.
    """
    return mp_log.add(
        str(log_file),
        format=METAPANG_LOG_FORMAT,
        level=level or _current_level,
        colorize=False,
        mode="a",
    )


@contextmanager
def log_indent(levels: int = 1):
    """Indent log messages emitted inside this block by `levels` steps (nestable)."""
    global _indent_depth
    _indent_depth += levels
    try:
        yield
    finally:
        _indent_depth -= levels


def mp_log_info(enabled: bool, *args, **kwargs) -> None:
    """Log an info message when enabled."""
    if enabled:
        mp_log.info(*args, **kwargs)


def mp_log_trace(enabled: bool, *args, **kwargs) -> None:
    """Log a trace message when enabled."""
    if enabled:
        mp_log.trace(*args, **kwargs)


def mp_log_debug(enabled: bool, *args, **kwargs) -> None:
    """Log a debug message when enabled."""
    if enabled:
        mp_log.debug(*args, **kwargs)


def mp_log_warning(enabled: bool, *args, **kwargs) -> None:
    """Log a warning message when enabled."""
    if enabled:
        mp_log.warning(*args, **kwargs)


def mp_log_error(enabled: bool, *args, **kwargs) -> None:
    """Log an error message when enabled."""
    if enabled:
        mp_log.error(*args, **kwargs)
