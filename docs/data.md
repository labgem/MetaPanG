# Managing pangenome data

`MetaPanG` profiles against `PanGBank` collections. Two commands let you see what
is available and manage the files kept locally: `metapang list` to browse the
catalog, and `metapang cache` to inspect, pre-download, and remove cached data.

## `metapang list`

Browse the `PanGBank` catalog and check what this `MetaPanG` release supports.

With no argument it lists every collection and release:

```
metapang list
```

| Column | Meaning |
| --- | --- |
| `collection` | The collection name. |
| `version` | A release of that collection. |
| `pangenomes` | Number of species pangenomes in the release. |
| `supported` | Whether this `MetaPanG` release can profile against it (see [Collection compatibility](#collection-compatibility)). |
| `discarded` | How many species are discarded by default in that release. |
| `link` | The web page for the release. |

Passing a `collection[@version]` shows that release in detail, including the
species discarded by default and their reasons, plus a link to browse every
species on the web:

```
metapang list GTDB_refseq@2.0.0
```

The version defaults to `latest` when omitted.

Add `--open` to open the corresponding PanGBank web page in a browser (the release
page for a `collection[@version]`, or the `PanGBank` site otherwise). On a headless
machine where no browser can be launched, the URL is printed instead.

```
metapang list GTDB_refseq@2.0.0 --open
```

## `metapang cache`

The files needed for a run (the collection index, and the graph and pangenome of
each species) are downloaded from `PanGBank` on demand and cached locally, so each
resource is retrieved only once and reused by later runs.

### Where the cache lives

By default the cache is `.metapang-cache` in the working directory. It can be
relocated, in increasing order of precedence:

| Method | Scope |
| --- | --- |
| `cache_directory` in a config file (see [Configuration](configuration.md)) | Persistent |
| `METAPANG_PANGBANK_CACHE_DIRECTORY` environment variable | Per shell |
| `metapang cache --path DIR ...` | Per invocation |

```
metapang cache --path /data/metapang-cache list
```

`metapang cache path` prints the resolved directory.

### Inspecting the cache

`metapang cache list` shows the cached collections and their contents, one row per
item, with its kind (`index`, `pangenome`, or `dbg`), completeness status, and
size, followed by the cache total.

```
metapang cache list
```

### Pre-downloading with `fetch`

`metapang cache fetch` populates the cache ahead of time, so a later `profile` run
has everything it needs offline.

```
metapang cache fetch TARGET [OPTIONS]
```

`TARGET` is `collection[@version][:species[,species,...]]`.

- Without `:species`, only the release bank index is fetched. This is what species
  detection needs.
- With `:species`, each named species graph (and its pangenome) is fetched as well.
  This is what read mapping needs.

| Option | Default | Description |
| --- | --- | --- |
| `--index` / `--no-index` | on | Fetch the release bank index. |
| `--dbg` / `--no-dbg` | on | Fetch the de Bruijn graph of each named species. |
| `--pangenome` / `--no-pangenome` | on | Fetch the `.h5` pangenome of each named species. |
| `-f`, `--force` | off | Re-download even if already cached. |

```
# prepare for detection: the index only
metapang cache fetch GTDB_refseq@2.0.0

# prepare to profile two species end to end: index plus their graphs
metapang cache fetch GTDB_refseq@2.0.0:s__Klebsiella_pneumoniae,s__Abiotrophia_defectiva
```

An unsupported `collection@version` is rejected up front, and unknown species
names are reported before anything is downloaded. Already-cached items are kept
and reported as present unless `--force` is given.

### Clearing the cache

`metapang cache clear` removes the whole cache, or a subset given as
`collection[@version][:name]`.

```
# everything (asks for confirmation)
metapang cache clear

# one collection release
metapang cache clear GTDB_refseq@2.0.0

# a single species within a release
metapang cache clear GTDB_refseq@2.0.0:s__Abiotrophia_defectiva
```

Add `-y` to skip the confirmation prompt.

## Collection compatibility

Each `MetaPanG` release ships a compatibility policy that decides which
`PanGBank` collections it can profile against. Run [`metapang list`](#metapang-list)
to see, per release, whether it is supported and how many species are discarded.

**Supported versions.** A collection version this release was not validated
against is rejected up front, before any work is done:

```
metapang profile -q reads.fastq.gz -b GTDB_refseq@1.0.0
# Error: 'GTDB_refseq@1.0.0' is not compatible with this MetaPanG version
#        (supported versions: 2.0.0).
```

This is a hard check and cannot be overridden; upgrade or downgrade `MetaPanG`
to match the collection.

**Discarded species.** Within a supported version, some species may be
discarded by default (for example, unreliable pangenomes).

When any are excluded the `profile` run log lists them:

```
Excluding 1 discarded species from detection (use --include-discarded to include them):
  - s__Some_species: low quality pangenome
```

Unlike the version check, discards are overridable with `--include-discarded`:

```
# include every discarded species
metapang profile -q reads.fastq.gz -b GTDB_refseq@2.0.0 --include-discarded

# include only specific ones (comma-separated, note the '=')
metapang profile -q reads.fastq.gz -b GTDB_refseq@2.0.0 \
  --include-discarded=s__Some_species,s__Other_species
```

Naming a discarded species explicitly through the `:pangenomes` suffix of `-b`
also profiles it, since that skips detection entirely.
