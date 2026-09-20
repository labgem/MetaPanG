# Contributing to MetaPanG

This guide covers the development setup, the tooling, and
the conventions used in the repository.

## Development environment

`MetaPanG` uses [pixi](https://pixi.sh) to manage its environments. Because
`graph-tool` and `metagraph` link incompatible Boost versions, they live in two
separate environments that are wired together:


| Environment | Contents | Purpose |
| --- | --- | --- |
| `default` | python, graph-tool, numpy, editable `metapang`, pytest | run and test `MetaPanG` |
| `metagraph` | metagraph | the metagraph binary (added to the `default`/`dev` `PATH`) |
| `dev` | `default` + dev tools (ruff, pyright, pre-commit, ipython) + docs tools (sphinx, furo) | contributing |

Install every environment (this also builds the `metagraph` env that `default`/`dev`
put on the `PATH`):

```
pixi install --all
```

Enter the development shell:

```
pixi shell -e dev
```

If you use Nix, `nix develop` drops you into the same `dev` shell.

## Common tasks

Run with `pixi run <task>` (from any directory in the repo):

| Task | Command | Notes |
| --- | --- | --- |
| Run the CLI | `pixi run metapang --help` | |
| Tests | `pixi run test` | pytest, in the `default` env |
| Format | `pixi run format` | `ruff format .` |
| Format check | `pixi run format-check` | `ruff format --check .` |
| Lint | `pixi run lint` | `ruff check .` |
| Lint (autofix) | `pixi run lint-fix` | `ruff check --fix .` |
| Type check | `pixi run typecheck` | `pyright` |
| All checks | `pixi run check` | format-check + lint + typecheck |
| Build the docs | `pixi run docs` | HTML into `docs/_build/html` |
| Install git hooks | `pixi run install-hooks` | pre-commit, commit-msg, and pre-push |
| Build the Docker image | `pixi run docker` | tags `ghcr.io/labgem/metapang:<version>` and `:latest` |


## Type checking, formatting and linting

- **Formatting and linting**: [ruff](https://docs.astral.sh/ruff/), configured in
  `pyproject.toml`. Run
  `pixi run format` and `pixi run lint`.
- **Type checking**: [pyright](https://microsoft.github.io/pyright/) in `basic` mode
  (`[tool.pyright]`). Run `pixi run typecheck`. It runs in the `dev` env so imports
  resolve.

The same checks run in CI (`.github/workflows/lint.yml`, `typecheck.yml`,
`ci.yml`).

## Git hooks

Hooks live in `.git/hooks/`,

One `pixi` task installs everything (the pre-commit, commit-msg, and pre-push hooks):

```
pixi run install-hooks
```

This enables, on each commit:

- `ruff check` and `ruff format --check` (Python files)
- `pyright` (whole package)
- a version-consistency check (`metapang.__version__` must equal the `pixi.toml`
  version)
- a conventional-commit message check (see below)

and, on push, a check that a pushed version tag matches the repo version.

Run all hooks over the whole repo at any time:

```
pixi run -e dev pre-commit run --all-files
```

## Commit messages

Commit messages must follow [Conventional Commits](https://www.conventionalcommits.org). The type prefixes used here include `feat`, `fix`,
`docs`, `build`, `ci`, `refactor`, `test`, and `chore`.

## Versioning and releases

The version is stored in two places kept in sync: `metapang/__init__.py`
(`__version__`) and `pixi.toml` (`[workspace] version`). Do not edit them by hand,
use the bump script:

```
scripts/bump.sh --patch          # 0.1.0 -> 0.1.1
scripts/bump.sh --minor          # 0.1.0 -> 0.2.0
scripts/bump.sh --major          # 0.1.0 -> 1.0.0
scripts/bump.sh --minor --tag    # bump, commit, and create tag vX.Y.Z
```

Pushing a `vX.Y.Z` tag triggers `.github/workflows/release.yml`, which builds and
pushes the Docker image to GHCR and drafts a GitHub release.

## Documentation

The documentation is generated with Sphinx + MyST (Markdown) under `docs/`.

```
pixi run docs
```

