"""Compatibility policy shipped with MetaPanG.

Declares which PanGBank collection versions this MetaPanG version can use, and
which species are discarded within a version.
Collection-version incompatibility is hard. Species discards can be overridden by the user.
"""

from metapang.exceptions import MetaPanG_ConfigError

# Collection -> set of supported versions.
SUPPORTED: dict[str, set[str]] = {
    "GTDB_refseq": {"2.0.0"},
}

# "collection@version" -> {species: reason} discarded by default (overridable).
DISCARDED: dict[str, dict[str, str]] = {
    "GTDB_refseq@2.0.0": {
        "s__ECMA0423_sp047199055": "Low quality representative (<85% completeness), likely E. coli",
        "s__G047199095_sp047199095": "Low quality representative (<85% completeness), likely E. coli",
        "s__Ferrimicrobium_sp027409005": "Low quality representative (<85% completeness)",
        "s__Lactobacillus_apis_A": "Low quality representative (<85% completeness)",
        "s__Lactobacillus_sp945980025": "Low quality representative (<85% completeness), likely L. johnsonii",
        "s__Streptococcus_oralis_K": "Low quality representative (<85% completeness)",
        "s__Bacteroides_caecimuris_A": "Low quality representative (<85% completeness)",
        "s__Bacteroides_sp900755095": "Low quality representative (<85% completeness), likely B. ovatus",
        "s__Bacteroides_sp947646015": "Low quality representative (<85% completeness), likely B. thetaiotaomicron",
        "s__Bacteroides_stercoris_A": "Low quality representative (<85% completeness)",
        "s__Prevotella_copri_U": "Low quality representative (<85% completeness)",
        "s__Thiolapillus_brandeum_A": "Low quality representative (<85% completeness)",
        "s__Enterobacter_flexneri_A": "Low quality representative (<85% completeness)",
        "s__Stutzerimonas_xanthomarina_A": "Low quality representative (<85% completeness)",
    }
}


def is_supported(collection: str, version: str) -> bool:
    """Return whether the collection at the given version is supported."""
    return version in SUPPORTED.get(collection, set())


def supported_versions(collection: str) -> set[str]:
    """Return the supported versions of a collection (empty if unknown)."""
    return SUPPORTED.get(collection, set())


def discarded_species(collection: str, version: str) -> dict[str, str]:
    """Return the discarded species and their reasons for a collection version."""
    return DISCARDED.get(f"{collection}@{version}", {})


def is_discarded(collection: str, version: str, species: str) -> bool:
    """Return whether a species is discarded in the given collection version."""
    return species in discarded_species(collection, version)


def discard_reason(collection: str, version: str, species: str) -> str | None:
    """Return why a species is discarded, or None if it is not discarded."""
    return discarded_species(collection, version).get(species)


def check_supported(collection: str, version: str) -> None:
    """Raise MetaPanG_ConfigError if the collection version is not supported."""
    if is_supported(collection, version):
        return
    versions = supported_versions(collection)
    if versions:
        hint = f"supported versions: {', '.join(sorted(versions))}"
    else:
        hint = f"supported collections: {', '.join(sorted(SUPPORTED))}"
    raise MetaPanG_ConfigError(
        f"'{collection}@{version}' is not compatible with this MetaPanG version "
        f"({hint})."
    )
