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
import os


def main() -> int:
    icon_path = "cloudseed.ico" if os.path.exists("cloudseed.ico") else None
    version_file = "version.txt" if os.path.exists("version.txt") and sys.platform == "win32" else None
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "cloudseed",
        "--clean",
        "--noconfirm",
    ]
    
    # Add icon for Windows
    if icon_path:
        cmd.extend(["--icon", icon_path])
    
    # Add version info for Windows EXE
    if version_file:
        cmd.extend(["--version-file", version_file])
    
    cmd.append("cloudseed/__main__.py")
    
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
