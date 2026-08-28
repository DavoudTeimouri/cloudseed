"""CloudSeed Template Maker: prepare current machine as a VM template."""

from __future__ import annotations

import os
import sys
import platform
import subprocess
import shutil
from typing import Optional, List, Tuple
from pathlib import Path

from .model import print_section, print_info, print_warn, print_error, print_success, check_shutdown, _ask_bool, _ask, colorize, Colors
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
        if virt == "none":
            return True, "systemd-detect-virt reports 'none' (physical hardware)"
    except Exception:
        pass
    
    # Check DMI
    try:
        with open("/sys/class/dmi/id/product_name", 'r') as f:
            product = f.read().strip().lower()
        if product in ("system product name", "to be filled by o.e.m.", ""):
            return True, f"DMI product name suggests physical: '{product}'"
    except Exception:
        pass
    
    return False, f"Virtualization detected: {virt}"


def check_root() -> bool:
    """Check if running as root/Administrator."""
    if platform.system().lower() == "windows":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False
    else:
        return os.geteuid() == 0


def clean_cloud_init() -> bool:
    """Clean cloud-init state for templating (Linux)."""
    print("Cleaning cloud-init state...")
    
    # cloud-init clean --machine-id
    rc, out, err = run_cmd(["cloud-init", "clean", "--machine-id"])
    if rc != 0:
        print(f"  Warning: cloud-init clean --machine-id failed: {err}")
        return False
    print("  cloud-init clean --machine-id: done")
    
    # Remove machine-id
    for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
        try:
            if os.path.exists(path):
                os.unlink(path)
                print(f"  Removed: {path}")
        except Exception as e:
            print(f"  Warning: could not remove {path}: {e}")
    
    # Remove cloud-init instance data
    import glob
    for path in glob.glob("/var/lib/cloud/instance*"):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
                print(f"  Removed directory: {path}")
        except Exception as e:
            print(f"  Warning: could not remove {path}: {e}")
    
    # Remove SSH host keys (will be regenerated on first boot)
    for key in glob.glob("/etc/ssh/ssh_host_*"):
        try:
            os.unlink(key)
            print(f"  Removed SSH key: {key}")
        except Exception as e:
            print(f"  Warning: could not remove {key}: {e}")
    
    print("Cloud-init state cleaned successfully.")
    return True


def clean_windows_for_template() -> bool:
    """Prepare Windows for templating (run Sysprep)."""
    print("Preparing Windows for templating...")
    
    # Check for Sysprep files
    sysprep_xml = Path("C:/Windows/System32/sysprep/unattend.xml")
    if not sysprep_xml.exists():
        # Check common locations
        for loc in ["C:/Temp/sysprep-unattend.xml", "C:/sysprep-unattend.xml", "./sysprep-unattend.xml"]:
            if Path(loc).exists():
                sysprep_xml = Path(loc)
                break
    
    if not sysprep_xml.exists():
        print("  ERROR: sysprep-unattend.xml not found.")
        print("  Generate it with CloudSeed first (Windows + Sysprep module).")
        return False
    
    print(f"  Found Sysprep answer file: {sysprep_xml}")
    print("  Running Sysprep generalize...")
    
    try:
        result = subprocess.run([
            "C:/Windows/System32/sysprep/sysprep.exe",
            "/generalize", "/oobe", "/shutdown",
            f"/unattend:{sysprep_xml}"
        ], check=False)
        
        if result.returncode == 0:
            print("  Sysprep completed. System will shutdown.")
            return True
        else:
            print(f"  Sysprep failed with exit code: {result.returncode}")
            return False
    except Exception as e:
        print(f"  Error running Sysprep: {e}")
        return False


