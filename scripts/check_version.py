#!/usr/bin/env python3
"""Check that the version is consistent across the repo.

Fails if metapang.__version__ and the pixi.toml [workspace] version disagree.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(pattern: str, path: Path) -> str | None:
    match = re.search(pattern, path.read_text(), re.MULTILINE)
    return match.group(1) if match else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Expected version, e.g. v0.1.0 or 0.1.0")
    parser.add_argument(
        "--pre-push",
        action="store_true",
        help="Read git pre-push refs on stdin and validate any pushed version tags",
    )
    args = parser.parse_args()

    init_v = _read(r'^__version__\s*=\s*"([^"]+)"', ROOT / "metapang" / "__init__.py")
    pixi_v = _read(r'^version\s*=\s*"([^"]+)"', ROOT / "pixi.toml")

    if init_v is None or pixi_v is None:
        print("check_version: could not read the version", file=sys.stderr)
        return 1

    if init_v != pixi_v:
        print(
            f"check_version: mismatch between metapang.__version__ ({init_v}) and "
            f"pixi.toml ({pixi_v}).",
            file=sys.stderr,
        )
        return 1

    tags: list[str] = []
    if args.tag is not None:
        tags.append(args.tag)
    if args.pre_push:
        for line in sys.stdin:
            local_ref = line.split()[0] if line.split() else ""
            match = re.match(r"^refs/tags/(v?\d+\.\d+\.\d+)$", local_ref)
            if match:
                tags.append(match.group(1))

    for tag in tags:
        if tag.lstrip("v") != init_v:
            print(
                f"check_version: tag {tag} does not match the repo version ({init_v}).",
                file=sys.stderr,
            )
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
