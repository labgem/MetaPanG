import os
import time
import fcntl
import typing as tp
from pathlib import Path

class FileLock:
    """Cross-process file lock guarding atomic downloads to a target path."""
    def __init__(
            self,
            target: Path | str,
            timeout: float = 600.0,
            poll: float = 0.1,
            lock_suffix: str = ".lock",
            temp_suffix: str = ".part"
    ):
        self._target: Path = Path(target)
        self._timeout: float = timeout
        self._poll: float = poll
        self._lock_path: Path = self._target.with_suffix(lock_suffix)
        self._temp_path: Path = self._target.with_suffix(temp_suffix)
        self._fd: tp.IO | None = None
        self._locked: bool = False

    def _open_lock_fd(self) -> None:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = open(self._lock_path, "a+b")
        if not self._fd:
            raise IOError(f"Failed to create a file descriptor for lock {self._lock_path}")

    def _close_lock_fd(self) -> None:
        if not self._fd:
            return

        try:
            self._fd.close()
        except Exception:
            pass
        self._fd = None

    def acquire(self) -> None:
        """Acquire the exclusive lock, blocking until available or timeout."""
        if self._locked:
            return
        start = time.time()
        self._open_lock_fd()

        while True:
            try:
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB) # type: ignore
                self._locked = True
                return
            except (BlockingIOError, OSError):
                if time.time() - start >= self._timeout:
                    self._close_lock_fd()
                    raise TimeoutError(f"Timeout while acquiring lock for {self._lock_path}")
                time.sleep(self._poll)

    def release(self) -> None:
        """Release the exclusive lock and close the lock file descriptor."""
        if not self._locked:
            self._close_lock_fd()
            return

        try:
            fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN) # type: ignore
        except OSError:
            pass
        finally:
            self._close_lock_fd()
            self._locked = False

    def download(self, callback: tp.Callable[[Path], tp.Any]) -> tuple[Path, tp.Any]:
        """Run callback under the lock to atomically produce the target file."""
        if self._target.exists():
            return self._target, None

        self.acquire()
        try:
            if self._target.exists():
                return self._target, None

            self._temp_path.parent.mkdir(parents=True, exist_ok=True)

            if self._temp_path.exists():
                try:
                    self._temp_path.unlink()
                except Exception:
                    pass

            res = callback(self._temp_path)

            if self._temp_path.exists():
                os.replace(str(self._temp_path), str(self._target))
            elif not self._target.exists():
                raise RuntimeError(f"Failed to download '{self._target}'")
            return self._target, res
        finally:
            try:
                if self._temp_path.exists():
                    self._temp_path.unlink()
            except Exception:
                pass
            self.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()

