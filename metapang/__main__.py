import sys

from metapang.app.metapang import metapang
from metapang.exceptions import MetaPanG_Error
from metapang.logger import mp_log


def main():
    """CLI entry point that runs MetaPanG and handles top-level errors."""
    try:
        metapang()
    except MetaPanG_Error as e:
        mp_log.error(f"{type(e).__name__} -> {str(e)}")
        sys.exit(1)
    except Exception as e:
        mp_log.error(f"{type(e).__name__} -> {str(e)}")
        mp_log.error("An unexpected error occurred. Please report it.")
        raise e


if __name__ == "__main__":
    main()
