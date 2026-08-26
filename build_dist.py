"""Build a portable single-file CloudSeed executable with PyInstaller.

Usage:
    pip install pyinstaller
    python build_dist.py            # onefile, current OS
    python build_dist.py --onefile  # explicit

Output: dist/cloudseed  (Linux) or dist/cloudseed.exe (Windows).
No bundled Python dependency in the package itself — runtime is stdlib-only.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "cloudseed",
        "--clean",
        "--noconfirm",
        "cloudseed/__main__.py",
    ]
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