def remove_cloudseed() -> bool:
    """Remove CloudSeed from the system."""
    print("Removing CloudSeed...")
    
    removed = False
    
    # Remove binary if in PATH
    for path in ["/usr/local/bin/cloudseed", "/usr/bin/cloudseed", "./cloudseed"]:
        try:
            if os.path.exists(path):
                os.unlink(path)
                print(f"  Removed binary: {path}")
                removed = True
        except Exception as e:
            print(f"  Warning: could not remove {path}: {e}")
    
    # Remove pip package
    try:
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "cloudseed"],
                       capture_output=True, timeout=30)
        print("  Removed pip package: cloudseed")
        removed = True
    except Exception:
        pass
    
    # Remove config directory
    config_dir = Path.home() / ".cloudseed"
    if config_dir.exists():
        try:
            shutil.rmtree(config_dir)
            print(f"  Removed config dir: {config_dir}")
            removed = True
        except Exception as e:
            print(f"  Warning: could not remove {config_dir}: {e}")
    
    if not removed:
        print("  CloudSeed not found in standard locations.")
    
    return True


def run_cmd(cmd: List[str], timeout: int = 30) -> Tuple[int, str, str]:
    """Run command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        return -1, "", "Command not found"
    except Exception as e:
        return -1, "", str(e)


def template_maker_menu() -> int:
    """Main template maker menu."""
    while True:
        check_shutdown()
        print_section("Template Maker", "Prepare CURRENT machine as a VM template")
        print()
        
        # Detect system info
        os_type = detect_os()
        virt_platform = detect_platform()
        is_physical, phys_reason = is_physical_machine()
        is_admin = check_root()
        
        print_info(f"Detected OS: {os_type.upper()}")
        print_info(f"Detected Platform: {virt_platform.upper()}")
        print_info(f"Physical Machine: {'YES' if is_physical else 'NO'} ({phys_reason})")
        print_info(f"Running as Admin/Root: {'YES' if is_admin else 'NO'}")
        print()
        
        if is_physical:
            print_warn("This appears to be a PHYSICAL machine!")
            print_warn("Template Maker is designed for VIRTUAL MACHINES.")
            print_warn("Running on physical hardware is AT YOUR OWN RISK.")
            print()
        
        if os_type == "unknown":
            print_error("Unsupported operating system.")
            print()
        
        if not is_admin:
            print_warn("Not running as root/Administrator!")
            print_warn("Template preparation requires elevated privileges.")
            print()
        
        print(f"  {colorize('1', Colors.CYAN)}) Prepare Linux template (clean cloud-init, remove SSH keys, machine-id)")
        print(f"  {colorize('2', Colors.CYAN)}) Prepare Windows template (run Sysprep generalize + shutdown)")
        print(f"  {colorize('3', Colors.CYAN)}) Remove CloudSeed from this machine")
        print(f"  {colorize('4', Colors.CYAN)}) Full template preparation (OS-specific + remove CloudSeed + poweroff)")
        print(f"  {colorize('5', Colors.CYAN)}) Configure template options (detailed sub-items)")
        print(f"  {colorize('0', Colors.GRAY)}) ← Back to Main Menu")
        print()
        
        choice = input(f"  {colorize('Select', Colors.BOLD)} [0]: ").strip() or "0"
        check_shutdown()
        
        if choice == "1":
            if os_type != "linux":
                print_error("This option is for Linux only.")
            elif is_physical:
                if not _ask_bool("WARNING: This is a PHYSICAL machine. Cleaning cloud-init/SSH keys may break the running system. Continue at your own risk?"):
                    print_info("Cancelled.")
                else:
                    clean_cloud_init()
            elif not is_admin:
                print_error("Requires root privileges. Run with sudo.")
            else:
                confirm = _ask_bool("This will clean cloud-init state and remove SSH host keys. Continue?")
                if confirm:
                    clean_cloud_init()
            input("\nPress Enter to continue...")
        
        elif choice == "2":
            if os_type != "windows":
                print_error("This option is for Windows only.")
            elif is_physical:
                if not _ask_bool("WARNING: This is a PHYSICAL machine. Running Sysprep generalize will RESET this machine (new SID, OOBE, shutdown). Continue at your own risk?"):
                    print_info("Cancelled.")
                else:
                    clean_windows_for_template()
            elif not is_admin:
                print_error("Requires Administrator privileges. Run as Administrator.")
            else:
                confirm = _ask_bool("This will run Sysprep generalize and SHUTDOWN the machine. Continue?")
                if confirm:
                    clean_windows_for_template()
            input("\nPress Enter to continue...")
        
        elif choice == "3":
            confirm = _ask_bool("Remove CloudSeed from this machine?")
            if confirm:
                remove_cloudseed()
            input("\nPress Enter to continue...")
        
        elif choice == "4":
            if is_physical:
                if not _ask_bool("WARNING: This is a PHYSICAL machine. Full preparation will clean OS state, remove CloudSeed, and POWEROFF. Continue at your own risk?"):
                    print_info("Cancelled.")
                    input("\nPress Enter to continue...")
                    continue
            
            if not is_admin:
                print_error("Requires root/Administrator privileges.")
                input("\nPress Enter to continue...")
                continue
            
            print_section("Full Template Preparation", f"OS: {os_type.upper()}, Platform: {virt_platform.upper()}")
            print()
            
            confirm = _ask_bool(
                "This will:\n"
                f"  - Prepare {os_type} for templating\n"
                "  - Remove CloudSeed\n"
                "  - POWEROFF the machine\n\n"
                "Continue?"
            )
            
            if not confirm:
                print_info("Cancelled.")
                input("\nPress Enter to continue...")
                continue
            
            success = True
            
            if os_type == "linux":
                success = clean_cloud_init()
            elif os_type == "windows":
                success = clean_windows_for_template()
            
            if success:
                remove_cloudseed()
                print_success("Template preparation complete.")
                print_info("Machine will now power off...")
                
                # Poweroff
                if os_type == "linux":
                    subprocess.run(["systemctl", "poweroff"])
                else:
                    subprocess.run(["shutdown", "/s", "/t", "0"])
            else:
                print_error("Template preparation failed. Machine NOT powered off.")
            
            input("\nPress Enter to continue...")
        
        elif choice == "5":
            _configure_template_options(os_type, is_physical, is_admin)
            input("\nPress Enter to continue...")
        
        elif choice == "0":
            return 0
        
        else:
            print_error("Invalid selection.")


def _configure_template_options(os_type: str, is_physical: bool, is_admin: bool) -> None:
    """Configure detailed template options."""
    print_section("Template Options", f"Detailed configuration for {os_type.upper()} template preparation")
    print()
    
    if os_type == "linux":
        print_info("Linux template preparation will:")
        print("  - Run 'cloud-init clean --machine-id' (removes instance data)")
        print("  - Remove /etc/machine-id and /var/lib/dbus/machine-id")
        print("  - Remove /var/lib/cloud/instance* (cloud-init instance data)")
        print("  - Remove ALL /etc/ssh/ssh_host_* keys (regenerated on first boot)")
        print("  - Clear /tmp and /var/tmp")
        print("  - Truncate /var/log/* logs")
        print()
        if is_physical:
            print_warn("On PHYSICAL machine: SSH keys removal will break existing SSH connections!")
            print_warn("Machine-id removal may affect services that depend on stable machine-id.")
            if not _ask_bool("Continue with physical machine cleanup?"):
                return
        if not is_admin:
            print_error("Requires root privileges. Run with sudo.")
            return
            
    elif os_type == "windows":
        print_info("Windows template preparation will:")
        print("  - Locate sysprep-unattend.xml (checks standard paths)")
        print("  - Run 'sysprep.exe /generalize /oobe /shutdown /unattend:<file>'")
        print("  - Machine will SHUTDOWN with generalized state")
        print("  - Next boot: new Machine SID, OOBE, device redetection")
        print()
        if is_physical:
            print_warn("On PHYSICAL machine: Sysprep will RESET this Windows installation!")
            print_warn("- New Machine SID generated")
            print_warn("- All device drivers re-detected")
            print_warn("- Machine goes through OOBE (Out-of-Box Experience)")
            print_warn("- MUST have local admin account to log in after reboot")
            if not _ask_bool("Continue with physical machine Sysprep?"):
                return
        if not is_admin:
            print_error("Requires Administrator privileges. Run as Administrator.")
            return
    
    print()
    print_info("Use options 1-4 to execute the preparation.")
    print_info("Option 4 = Full preparation + CloudSeed removal + Poweroff")


if __name__ == "__main__":
    raise SystemExit(template_maker_menu())