#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/bump.sh (--major | --minor | --patch) [--tag]

Bump the version in metapang/__init__.py and pixi.toml.

Options:
  --major   Bump to (X+1).0.0
  --minor   Bump to X.(Y+1).0
  --patch   Bump to X.Y.(Z+1)
  --tag     Also commit the bump (chore(release): vX.Y.Z) and create an
            annotated git tag vX.Y.Z
  -h, --help
EOF
}

part=""
do_tag=0
for arg in "$@"; do
    case "$arg" in
        --major | --minor | --patch)
            if [[ -n "$part" ]]; then
                echo "Error: give only one of --major/--minor/--patch" >&2
                exit 1
            fi
            part="${arg#--}"
            ;;
        --tag) do_tag=1 ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            echo "Error: unknown argument '$arg'" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ -z "$part" ]]; then
    echo "Error: one of --major, --minor, --patch is required" >&2
    usage >&2
    exit 1
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
init_file="$root/metapang/__init__.py"
pixi_file="$root/pixi.toml"

current="$(grep -oE '__version__ *= *"[0-9]+\.[0-9]+\.[0-9]+"' "$init_file" |
    grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)"
if [[ -z "$current" ]]; then
    echo "Error: could not read current version from $init_file" >&2
    exit 1
fi

IFS='.' read -r major minor patch <<<"$current"
case "$part" in
    major)
        major=$((major + 1))
        minor=0
        patch=0
        ;;
    minor)
        minor=$((minor + 1))
        patch=0
        ;;
    patch) patch=$((patch + 1)) ;;
esac
new="${major}.${minor}.${patch}"
tag="v${new}"

if [[ "$do_tag" -eq 1 ]] && git -C "$root" rev-parse -q --verify "refs/tags/$tag" >/dev/null 2>&1; then
    echo "Error: tag $tag already exists" >&2
    exit 1
fi

echo "Bumping version: $current -> $new"

sed_inplace() {
    if sed --version >/dev/null 2>&1; then
        sed -i "$@"
    else
        sed -i '' "$@"
    fi
}

sed_inplace -E "s/^__version__ *= *\"[0-9]+\.[0-9]+\.[0-9]+\"/__version__ = \"$new\"/" "$init_file"
sed_inplace -E "s/^version *= *\"[0-9]+\.[0-9]+\.[0-9]+\"/version = \"$new\"/" "$pixi_file"

echo "Updated:"
echo "  metapang/__init__.py"
echo "  pixi.toml"

if [[ "$do_tag" -eq 1 ]]; then
    git -C "$root" add "$init_file" "$pixi_file"
    git -C "$root" commit -m "chore(release): $tag"
    git -C "$root" tag -a "$tag" -m "$tag"
    echo "Committed bump and created tag $tag"
fi
