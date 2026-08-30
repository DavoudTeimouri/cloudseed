"""CloudSeed Template Maker: prepare current machine as a VM template."""

from __future__ import annotations

import os
import sys
import platform
import subprocess
import shutil
from typing import Optional, List, Tuple
from pathlib import Path

from .model import print_section, print_info, print_warn, print_error, print_success, check_shutdown, _ask_bool, _ask, colorize, Colors, print_banner
from .cli import detect_cloud_init_version, get_cloud_init_compatibility


def detect_platform() -> str:
    """Detect virtualization platform."""
    # Check for VMware
    try:
        result = subprocess.run(
            ["systemd-detect-virt"], capture_output=True, text=True, timeout=5
        )
        virt = result.stdout.strip().lower()
        if "vmware" in virt:
            return "vsphere"
        elif "kvm" in virt or "qemu" in virt:
            return "kvm"
    except Exception:
        pass

    # Check /sys/class/dmi/id for VMware
    dmi_paths = [
        "/sys/class/dmi/id/product_name",
        "/sys/class/dmi/id/sys_vendor",
        "/sys/class/dmi/id/board_vendor",
    ]
    for p in dmi_paths:
        try:
            with open(p, 'r') as f:
                content = f.read().lower()
                if "vmware" in content:
                    return "vsphere"
        except Exception:
            pass

    # Check for cloud-init datasource
    try:
        result = subprocess.run(
            ["cloud-init", "query", "ds"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            ds = result.stdout.strip().lower()
            if "vmware" in ds or "vsphere" in ds:
                return "vsphere"
            elif "openstack" in ds or "configdrive" in ds:
                return "kvm"  # Could be KVM/OpenStack
    except Exception:
        pass

    return "physical"


def detect_os() -> str:
    """Detect guest OS type."""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    else:
        return "unknown"


def is_physical_machine() -> Tuple[bool, str]:
    """Check if running on physical hardware."""
    virt = "unknown"
    try:
        result = subprocess.run(
            ["systemd-detect-virt"], capture_output=True, text=True, timeout=5
        )
        virt = result.stdout.strip().lower()
    except Exception:
        pass

    if virt and virt != "none":
        return False, f"Virtual: {virt}"
    return True, "Physical (no virtualization detected)"


def is_admin() -> bool:
    """Check if running as root/Administrator."""
    try:
        if platform.system().lower() == "windows":
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.geteuid() == 0
    except Exception:
        return False


def clean_cloud_init() -> bool:
    """Clean cloud-init state on Linux."""
    print_section("Cleaning Cloud-Init", "Removing instance data, machine-id, SSH keys, logs")
    try:
        # cloud-init clean
        print_info("Running: cloud-init clean --machine-id --logs")
        subprocess.run(["cloud-init", "clean", "--machine-id", "--logs"], check=False)

        # Remove machine-id files
        for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
            if os.path.exists(path):
                os.remove(path)
                print_info(f"Removed: {path}")

        # Remove cloud-init instance data
        import glob
        for path in glob.glob("/var/lib/cloud/instance*"):
            shutil.rmtree(path, ignore_errors=True)
            print_info(f"Removed: {path}")

        # Remove SSH host keys
        for path in glob.glob("/etc/ssh/ssh_host_*"):
            os.remove(path)
            print_info(f"Removed: {path}")

        # Clear temp directories
        for path in ["/tmp", "/var/tmp"]:
            if os.path.exists(path):
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    try:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                    except Exception:
                        pass
        print_info("Cleared /tmp and /var/tmp")

        # Truncate logs
        for path in glob.glob("/var/log/*.log"):
            open(path, 'w').close()
        for path in glob.glob("/var/log/*/*.log"):
            open(path, 'w').close()
        print_info("Truncated /var/log/*")

        # Clear shell history
        for path in ["/root/.bash_history", "/home/*/.bash_history"]:
            for p in glob.glob(path):
                open(p, 'w').close()

        print_success("Cloud-init cleanup complete!")
        return True

    except Exception as e:
        print_error(f"Cleanup failed: {e}")
        return False


def clean_windows_for_template() -> bool:
    """Run Sysprep generalize for Windows template."""
    print_section("Windows Sysprep", "Generalizing Windows for templating (new SID, OOBE)")

    # Find sysprep-unattend.xml
    sysprep_paths = [
        r"C:\Windows\System32\Sysprep\sysprep-unattend.xml",
        r"C:\Windows\System32\Sysprep\unattend.xml",
        os.path.join(os.getcwd(), "sysprep-unattend.xml"),
    ]
    unattend = None
    for p in sysprep_paths:
        if os.path.exists(p):
            unattend = p
            break

    if not unattend:
        print_error("sysprep-unattend.xml not found. Generate it first with CloudSeed.")
        return False

    print_info(f"Using unattend: {unattend}")
    print_warn("Running Sysprep will SHUTDOWN this machine!")
    print_warn("Next boot will have: new Machine SID, OOBE, device redetection")

    try:
        cmd = ["sysprep.exe", "/generalize", "/oobe", "/shutdown", f"/unattend:{unattend}"]
        print_info(f"Executing: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Sysprep failed: {e}")
        return False
    except Exception as e:
        print_error(f"Sysprep error: {e}")
        return False


def remove_cloudseed() -> bool:
    """Remove CloudSeed from the system."""
    print_section("Remove CloudSeed", "Removing CloudSeed configuration and scripts")
    try:
        paths_to_remove = [
            "/etc/cloud/cloud.cfg.d/99-cloudseed*.cfg",
            "/var/lib/cloudseed",
            "/opt/cloudseed",
        ]
        import glob
        for pattern in paths_to_remove:
            for path in glob.glob(pattern):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                print_info(f"Removed: {path}")
        print_success("CloudSeed removed!")
        return True
    except Exception as e:
        print_error(f"Remove failed: {e}")
        return False


def generate_cleanup_script(os_type: str) -> bool:
    """Generate a cleanup script that can be run manually."""
    print_section("Generate Cleanup Script", f"Creating template cleanup script for {os_type.upper()}")

    try:
        if os_type == "linux":
            script_path = os.path.join(os.getcwd(), "cloudseed-template-cleanup-linux.sh")
            content = '''#!/bin/bash
# CloudSeed VM Template Cleanup Script (Linux)
# Run as root on VM BEFORE converting to template
# This script is safe to run multiple times

set -euo pipefail

echo "=== CloudSeed Template Cleanup (Linux) ==="

echo "Cleaning cloud-init state..."
cloud-init clean --machine-id --logs 2>/dev/null || true
rm -f /etc/machine-id /var/lib/dbus/machine-id
rm -rf /var/lib/cloud/instance*
rm -f /etc/ssh/ssh_host_*

echo "Clearing temp files..."
rm -rf /tmp/* /var/tmp/*

echo "Truncating logs..."
for f in /var/log/*.log /var/log/*/*.log; do
    [ -f "$f" ] && truncate -s 0 "$f"
done

echo "Clearing shell history..."
unset HISTFILE
history -c 2>/dev/null || true
for h in /root/.bash_history /home/*/.bash_history; do
    [ -f "$h" ] && truncate -s 0 "$h"
done

echo "=== Done. Now convert VM to template ==="'''
        else:
            script_path = os.path.join(os.getcwd(), "cloudseed-template-cleanup-windows.bat")
            content = '''@echo off
REM CloudSeed VM Template Cleanup Script (Windows)
REM Run as Administrator on VM BEFORE converting to template
REM This script is safe to run multiple times

echo === CloudSeed Template Cleanup (Windows) ===

echo Cleaning Event Logs...
wevtutil cl System 2>nul
wevtutil cl Security 2>nul
wevtutil cl Application 2>nul

echo Cleaning Windows Update cache...
if exist C:\Windows\SoftwareDistribution\Download rmdir /s /q C:\Windows\SoftwareDistribution\Download 2>nul

echo Cleaning temp files...
if exist C:\Windows\Temp rmdir /s /q C:\Windows\Temp 2>nul
mkdir C:\Windows\Temp 2>nul
if exist %TEMP% rmdir /s /q %TEMP% 2>nul
mkdir %TEMP% 2>nul

echo Cleaning cloudbase-init state...
if exist "C:\Program Files\Cloudbase Solutions\Cloudbase-Init\conf\cloudbase-init.conf" (
    REM Keep config but remove state
    if exist "C:\Program Files\Cloudbase Solutions\Cloudbase-Init\log\*" del /q "C:\Program Files\Cloudbase Solutions\Cloudbase-Init\log\*" 2>nul
)

echo === Done. Now run Sysprep and convert VM to template ==='''

        with open(script_path, 'w') as f:
            f.write(content)
        os.chmod(script_path, 0o755)
        print_success(f"Script created: {script_path}")
        print_info("Copy to target VM, run as root/Administrator, then convert to template")
        return True
    except Exception as e:
        print_error(f"Script generation failed: {e}")
        return False


def show_best_practices(os_type: str, virt_platform: str) -> None:
    """Show vendor-recommended best practices checklist."""
    print_section("Best Practices Checklist", f"Vendor-recommended VM template preparation ({os_type.upper()})")
    print()

    if os_type == "linux":
        print_info("Linux-specific (VMware/KVM/Physical):")
        print("  [ ] cloud-init clean --machine-id (removes instance-id, machine-id)")
        print("  [ ] rm -f /etc/machine-id /var/lib/dbus/machine-id")
        print("  [ ] rm -rf /var/lib/cloud/instance*")
        print("  [ ] rm -f /etc/ssh/ssh_host_* (regenerates on first boot)")
        print("  [ ] rm -f /var/log/journal/* /var/log/*.log /var/log/*/*.log")
        print("  [ ] touch /etc/machine-id (empty, systemd will regenerate)")
        print("  [ ] systemd-machine-id-setup (optional, recreates machine-id)")
        print("  [ ] truncate -s 0 /etc/hostname (or set to 'localhost')")
        print("  [ ] Clean package cache: apt clean / dnf clean all / zypper clean")
        print("  [ ] Remove udev persistent rules: rm -f /etc/udev/rules.d/70-persistent-net.rules")
        print("  [ ] VMware: Install open-vm-tools")
        print("  [ ] KVM: Install qemu-guest-agent")
        print()
    else:
        print_info("Windows-specific:")
        print("  [ ] Sysprep /generalize /oobe /shutdown (mandatory for cloning)")
        print("  [ ] Use unattend.xml with CopyProfile, DoNotCleanTaskBar")
        print("  [ ] Install Cloudbase-Init")
        print("  [ ] Remove Cloudbase-Init configs not for template")
        print("  [ ] Clear Event Logs: wevtutil cl System / cl Security / cl Application")
        print("  [ ] Remove Windows Update cache: C:\\Windows\\SoftwareDistribution\\Download")
        print("  [ ] Clean DriverStore: pnputil /delete-driver (old drivers)")
        print("  [ ] Clean Disk: cleanmgr /sageset:1 /sagerun:1")
        print("  [ ] VMware: Install VMware Tools")
        print("  [ ] KVM: Install qemu-guest-agent")
        print()

    print_info("vSphere-specific:")
    print("  [ ] Customization Spec: hostname, domain, DNS, time zone")
    print("  [ ] Network: DHCP or static IP per NIC (preserve MAC vNICs)")
    print("  [ ] Remove vSphere Guest Customization leftovers")
    print("  [ ] Remove CD/DVD and floppy from VM before template")
    print("  [ ] Disable 'Synchronize guest time with host' if using NTP")
    print()

    print_info("KVM-specific:")
    print("  [ ] virt-sparsify / qemu-img convert for thin provisioning")
    print("  [ ] Remove MAC addresses from ifcfg-eth* (HWADDR)")
    print("  [ ] GRUB: GRUB_DISABLE_OS_PROBER=true, GRUB_TIMEOUT=0")
    print("  [ ] fstab: Use UUID or LABEL, not device paths")
    print()

    print_info("General (all platforms):")
    print("  [ ] Power OFF completely before marking as template")
    print("  [ ] Test template by deploying a clone")
    print("  [ ] Verify network, hostname, SSH, cloud-init on clone")
    print()


def template_maker_menu() -> int:
    """Main template maker menu."""
    while True:
        check_shutdown()
        
        # Detect system info
        os_type = detect_os()
        virt_platform = detect_platform()
        is_physical, phys_reason = is_physical_machine()
        admin = is_admin()

        print_banner("Template Maker (Prepare Current Machine as Template)")
        print_info(f"Detected OS: {os_type.upper()}")
        print_info(f"Detected Platform: {virt_platform.upper()}")
        print_info(f"Physical Machine: {'YES' if is_physical else 'NO'} ({phys_reason})")
        print_info(f"Running as Admin/Root: {'YES' if admin else 'NO'}")
        print()

        if is_physical:
            print_warn("This appears to be a PHYSICAL machine!")
            print_warn("Template Maker is designed for VIRTUAL MACHINES.")
            print_warn("Running on physical hardware is AT YOUR OWN RISK.")
            print()

        if os_type == "unknown":
            print_error("Unsupported operating system.")
            print()

        if not admin:
            print_warn("Not running as root/Administrator!")
            print_warn("Template preparation requires elevated privileges.")
            print()

        print(f"  {colorize('1', Colors.CYAN)}) Clean & Prepare Template (Linux: cloud-init clean, Windows: Sysprep)")
        print(f"  {colorize('2', Colors.CYAN)}) Show Best Practices Checklist")
        print(f"  {colorize('3', Colors.CYAN)}) Generate Cleanup Script (run manually later)")
        print(f"  {colorize('4', Colors.CYAN)}) Remove CloudSeed from System")
        print(f"  {colorize('0', Colors.GRAY)}) \u2190 Back Main Menu")
        print()

        choice = input(f"  {colorize('Select', Colors.BOLD)} [0]: ").strip() or "0"
        check_shutdown()

        if choice == "1":
            if is_physical:
                confirm = input("\u26a0\ufe0f  CONFIRM: PHYSICAL machine detected. Type 'PHYSICAL-OK' to proceed: ").strip()
                if confirm != "PHYSICAL-OK":
                    print_info("Cancelled.")
                    input("\nPress Enter to continue...")
                    continue
            if not admin:
                confirm = input("\u26a0\ufe0f  CONFIRM: Not running as root/Administrator. Type 'NO-ADMIN-OK' to proceed: ").strip()
                if confirm != "NO-ADMIN-OK":
                    print_info("Cancelled.")
                    input("\nPress Enter to continue...")
                    continue

            # Double confirm for production
            if is_physical or not admin:
                confirm2 = input("\u26a0\ufe0f  FINAL CONFIRM: This may render the system unusable. Type 'I-UNDERSTAND' to proceed: ").strip()
                if confirm2 != "I-UNDERSTAND":
                    print_info("Cancelled.")
                    input("\nPress Enter to continue...")
                    continue

            if os_type == "linux":
                if not admin:
                    print_error("Linux template prep requires root. Run with sudo.")
                else:
                    clean_cloud_init()
            elif os_type == "windows":
                if not admin:
                    print_error("Windows template prep requires Administrator. Run as Administrator.")
                else:
                    clean_windows_for_template()
            else:
                print_error(f"Unsupported OS: {os_type}")
            input("\nPress Enter to continue...")

        elif choice == "2":
            show_best_practices(os_type, virt_platform)
            input("\nPress Enter to continue...")

        elif choice == "3":
            generate_cleanup_script(os_type)
            input("\nPress Enter to continue...")

        elif choice == "4":
            confirm = _ask_bool("Remove CloudSeed from this machine?")
            if confirm:
                remove_cloudseed()
            input("\nPress Enter to continue...")

        elif choice == "0":
            return 0

        else:
            print_error("Invalid selection.")


if __name__ == "__main__":
    raise SystemExit(template_maker_menu())