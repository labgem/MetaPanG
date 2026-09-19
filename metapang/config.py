import os
import typing as tp
from pathlib import Path

import jsonschema
import msgspec
from msgspec import Struct, field

from metapang.exceptions import MetaPanG_ConfigError
from metapang.utils.io import convert

METAPANG_CONFIG_PATHS = [
    Path().home() / ".config" / "metapang-config",
    Path(".metapang-config"),
]

METAPANG_CONFIG_DECODERS = {
    ".json": msgspec.json,
    ".yaml": msgspec.yaml,
    ".toml": msgspec.toml,
}


def enc_hook(obj: tp.Any):
    """Encode unsupported objects (Path) into JSON-serializable values."""
    if isinstance(obj, Path):
        return str(Path)
    else:
        raise NotImplementedError(f"Objects of type {type(obj)} are not supported")


def dec_hook(type: type, obj: tp.Any):
    """Decode raw values into supported target types (Path)."""
    if type is Path:
        return Path(obj)
    else:
        raise NotImplementedError(f"Objects of type {type} are not supported")


class PanGBank_Config(Struct):
    """Configuration for the PanGBank API client and cache."""

    api_endpoint: str = field(default="https://pangbank-api.genoscope.cns.fr")
    cache_directory: str = field(default=".metapang-cache")
    use_cache: bool = field(default=True)
    with_tty_log: bool = field(default=True)


class MetaPanG_External(Struct):
    """Configuration for locating external executables used by MetaPanG."""

    search_locations: list[str] = field(default_factory=list)
    metagraph_exe: str = field(default="metagraph")
    pangbank_exe: str = field(default="pangbank")


class metapang_search_c(Struct):
    """Configuration for the search command."""

    class pangenome_c(Struct):
        """Configuration for searching a single pangenome."""

        mode: str = field(default="containment")
        threshold: float = field(default=0.1)
        threads: int = field(default=1)
        metagraph_path: str = field(default="metagraph")
        output: str = field(default="{pangenome_name}_{query_file_name}.tsv")

    class bank_c(Struct):
        """Configuration for searching a bank of pangenomes."""

        mode: str = field(default="containment")
        threshold_pangenome: float = field(default=0.05)
        threshold_genome: float = field(default=0.5)
        threads: int = field(default=1)

    pangenome: pangenome_c = field(default_factory=pangenome_c)
    bank: bank_c = field(default_factory=bank_c)


class metapang_profile_c(Struct):
    """Configuration for the profile command."""

    # Single source of truth for the `profile` command's tunable defaults.
    # StrainProfileConfig (metapang.core.profile.strains) sources its defaults
    # from here, and the CLI options default from it too. Field names MUST match
    # the command's click parameter names (that's how config values reach them).
    pangbank: str = field(default="GTDB_refseq")
    output: str = field(default="{query}_{collection}_profile")
    threads: int = field(default=1)
    metagraph_path: str = field(default="metagraph")
    # strain-number selection
    merge_jaccard: float = field(default=0.95)
    k_max: int = field(default=12)
    stop_rule: str = field(default="cv_paired")
    cv_folds: int = field(default=5)
    cv_min_rel_reduction: float = field(default=0.02)
    # per-strain gene-content reconciliation
    refine_ra: bool = field(default=True)
    impute_min_neighbour_frac: float = field(default=0.5)
    reassign_max_rel_residual: float = field(default=0.5)


class metapang_index_c(Struct):
    """Configuration for the index command."""

    class bank_c(Struct):
        """Configuration for indexing a bank of pangenomes."""

        kmer_size: int = field(default=21)
        scaled: int = field(default=1000)
        nb_hash: int = field(default=0)
        threads: int = field(default=1)

    class pangenome_c(Struct):
        """Configuration for indexing a single pangenome."""

        kmer_size: int = field(default=21)
        annotation_type: str = field(default="rd_brwt")
        filter: str = field(default="all")
        tmp: str = field(default="/tmp/MetaPanG")
        threads: int = field(default=1)

    bank: bank_c = field(default_factory=bank_c)
    pangenome: pangenome_c = field(default_factory=pangenome_c)


class metapang_configure_c(Struct):
    """Configuration for the configure command."""

    class show_c(Struct):
        """Configuration for the configure show subcommand."""

        source: bool = field(default=False)
        format: str = field(default="yaml")
        test: str = field(default="")

    class template_c(Struct):
        """Configuration for the configure template subcommand."""

        format: str = field(default="yaml")
        output: str = field(default="stdout")
        schema: bool = field(default=False)

    show: show_c = field(default_factory=show_c)
    template: template_c = field(default_factory=template_c)


class metapang_tools_c(Struct):
    """Configuration for the tools command group."""

    class pg_dump_c(Struct):
        """Configuration for the pg_dump tool."""

        class fams_c(Struct):
            """Configuration for dumping gene families."""

            compress: bool = field(default=False)
            filter: str = field(default="all")
            split: bool = field(default=False)

        class genes_c(Struct):
            """Configuration for dumping genes."""

            compress: bool = field(default=False)
            filter: str = field(default="all")

        class reprs_c(Struct):
            """Configuration for dumping representative sequences."""

            compress: bool = field(default=False)
            filter: str = field(default="all")

        fams: fams_c = field(default_factory=fams_c)
        genes: genes_c = field(default_factory=genes_c)
        reprs: reprs_c = field(default_factory=reprs_c)

    pg_dump: pg_dump_c = field(default_factory=pg_dump_c)


