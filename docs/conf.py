import re
from pathlib import Path


def _read_version() -> str:
    init = Path(__file__).resolve().parent.parent / "metapang" / "__init__.py"
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init.read_text())
    return match.group(1) if match else "0.0.0"


project = "MetaPanG"
author = "Téo Lemane"
copyright = "2026, LABGeM"
release = _read_version()
version = release

extensions = [
    "myst_parser",
    "sphinx_copybutton",
]

myst_enable_extensions = ["colon_fence", "deflist"]
myst_heading_anchors = 3

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"
html_title = f"MetaPanG {release}"
html_static_path = ["_static"]
html_theme_options = {
    "source_repository": "https://github.com/LABGeM/MetaPanG",
    "source_branch": "main",
    "source_directory": "docs/",
}
