"""CloudSeed Toolbox: external tools and utilities."""

from __future__ import annotations

import os
import subprocess
import sys
import platform
from typing import Optional

from . import __version__
from .model import print_section, print_info, print_warn, print_error, print_success, check_shutdown, colorize, Colors


def show_sid_tool_info() -> int:
    """Show information about valid Windows SID change methods."""
    print_section("Windows SID Change Methods", "Official and recommended approaches for changing Machine SID")
    print()
    
    print_info("Official Microsoft recommendation: Use Sysprep /generalize")
    print("  This is the ONLY supported method for creating deployable Windows images.")
    print()
    print("  Steps:")
    print("  1. Install Windows and configure your base image")
    print("  2. Install Cloudbase-Init and place CloudSeed configs")
    print("  3. Run: sysprep.exe /generalize /oobe /shutdown /unattend:unattend.xml")
    print("  4. VM shuts down - capture as template/golden image")
    print("  5. Each deployed VM gets a unique SID on first boot")
    print()
    
    print_warn("Tools like 'NewSID' (Sysinternals) and 'sidchanger' are NOT supported by Microsoft")
    print("  - NewSID was officially retired by Mark Russinovich in 2011")
    print("  - Microsoft states: 'We do not support, test, or recommend any third-party tools'")
    print("  - Using unsupported tools can cause: WSUS issues, domain join failures,")
    print("    encryption problems, licensing issues, and application compatibility bugs")
    print()
    
    print_info("If you cloned a VM without Sysprep and need to fix SIDs:")
    print("  1. BEST: Rebuild the image properly with Sysprep")
    print("  2. Workaround: Use Sysprep on the cloned VM (run from recovery/env)")
    print("  3. Last resort: Manual SID change (not recommended for production)")
    print()
    print("  CloudSeed generates sysprep-unattend.xml and run-sysprep.bat")
    print("  for proper, Microsoft-supported image preparation.")
    print()
    
    input("Press Enter to continue...")
    return 0


def show_sysprep_guidance() -> int:
    """Show detailed Sysprep guidance."""
    print_section("Sysprep Guidance", "Proper Windows image preparation with Sysprep")
    print()
    
    print_info("CloudSeed generates these files for Windows:")
    print("  - sysprep-unattend.xml  : Unattend answer file (generalize + specialize + oobe)")
    print("  - run-sysprep.bat       : Launches Sysprep with correct parameters")
    print("  - cloudbase-init.conf   : Cloudbase-Init service configuration")
    print("  - cloudbase-init-unattend.conf : Unattend phase configuration")
    print()
    
    print_info("To prepare a Windows golden image:")
    print("  1. Install Windows on a VM")
    print("  2. Install Cloudbase-Init (https://cloudbase.it/cloudbase-init/)")
    print("  3. Copy generated .conf files to:")
    print("       C:\\Program Files\\Cloudbase Solutions\\Cloudbase-Init\\conf\\")
    print("  4. Copy sysprep-unattend.xml and run-sysprep.bat to C:\\Temp\\")
    print("  5. Run as Administrator: C:\\Temp\\run-sysprep.bat")
    print("  6. VM shuts down - convert to template in vSphere/KVM")
    print()
    
    print_warn("Important:")
    print("  - NEVER skip Sysprep when cloning Windows VMs")
    print("  - Duplicate SIDs break: Domain join, Group Policy, WSUS,")
    print("    File/Registry ACLs, Windows Activation, AppLocker")
    print("  - Sysprep /generalize resets: Machine SID, CMID (WSUS),")
    print("    Product activation grace, Device driver state")
    print()
    
    print_info("For vSphere: Enable 'Let Platform Handle...' modules")
    print("  - Platform sets hostname, network, domain, timezone")
    print("  - Cloud-init handles: users, packages, scripts only")
    print("  - Clean separation = no conflicts")
    print()
    
    input("Press Enter to continue...")
    return 0


def toolbox_menu() -> int:
    """Display toolbox menu and handle selection."""
    while True:
        check_shutdown()
        print_section("Toolbox", "Guidance and references for VM customization tools")
        print()
        print(f"  {colorize('1', Colors.CYAN)}) Windows SID Change - Official Methods")
        print(f"  {colorize('2', Colors.CYAN)}) Sysprep Guidance - Image Preparation")
        print(f"  {colorize('3', Colors.CYAN)}) Cloud-Init Version Compatibility Matrix")
        print(f"  {colorize('0', Colors.GRAY)}) ← Back to Main Menu")
        print()
        
        choice = input(f"  {colorize('Select', Colors.BOLD)} [0]: ").strip() or "0"
        check_shutdown()
        
        if choice == "1":
            show_sid_tool_info()
        elif choice == "2":
            show_sysprep_guidance()
        elif choice == "3":
            show_cloud_init_compat()
        elif choice == "0":
            return 0
        else:
            print_error("Invalid selection.")


def show_cloud_init_compat() -> int:
    """Show cloud-init version compatibility matrix."""
    print_section("Cloud-Init Version Compatibility", "Supported versions and feature availability")
    print()
    
    versions = [
        ("≥ 24.x", "✅ Full Support", "All modules, network v2, growpart, ntp"),
        ("23.x",   "✅ Full Support", "All modules, network v2, growpart, ntp"),
        ("22.x",   "✅ Supported",  "Minor network v2 syntax differences"),
        ("21.x",   "⚠️  Limited",    "Missing ntp, growpart modules"),
        ("< 21",   "❌ Not Supported", "Too old for modern config schema"),
    ]
    
    print(f"  {'Version':<10} {'Status':<18} Notes")
    print(f"  {'─'*10} {'─'*18} {'─'*50}")
    for ver, status, notes in versions:
        status_color = Colors.GREEN if "✅" in status else (Colors.YELLOW if "⚠️" in status else Colors.RED)
        print(f"  {colorize(ver, Colors.CYAN):<10} {colorize(status, status_color):<18} {notes}")
    print()
    
    print_info("Run 'cloud-init --version' on your target image to check")
    print_info("CloudSeed also provides: cloudseed --detect-cloud-init")
    print()
    
    input("Press Enter to continue...")
    return 0


if __name__ == "__main__":
    raise SystemExit(toolbox_menu())