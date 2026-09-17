from typing import Type, Any
from shutil import which
from pathlib import Path
from metapang.exceptions import (
    MetaPanG_MissingTool,
    MetaPanG_MissingResource,
    MetaPanG_ExternalError,
)
from metapang.logger import mp_log
from dataclasses import dataclass, field, fields


def is_executable(name: str) -> bool:
    """Check if a command line tool is available in $PATH and executable."""

    return which(name) is not None


def find_executable(name: str, extra: list[str | Path] = []) -> str:
    """Find the path to an executable in $PATH.

    Args:
        extra: Additional directories to search beyond $PATH.
    Raises:
        MetaPanG_MissingTool: If the executable is not found.
    """

    if exe := which(name):
        return exe

    for path in extra:
        if exe := which(name, path=str(path)):
            return exe

    raise MetaPanG_MissingTool(name)


def find_metapang_resource(name: str) -> Path:
    """Find a MetaPanG resource file bundled with the package."""

    from importlib.resources import files

    p = Path(str(files("metapang") / name))
    if not p.exists():
        raise MetaPanG_MissingResource(f"Resource {name} not found")
    return p


class CLIField:
    """Metadata describing how a dataclass field maps to a CLI argument."""
    def __init__(
        self,
        type_: Type,
        *,
        value: Any,
        positional: bool,
        prefix: str,
        replace: dict[str, str],
        flag: bool,
        default: Any,
        stdin: bool,
    ):
        self._type = type_
        self.value = value
        self.positional = positional
        self.prefix = prefix
        self.replace = replace
        self.flag = flag
        self.default = default
        self.stdin = stdin

    def key(self, key: str):
        """Return the CLI option key for a field name after applying replacements."""
        for s, r in self.replace.items():
            key = key.replace(s, r)
        return f"{self.prefix}{key}"


def cli_field(
    type_: type,
    *,
    positional: bool = False,
    prefix: str = "--",
    replace: dict[str, str] = {"_": "-"},
    flag: bool = False,
    default: Any = None,
    stdin: bool = False,
) -> CLIField:
    """Define a dataclass field carrying CLI argument metadata."""
    f = CLIField(
        type_=type_,
        value=default,
        positional=positional,
        prefix=prefix,
        replace=replace,
        flag=flag,
        default=default,
        stdin=stdin,
    )
    return field(default=default, metadata={"cli": f})


def cli_dataclass(cls: Type) -> Type:
    """Class decorator turning a dataclass into a CLI-argument builder."""
    def __post_init__(self):
        cli_fields = {}
        for f in fields(self):
            meta = f.metadata.get("cli")
            if meta:
                cli_fields[f.name] = meta
        setattr(self, "_cli_fields", cli_fields)

    def get_cli_options(self) -> list[str]:
        """Return the non-positional CLI flags and options for the current field values."""
        args = []
        cli_fields = getattr(self, "_cli_fields", {})
        for name, meta in cli_fields.items():
            val = getattr(self, name)
            if not meta.positional and not meta.stdin:
                if meta.flag:
                    if val:
                        args.append(meta.key(name))
                else:
                    if val is None:
                        if meta.default is None:
                            continue
                        else:
                            val = meta.default
                    args.extend([meta.key(name), str(val)])
        return args

    def get_cli_positionals(self) -> list[str]:
        """Return the positional CLI arguments for the current field values."""
        args = []
        cli_fields = getattr(self, "_cli_fields", {})
        for name, meta in cli_fields.items():
            if meta.positional and not meta.stdin:
                val = getattr(self, name)
                if isinstance(val, list):
                    args.extend([str(v) for v in val])
                else:
                    args.append(str(val))
        return args

    def get_cli_input(self) -> str | None:
        """Return the value to pipe to the tool's stdin, or None if no stdin field is set."""
        cli_fields = getattr(self, "_cli_fields", {})
        for name, meta in cli_fields.items():
            if meta.stdin:
                v = getattr(self, name)
                if isinstance(v, str):
                    return v
                elif isinstance(v, list):
                    return "\n".join(str(i) for i in v)
                return getattr(self, name)
        return None

    def get_cli(self) -> list[str]:
        """Return the full CLI argument list (options followed by positionals)."""
        return self.get_cli_options() + self.get_cli_positionals()

    cls.__post_init__ = __post_init__
    cls.get_cli = get_cli
    cls.get_cli_options = get_cli_options
    cls.get_cli_positionals = get_cli_positionals
    cls.get_cli_input = get_cli_input
    return dataclass(cls)


import subprocess


class CLIExecutor:
    """Builds and runs external command-line tools via subprocess."""

    def _execute(
        self,
        executable: str,
        command: str,
        options,
        wd: str | None = None,
        capture: bool = True,
        capture_stderr: bool = True,
        stdout_file=None,
    ) -> tuple[int | None, bytes | None, bytes | None]:
        """Run `executable command <options>` and return (returncode, stdout, stderr).

        stdout is captured as bytes when `capture` is set, or redirected to
        `stdout_file` (an open file object) when given; raises MetaPanG_ExternalError
        on a non-zero exit.
        """
        argv = [executable, command, *options.get_cli()]
        exec_name = executable.rsplit("/", 1)[-1]
        mp_log.debug(f"Executing command: '{exec_name} {command}'")
        mp_log.trace(" ".join(argv))

        stdin_data = options.get_cli_input()
        if isinstance(stdin_data, str):
            stdin_data = stdin_data.encode()

        if stdout_file is not None:
            stdout_target = stdout_file
        elif capture:
            stdout_target = subprocess.PIPE
        else:
            stdout_target = None
        stderr_target = subprocess.PIPE if capture_stderr else None

        try:
            proc = subprocess.run(
                argv,
                cwd=wd if wd else str(Path.cwd()),
                input=stdin_data,
                stdout=stdout_target,
                stderr=stderr_target,
            )
        except OSError as e:
            raise MetaPanG_ExternalError(f"Failed to run '{exec_name} {command}': {e}") from e

        if proc.returncode != 0:
            raise MetaPanG_ExternalError(
                f"Command '{exec_name} {command}' failed with return code {proc.returncode}.\n"
                + self._make_std_message(proc.stdout, proc.stderr)
            )

        mp_log.debug(f"Command executed successfully: {exec_name} {command} (rc={proc.returncode}).")
        mp_log.trace(
            f"Command outputs: {self._make_std_message(proc.stdout, proc.stderr, capture, capture_stderr)}"
        )
        return proc.returncode, proc.stdout, proc.stderr

    def _make_std_message(
        self, stdout: bytes | None, stderr: bytes | None,
        with_stdout: bool = True, with_stderr: bool = True,
    ) -> str:
        """Format captured stdout/stderr bytes into a readable diagnostic block."""
        msg = ""
        dstdout = stdout.decode().strip() if with_stdout and stdout else ""
        dstderr = stderr.decode().strip() if with_stderr and stderr else ""

        if dstdout:
            msg += f"\nstdout: \n{dstdout}\n"
        else:
            msg += "stdout=∅ "

        if dstderr:
            msg += f"\nstderr: \n{dstderr}"
        else:
            msg += "stderr=∅"

        return msg
