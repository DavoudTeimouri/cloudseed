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
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "cloudseed",
        "--clean",
        "--noconfirm",
    ]
    
    # Add icon for Windows
    if icon_path and sys.platform == "win32":
        cmd.extend(["--icon", icon_path])
    elif icon_path and os.name != "nt":
        # On Linux, we can still embed the icon for cross-compilation scenarios
        cmd.extend(["--icon", icon_path])
    
    cmd.append("cloudseed/__main__.py")
    
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
