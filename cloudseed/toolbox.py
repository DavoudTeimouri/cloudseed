"""CloudSeed Toolbox: external tools and utilities."""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
import tempfile
import platform
from typing import Optional

from . import __version__
from .model import print_banner, check_shutdown


SID_TOOL_URL = "https://github.com/stratus/sidchanger/releases/download/v1.0.0/sidchanger.exe"
SID_TOOL_NAME = "sidchanger.exe"


def download_sid_tool(dest_dir: str) -> Optional[str]:
    """Download Windows SID changer tool (sidchanger.exe)."""
    print_banner("Toolbox: Download SID Changer")
    print("Downloading sidchanger.exe for Windows SID change without Sysprep...")
    print("Source: https://github.com/stratus/sidchanger")
    print()
    
    try:
        dest_path = os.path.join(dest_dir, SID_TOOL_NAME)
        
        # Check if already exists
        if os.path.exists(dest_path):
            overwrite = input(f"File exists at {dest_path}. Overwrite? [y/N]: ").strip().lower()
            if overwrite not in ("y", "yes"):
                print("Skipped.")
                return None
        
        print(f"Downloading to {dest_path}...")
        urllib.request.urlretrieve(SID_TOOL_URL, dest_path)
        print(f"Downloaded: {dest_path}")
        print()
        print("Usage on target Windows VM:")
        print(f"  1. Copy {SID_TOOL_NAME} to the VM")
        print("  2. Run as Administrator: sidchanger.exe")
        print("  3. Reboot the VM")
        print()
        print("Note: This changes the Machine SID without requiring Sysprep.")
        print("      Use only on cloned VMs that were NOT sysprepped.")
        return dest_path
    except Exception as e:
        print(f"Error downloading SID tool: {e}")
        return None


def run_sid_tool_windows() -> int:
    """Run SID changer on Windows (must run as Administrator)."""
    print_banner("Toolbox: Run SID Changer (Windows)")
    
    if platform.system().lower() != "windows":
        print("This tool only runs on Windows.")
        print("Use 'Download SID Changer' to get the .exe, then run it on the target Windows VM.")
        return 1
    
    # Check for sidchanger.exe in current dir or PATH
    tool_path = None
    for path in [".", os.path.dirname(sys.argv[0])]:
        test_path = os.path.join(path, SID_TOOL_NAME)
        if os.path.exists(test_path):
            tool_path = test_path
            break
    
    if not tool_path:
        # Try PATH
        for path in os.environ.get("PATH", "").split(os.pathsep):
            test_path = os.path.join(path, SID_TOOL_NAME)
            if os.path.exists(test_path):
                tool_path = test_path
                break
    
    if not tool_path:
        print(f"{SID_TOOL_NAME} not found.")
        print("Run 'Download SID Changer' from Toolbox first, or place sidchanger.exe in the same folder.")
        return 1
    
    # Check if running as admin
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False
    
    if not is_admin:
        print("ERROR: Must run as Administrator!")
        print("Right-click terminal -> Run as Administrator")
        return 1
    
    print(f"Running {tool_path}...")
    print("This will change the Machine SID. The system will need to reboot.")
    confirm = input("Continue? [y/N]: ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Cancelled.")
        return 0
    
    try:
        result = subprocess.run([tool_path], check=False)
        print(f"SID changer exited with code: {result.returncode}")
        if result.returncode == 0:
            print("SID changed successfully. Reboot required.")
        return result.returncode
    except Exception as e:
        print(f"Error running SID changer: {e}")
        return 1


def toolbox_menu() -> int:
    """Display toolbox menu and handle selection."""
    while True:
        check_shutdown()
        print_banner("Toolbox")
        print("External tools and utilities for VM customization.")
        print()
        print("  1) Download SID Changer (Windows - change SID without Sysprep)")
        print("  2) Run SID Changer (Windows - must be Administrator)")
        print("  3) Back to Main Menu")
        print()
        
        choice = input("Select [3]: ").strip() or "3"
        check_shutdown()
        
        if choice == "1":
            dest = input("Download directory [.]: ").strip() or "."
            download_sid_tool(dest)
            input("\nPress Enter to continue...")
        elif choice == "2":
            run_sid_tool_windows()
            input("\nPress Enter to continue...")
        elif choice == "3":
            return 0
        else:
            print("Invalid selection.")


if __name__ == "__main__":
    raise SystemExit(toolbox_menu())