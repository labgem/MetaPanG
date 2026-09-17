def colors(partition: str) -> str:
    """Return the hex color associated with a pangenome partition."""
    if partition == "P" or partition.lower() == "persistent":
        return "#e59c04"
    elif partition == "S" or partition.lower() == "shell":
        return "#00d860"
    elif partition == "C" or partition.lower() == "cloud":
        return "#79deff"
    else:
        return "#d62728"

