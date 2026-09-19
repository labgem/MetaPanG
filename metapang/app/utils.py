import click
import pandas as pd
from rich.table import Table


class ClickEnum(click.Choice):
    """A click.Choice that converts to an Enum member."""

    def __init__(self, enum):
        self._enum = enum
        super().__init__(list(sorted(set(enum.__members__))))

    def convert(self, value, param, ctx):
        """Convert the parsed choice string into its matching Enum member."""
        value = super().convert(value, param, ctx)
        return next(_ for _ in self._enum if _.name == value)

    def get_metavar(self, param, *args, **kwargs):
        """Return the help metavar listing the available enum member names."""
        return f"[{', '.join(self._enum.__members__)}]"


def df_to_rich(df: pd.DataFrame, title="") -> Table:
    """Convert a pandas DataFrame to a rich Table."""
    df = df.astype(str)
    table = Table(title=title)
    for col in df.columns:
        table.add_column(col)
    for row in df.values:
        table.add_row(*row)
    return table


def show_df_in_rich(df: pd.DataFrame, title=""):
    """Display a pandas DataFrame as a rich Table on stderr."""
    table = df_to_rich(df, title)
    from rich.console import Console

    console = Console(stderr=True)
    console.print(table)


def metanpang_option(*param_decls, shelp="", lhelp="", **kwargs):
    """Build a click.option decorator with a short and long help description."""
    h = f"""
    {shelp} __placeholder__ [/]
    [i]{lhelp}[/]
    """
    kwargs["help"] = h

    def decorator(func):
        return click.option(*param_decls, **kwargs)(func)

    return decorator


def space(n: int = 2) -> str:
    """Return a string of n non-breaking spaces."""
    return "\u00a0" * n
