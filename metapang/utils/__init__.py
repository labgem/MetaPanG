def parse_version(version: str) -> tuple:
    """Parse a dotted version string into a tuple of integers."""
    return tuple(map(int, version.lstrip("v").split(".")))
