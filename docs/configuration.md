# Configuration

`MetaPanG` uses a cascading configuration system so that stable defaults can be kept
in a file while individual runs, environments, or invocations override them without
editing that file. A parameter may be set at several levels. Each level overrides the
previous one. From lowest to highest precedence:

1. **system** (`~/.config/metapang-config.*`): user-wide defaults shared by every run,
   for example the cache directory or the `PanGBank` endpoint.
2. **local** (`.metapang-config.*` in the current working directory): settings specific
   to an analysis directory, kept alongside its data.
3. **cli** (a file passed with `metapang --config <path>`): a configuration selected
   explicitly for a given run.
4. **environment** (variables of the form `METAPANG_<CMD>_<SUBCMD>_<PARAM>`): transient
   overrides, convenient in scripts, containers, or job schedulers.
5. **option** (a command-line option, `--param <value>`): a one-off override for a
   single invocation.

Configuration files may be written in TOML, JSON, or YAML. A template, or the
configuration schema, can be produced with:

```
metapang configure template            # commented template
metapang configure template --schema   # JSON schema
```

The resolved configuration, and the origin of each value, can be inspected with:

```
metapang configure show        # the effective configuration
metapang configure show -s     # the same, annotated with the source of each value
```

## File structure

A configuration file has two top-level sections:

`pangbank`
: global settings such as the cache directory and the `PanGBank` endpoint.

`commands`
: per-command defaults, keyed by command then option. A top-level command like
  `profile` is `commands.profile.<option>`. A nested one like `search bank` is
  `commands.search.bank.<option>`.

You only need to set the values you want to change. Everything else keeps its
default. The following file sets the cache directory and a few `profile` defaults,
shown in each supported format.

### YAML

```yaml
pangbank:
  cache_directory: /shared/metapang-cache
  api_endpoint: https://pangbank-api.genoscope.cns.fr

commands:
  profile:
    threads: 8
    stop_rule: cv_paired
    k_max: 12
  search:
    bank:
      threshold_genome: 0.5
```

### TOML

```toml
[pangbank]
cache_directory = "/shared/metapang-cache"
api_endpoint = "https://pangbank-api.genoscope.cns.fr"

[commands.profile]
threads = 8
stop_rule = "cv_paired"
k_max = 12

[commands.search.bank]
threshold_genome = 0.5
```

### JSON

```json
{
  "pangbank": {
    "cache_directory": "/shared/metapang-cache",
    "api_endpoint": "https://pangbank-api.genoscope.cns.fr"
  },
  "commands": {
    "profile": {
      "threads": 8,
      "stop_rule": "cv_paired",
      "k_max": 12
    },
    "search": {
      "bank": {
        "threshold_genome": 0.5
      }
    }
  }
}
```

The format is chosen by the file extension (`.yaml`/`.yml`, `.toml`, or `.json`). A
full commented template listing every option is produced with
`metapang configure template`.

## Cache location

Downloaded pangenomes and indices are cached under `.metapang-cache` in the current
directory by default. The location is set by the `pangbank.cache_directory` parameter,
for example in a system configuration file:

```toml
[pangbank]
cache_directory = "/shared/metapang-cache"
```

or through the corresponding environment variable:

```
export METAPANG_PANGBANK_CACHE_DIRECTORY=/shared/metapang-cache
```

On a shared system, pointing several users at the same directory lets them share a
single cache. Downloads are file-locked, so concurrent runs may safely populate it.
