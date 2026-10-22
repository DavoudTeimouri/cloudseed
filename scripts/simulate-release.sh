#!/usr/bin/env bash
# Dry-run the release metadata that .github/workflows/release.yml computes.
#
# The release workflow resolves the version from the tag, decides whether the
# release is a pre-release, extracts the matching CHANGELOG section, and
# builds the API payload. Those steps are where a release silently goes wrong:
# a pre-release tag used to produce an empty changelog body and a stable
# release, and the API rejects a pre-release that is also marked as the latest
# one.
#
# This script runs the real step scripts, extracted from the real workflow,
# against the real CHANGELOG, and checks the resulting payload, so the release
# can be verified without publishing anything.
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

# The awk implementations to test the changelog step against.
awk_impls() {
    local found=""
    for impl in awk gawk mawk; do
        if command -v "$impl" >/dev/null 2>&1; then
            found="$found $impl"
        fi
    done
    echo "$found"
}

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
CHANGELOG_STEP=$(extract_step "Generate Changelog" "Build the release payload")

for step in "$RESOLVE" "$CHANGELOG_STEP"; do
    if [ -z "$step" ]; then
        echo "error: could not extract the release steps from the workflow" >&2
        exit 1
    fi
done

check_tag() {
    local tag="$1"
    local work
    work=$(mktemp -d)
    trap 'rm -rf "$work"' RETURN

    # The runner substitutes the expressions with the real values.
    echo "$RESOLVE" \
        | sed "s#\${{ github.event.inputs.tag || github.ref_name }}#$tag#" \
        > "$work/resolve.sh"

    export GITHUB_OUTPUT="$work/output.txt"
    : > "$GITHUB_OUTPUT"
    ( cd "$work" && bash resolve.sh )

    local base prerelease make_latest failed=0
    base=$(grep '^base=' "$GITHUB_OUTPUT" | cut -d= -f2)
    prerelease=$(grep '^prerelease=' "$GITHUB_OUTPUT" | cut -d= -f2)
    make_latest=$(grep '^make_latest=' "$GITHUB_OUTPUT" | cut -d= -f2)

    echo "$CHANGELOG_STEP" \
        | sed "s#\${{ steps.version.outputs.base }}#$base#" \
        > "$work/changelog.sh"
    cp "$CHANGELOG" "$work/CHANGELOG.md"

    # The changelog step must produce the same result under every awk
    # implementation available. The runners use gawk, which processes escape
    # sequences in -v assignments, while many local systems have mawk, which
    # does not. A step that only works under one of them breaks in CI and
    # passes locally.
    for awk_impl in $(awk_impls); do
        mkdir -p "$work/bin-$awk_impl"
        ln -sf "$(command -v "$awk_impl")" "$work/bin-$awk_impl/awk"
        (
            cd "$work"
            PATH="$work/bin-$awk_impl:$PATH" bash changelog.sh
        )
        if [ ! -s "$work/changelog.md" ]; then
            echo "  FAIL: the changelog step produced nothing under $awk_impl"
            failed=1
        else
            echo "  awk:        $awk_impl ok"
        fi
    done
    if [ "$failed" -ne 0 ]; then
        return 1
    fi

    # The payload is built by the same script the workflow runs.
    (
        cd "$work"
        python3 "$REPO/scripts/make-release-payload.py" \
            --tag "$tag" \
            --prerelease "$prerelease" \
            --make-latest "$make_latest" \
            --changelog changelog.md \
            --out release.json > /dev/null
    )

    echo "tag:            $tag"
    echo "  base:         $base"
    echo "  prerelease:   $prerelease"
    echo "  make_latest:  $make_latest"
    echo "  body lines:   $(grep -c . "$work/changelog.md" || true)"

    local failed=0
    [ -n "$base" ] || { echo "  FAIL: no base version"; failed=1; }
    [ -n "$prerelease" ] || { echo "  FAIL: no prerelease flag"; failed=1; }
    [ -n "$make_latest" ] || { echo "  FAIL: no make_latest flag"; failed=1; }
    if [ ! -s "$work/changelog.md" ]; then
        echo "  FAIL: the changelog body is empty"
        failed=1
    fi
    # A pre-release must not be marked as the latest release.
    if [ "$prerelease" = "true" ] && [ "$make_latest" != "false" ]; then
        echo "  FAIL: a pre-release cannot be the latest release"
        failed=1
    fi

    # The payload must be valid JSON with the fields the API needs.
    if ! python3 - "$work/release.json" "$tag" "$prerelease" "$make_latest" <<'PY'
import json
import sys

path, tag, prerelease, make_latest = sys.argv[1:5]
with open(path, encoding="utf-8") as handle:
    payload = json.load(handle)

problems = []
if payload.get("tag_name") != tag:
    problems.append("tag_name is %r" % payload.get("tag_name"))
if payload.get("prerelease") is not (prerelease == "true"):
    problems.append("prerelease is %r" % payload.get("prerelease"))
if payload.get("make_latest") != make_latest:
    problems.append("make_latest is %r" % payload.get("make_latest"))
if payload.get("draft") is not False:
    problems.append("draft is %r" % payload.get("draft"))
if not payload.get("body", "").strip():
    problems.append("the body is empty")
if payload.get("prerelease") and payload.get("make_latest") == "true":
    problems.append("a pre-release cannot be the latest release")

if problems:
    for problem in problems:
        print("  FAIL: " + problem)
    sys.exit(1)
PY
    then
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
