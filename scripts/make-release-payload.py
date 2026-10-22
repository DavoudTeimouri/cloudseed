#!/usr/bin/env python3
"""Build the GitHub release payload for a tag.

The release workflow posts this payload to the GitHub API. It is kept in a
file rather than inline in the workflow so that the exact code that publishes
can also be run locally, by scripts/simulate-release.sh.
"""

import argparse
import json
import pathlib
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="the release tag, e.g. v2.2.0-rc.1")
    parser.add_argument(
        "--prerelease",
        default="false",
        help='"true" or "false"',
    )
    parser.add_argument(
        "--make-latest",
        default="true",
        help='"true" or "false"; a pre-release cannot be the latest release',
    )
    parser.add_argument("--changelog", default="changelog.md", help="the release body")
    parser.add_argument("--out", default="release.json", help="where to write the payload")
    args = parser.parse_args()

    if args.prerelease not in ("true", "false"):
        print("error: --prerelease must be true or false", file=sys.stderr)
        return 1
    if args.make_latest not in ("true", "false"):
        print("error: --make-latest must be true or false", file=sys.stderr)
        return 1

    body = pathlib.Path(args.changelog).read_text(encoding="utf-8")
    if not body.strip():
        print(f"error: {args.changelog} is empty", file=sys.stderr)
        return 1

    prerelease = args.prerelease == "true"
    if prerelease and args.make_latest != "false":
        print(
            "error: a pre-release cannot be the latest release",
            file=sys.stderr,
        )
        return 1

    payload = {
        "tag_name": args.tag,
        "name": "CloudSeed " + args.tag,
        "body": body,
        "draft": False,
        "prerelease": prerelease,
        "make_latest": args.make_latest,
    }

    text = json.dumps(payload, indent=2)
    pathlib.Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
