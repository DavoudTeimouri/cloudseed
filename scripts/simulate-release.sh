#!/usr/bin/env bash
# Dry-run the release metadata that .github/workflows/release.yml computes.
#
# The release workflow resolves the version from the tag, decides whether the
# release is a pre-release, and extracts the matching CHANGELOG section. Those
# three steps are where a release silently goes wrong: a pre-release tag used
# to produce an empty changelog body and a stable release, and the API
# rejects a pre-release that is also marked as the latest one.
#
# This script runs the real step scripts, extracted from the real workflow,
# against the real CHANGELOG, so the result can be checked without publishing
# anything.
#
# Usage: scripts/simulate-release.sh [tag ...]
#        (no arguments checks the version in the workspace Cargo.toml)

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$REPO/.github/workflows/release.yml"
CHANGELOG="$REPO/CHANGELOG.md"

if [ ! -f "$WORKFLOW" ]; then
    echo "error: $WORKFLOW not found" >&2
    exit 1
fi

# Extract a `run:` block from the workflow, stripped of its YAML indentation.
extract_step() {
    local start="$1" end="$2"
    awk -v s="$start" -v e="$end" '
        $0 ~ "- name: " s { found=1; next }
        found && $0 ~ "- name: " e { exit }
        found && !run && /run: *\|/ { run=1; next }
        found && run { print }
    ' "$WORKFLOW" | sed 's/^          //'
}

RESOLVE=$(extract_step "Resolve version" "Generate Changelog")
CHANGELOG_STEP=$(extract_step "Generate Changelog" "Create Release and Upload")

if [ -z "$RESOLVE" ] || [ -z "$CHANGELOG_STEP" ]; then
    echo "error: could not extract the release steps from the workflow" >&2
    exit 1
fi

check_tag() {
    local tag="$1"
    local work
    work=$(mktemp -d)
    trap 'rm -rf "$work"' RETURN

    # The runner substitutes the expression with the tag name.
    echo "$RESOLVE" \
        | sed "s#\${{ github.event.inputs.tag || github.ref_name }}#$tag#" \
        > "$work/resolve.sh"

    export GITHUB_OUTPUT="$work/output.txt"
    : > "$GITHUB_OUTPUT"
    ( cd "$work" && bash resolve.sh )

    local base prerelease make_latest
    base=$(grep '^base=' "$GITHUB_OUTPUT" | cut -d= -f2)
    prerelease=$(grep '^prerelease=' "$GITHUB_OUTPUT" | cut -d= -f2)
    make_latest=$(grep '^make_latest=' "$GITHUB_OUTPUT" | cut -d= -f2)

    echo "$CHANGELOG_STEP" \
        | sed "s#\${{ steps.version.outputs.base }}#$base#" \
        > "$work/changelog.sh"
    cp "$CHANGELOG" "$work/CHANGELOG.md"
    ( cd "$work" && bash changelog.sh )

    local body
    body=$(sed -n '/^changelog<<EOF$/,/^EOF$/p' "$GITHUB_OUTPUT")

    echo "tag:            $tag"
    echo "  base:         $base"
    echo "  prerelease:   $prerelease"
    echo "  make_latest:  $make_latest"
    echo "  body lines:   $(printf '%s\n' "$body" | grep -c . || true)"

    local failed=0
    [ -n "$base" ] || { echo "  FAIL: no base version"; failed=1; }
    [ -n "$prerelease" ] || { echo "  FAIL: no prerelease flag"; failed=1; }
    [ -n "$make_latest" ] || { echo "  FAIL: no make_latest flag"; failed=1; }
    if [ -z "$body" ]; then
        echo "  FAIL: the changelog body is empty"
        failed=1
    fi
    # A pre-release must not be marked as the latest release.
    if [ "$prerelease" = "true" ] && [ "$make_latest" != "false" ]; then
        echo "  FAIL: a pre-release cannot be the latest release"
        failed=1
    fi
    return $failed
}

if [ $# -gt 0 ]; then
    for tag in "$@"; do
        check_tag "$tag" || exit 1
        echo
    done
else
    version=$(grep -m1 '^version = ' "$REPO/Cargo.toml" | sed -E 's/.*"([^"]+)".*/\1/')
    check_tag "v$version" || exit 1
fi
