import subprocess
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py


def _commit_hash() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return ""


class build_py_with_commit(build_py):
    def run(self):
        super().run()
        target = Path(self.build_lib) / "metapang" / "_commit.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f'COMMIT = "{_commit_hash()}"\n')


setup(cmdclass={"build_py": build_py_with_commit})