class metapang_commands_c(Struct):
    """Configuration aggregating all MetaPanG command settings."""

    configure: metapang_configure_c = field(default_factory=metapang_configure_c)
    tools: metapang_tools_c = field(default_factory=metapang_tools_c)
    index: metapang_index_c = field(default_factory=metapang_index_c)
    search: metapang_search_c = field(default_factory=metapang_search_c)
    profile: metapang_profile_c = field(default_factory=metapang_profile_c)


class MetaPanG_Config(Struct):
    """Top-level configuration for MetaPanG."""

    pangbank: PanGBank_Config = field(default_factory=PanGBank_Config)
    commands: metapang_commands_c = field(default_factory=metapang_commands_c)


def read_configuration_from_file(path: Path) -> dict:
    """Read and decode a configuration file into a dict."""
    if not path.exists():
        return {}

    ext = path.suffix.lower()

    decoder = METAPANG_CONFIG_DECODERS.get(ext, None)
    if decoder is None:
        raise MetaPanG_ConfigError(f"Unsupported config file extension: {ext}")
    else:
        try:
            with open(path, "rb") as f:
                return decoder.decode(f.read(), type=dict)
        except Exception as e:
            raise MetaPanG_ConfigError(f"Failed to read config from {path}: {e}") from e


def merge_configuration_data(base: dict, override: dict) -> dict:
    """Recursively merge override values onto base configuration data."""
    result = base.copy()
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = merge_configuration_data(result[k], v)
        else:
            result[k] = v
    return result


def configuration_envs() -> dict[str, tp.Any]:
    """Return the environment variable names mapping to configuration fields."""

    def collect_envs(data: dict, env: dict[str, tp.Any], prefix="METAPANG_") -> None:
        for k, v in data.items():
            if isinstance(v, dict):
                collect_envs(v, env, prefix + k.upper() + "_")
            else:
                env[prefix + k.upper()] = os.environ.get(prefix + k.upper())

    as_dict = msgspec.to_builtins(MetaPanG_Config())
    envs = {}
    collect_envs(as_dict, envs)
    return envs


def apply_env_overrides(
    data: dict, sources: dict, env_prefix: str = "METAPANG_"
) -> dict:
    """Override configuration values from matching environment variables."""
    for k, v in data.items():
        env_key = env_prefix + k.upper()
        if isinstance(v, dict):
            data[k] = apply_env_overrides(
                v,
                sources[k],
                env_prefix + k.upper() + "_" if k != "commands" else env_prefix,
            )
        elif env_key in os.environ:
            data[k] = convert(os.environ[env_key])
            sources[k] = f"{str(os.environ[env_key])} (from:{env_key})"
    return data


def set_configuration_source(sources: dict, override: dict, source: str) -> dict:
    """Record the origin of each configuration value for provenance tracking."""
    for k, v in override.items():
        if isinstance(v, dict):
            sources[k] = set_configuration_source(sources.get(k, {}), v, source)
        else:
            if source == "default":
                sources[k] = v
            else:
                sources[k] = f"{v} (from:{source})"
    return sources


def validate_schema(data: dict, schema: dict, source: str):
    """Validate configuration data against a JSON schema."""
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        raise MetaPanG_ConfigError(
            f"Configuration validation error from '{source}': {e.message}"
        ) from e


def configuration(
    configuration_path: Path | None = None,
) -> tuple[MetaPanG_Config, dict[str, str]]:
    """Load the merged MetaPanG configuration and its value sources."""
    configuration_data = msgspec.to_builtins(MetaPanG_Config())
    sources = set_configuration_source({}, configuration_data, "default")

    schema = msgspec.json.schema(MetaPanG_Config)
    schema["$defs"]["MetaPanG_Config"]["additionalProperties"] = False

    for base_path in METAPANG_CONFIG_PATHS:
        for ext in METAPANG_CONFIG_DECODERS:
            path = base_path.with_suffix(ext)
            override_data = read_configuration_from_file(path)
            validate_schema(override_data, schema, str(path))
            sources = set_configuration_source(sources, override_data, str(path))
            configuration_data = merge_configuration_data(
                configuration_data, override_data
            )

    if configuration_path is not None and configuration_path.exists():
        override_data = read_configuration_from_file(configuration_path)
        validate_schema(override_data, schema, str(configuration_path))
        sources = set_configuration_source(
            sources, override_data, str(configuration_path)
        )
        configuration_data = merge_configuration_data(configuration_data, override_data)

    configuration_data = apply_env_overrides(configuration_data, sources, "METAPANG_")
    validate_schema(configuration_data, schema, "environment variables")
    return (
        msgspec.convert(configuration_data, type=MetaPanG_Config, strict=False),
        sources,
    )


def configuration_template(format: str) -> str:
    """Render a default configuration template in the requested format."""
    default = MetaPanG_Config()
    as_dict = msgspec.to_builtins(default)

    match format.lower():
        case "json":
            return msgspec.json.format(msgspec.json.encode(as_dict)).decode()
        case "yaml":
            return msgspec.yaml.encode(as_dict).decode()
        case "toml":
            return msgspec.toml.encode(as_dict).decode()
        case _:
            raise MetaPanG_ConfigError(
                f"Unsupported configuration template format: {format}"
            )


def configuration_schema() -> str:
    """Return the JSON schema for the MetaPanG configuration."""
    json = msgspec.json.encode(msgspec.json.schema(MetaPanG_Config))
    return msgspec.json.format(json).decode()
