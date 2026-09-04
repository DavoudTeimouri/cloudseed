#!/usr/bin/env python3
"""Release automation: bump version across all files, update CHANGELOG."""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
VERSION_FILES = {
    ROOT / "cloudseed" / "__init__.py": r'__version__\s*=\s*"([^"]+)"',
    ROOT / "pyproject.toml": r'version\s*=\s*"([^"]+)"',
    ROOT / "version.txt": r'^(\d+\.\d+\.\d+)$',
}
CHANGELOG = ROOT / "CHANGELOG.md"


def read_version(file: Path, pattern: str) -> str:
    content = file.read_text(encoding="utf-8")
    m = re.search(pattern, content, re.MULTILINE)
    if not m:
        raise ValueError(f"Version not found in {file}")
    return m.group(1)


def write_version(file: Path, pattern: str, new_version: str) -> None:
    content = file.read_text(encoding="utf-8")
    content = re.sub(pattern, lambda m: m.group(0).replace(m.group(1), new_version), content)
    file.write_text(content, encoding="utf-8")


def update_changelog(new_version: str, date: str) -> None:
    """Prepend new version section to CHANGELOG."""
    content = CHANGELOG.read_text(encoding="utf-8")
    new_section = f"""## [{new_version}] - {date}

### Added
- 

### Changed
- 

### Fixed
- 

"""
    lines = content.splitlines(keepends=True)
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("## ["):
            insert_idx = i
            break
    lines.insert(insert_idx, new_section)
    CHANGELOG.write_text("".join(lines), encoding="utf-8")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/release.py <new_version> [date]")
        print("Example: python scripts/release.py 2.0.3 2026-09-05")
        return 1

    new_version = sys.argv[1]
    if not re.match(r"^\d+\.\d+\.\d+$", new_version):
        print("Error: version must be X.Y.Z")
        return 1

    date = sys.argv[2] if len(sys.argv) > 2 else __import__("datetime").date.today().isoformat()

    # Verify all version files have same version
    versions = {}
    for file, pattern in VERSION_FILES.items():
        if file.exists():
            versions[file] = read_version(file, pattern)
        else:
            print(f"Warning: {file} not found")

    if len(set(versions.values())) > 1:
        print("Error: version mismatch across files:")
        for f, v in versions.items():
            print(f"  {f}: {v}")
        return 1

    old_version = list(versions.values())[0] if versions else "0.0.0"
    print(f"Bumping version: {old_version} -> {new_version}")

    # Update all version files
    for file, pattern in VERSION_FILES.items():
        if file.exists():
            write_version(file, pattern, new_version)
            print(f"  Updated {file}")

    # Update CHANGELOG
    update_changelog(new_version, date)
    print(f"  Updated {CHANGELOG}")

    print("\nDone. Review changes, then commit and tag:")
    print(f"  git add {' '.join(str(f.relative_to(ROOT)) for f in VERSION_FILES) + ' CHANGELOG.md'}")
    print(f"  git commit -m 'chore: release v{new_version}'")
    print(f"  git tag v{new_version}")
    print(f"  git push origin main --tags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
