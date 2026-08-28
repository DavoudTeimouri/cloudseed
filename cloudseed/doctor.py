"""CloudSeed Cloud-Init Doctor: diagnose cloud-init issues on running systems."""

from __future__ import annotations

import os
import json
import subprocess
import sys
import platform
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from .model import print_section, print_info, print_warn, print_error, print_success, check_shutdown, colorize, Colors
from .cli import detect_cloud_init_version, get_cloud_init_compatibility


def run_cmd(cmd: List[str], timeout: int = 10) -> tuple:
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


def check_cloud_init_status() -> Dict[str, Any]:
    """Check cloud-init status and return structured info."""
    info = {
        "version": "not found",
        "status": "unknown",
        "enabled": False,
        "running": False,
        "last_boot": None,
        "errors": [],
        "warnings": [],
    }
    
    # Check version
    version = detect_cloud_init_version()
    info["version"] = version
    info["compatibility"] = get_cloud_init_compatibility(version)
    
    if version == "not found":
        info["errors"].append("cloud-init not installed")
        return info
    
    info["enabled"] = True
    
    # Check status
    rc, out, err = run_cmd(["cloud-init", "status", "--long"])
    if rc == 0:
        info["status"] = out.strip()
        if "running" in out.lower():
            info["running"] = True
    else:
        info["warnings"].append(f"cloud-init status failed: {err}")
    
    # Check cloud-init analyze
    rc, out, err = run_cmd(["cloud-init", "analyze", "show"])
    if rc == 0:
        info["analyze"] = out.strip()
    
    # Check for errors in logs
    log_paths = [
        "/var/log/cloud-init.log",
        "/var/log/cloud-init-output.log",
    ]
    
    for log_path in log_paths:
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r') as f:
                    content = f.read()
                
                # Look for errors
                error_lines = [l for l in content.split('\n') if 'ERROR' in l.upper() or 'FAIL' in l.upper()]
                if error_lines:
                    info["errors"].extend([f"{log_path}: {l.strip()}" for l in error_lines[-10:]])
                
                # Look for warnings
                warn_lines = [l for l in content.split('\n') if 'WARNING' in l.upper() or 'WARN' in l.upper()]
                if warn_lines:
                    info["warnings"].extend([f"{log_path}: {l.strip()}" for l in warn_lines[-10:]])
                    
            except Exception as e:
                info["warnings"].append(f"Could not read {log_path}: {e}")
    
    # Check cloud-init stages
    stages = [
        ("generator", "/var/lib/cloud/instance"),
        ("local", "/var/lib/cloud/instance/local"),
        ("network", "/var/lib/cloud/instance/network"),
        ("config", "/var/lib/cloud/instance/config"),
        ("final", "/var/lib/cloud/instance/final"),
    ]
    
    info["stages"] = {}
    for stage, path in stages:
        p = Path(path)
        info["stages"][stage] = {
            "completed": p.exists(),
            "path": str(p),
        }
        if p.exists():
            # Check for semaphore files
            semaphores = list(p.glob("*.json"))
            info["stages"][stage]["semaphores"] = [s.name for s in semaphores]
    
    return info


def check_cloud_config() -> Dict[str, Any]:
    """Check cloud-init configuration files."""
    info = {
        "config_files": [],
        "merged_config": None,
        "errors": [],
        "warnings": [],
    }
    
    config_dirs = [
        "/etc/cloud/cloud.cfg",
        "/etc/cloud/cloud.cfg.d",
        "/var/lib/cloud/instance/cloud-config.txt",
    ]
    
    for d in config_dirs:
        p = Path(d)
        if p.exists():
            if p.is_file():
                info["config_files"].append(str(p))
            elif p.is_dir():
                for f in p.glob("*.cfg"):
                    info["config_files"].append(str(f))
    
    # Get merged config
    rc, out, err = run_cmd(["cloud-init", "query", "--all"])
    if rc == 0:
        try:
            info["merged_config"] = json.loads(out)
        except json.JSONDecodeError:
            info["merged_config"] = out
    else:
        info["warnings"].append(f"Could not query merged config: {err}")
    
    return info


def check_boot_status() -> Dict[str, Any]:
    """Check boot and systemd status related to cloud-init."""
    info = {
        "services": {},
        "boot_time": None,
        "errors": [],
        "warnings": [],
    }
    
    # Check systemd services
    services = [
        "cloud-init-local.service",
        "cloud-init.service",
        "cloud-config.service",
        "cloud-final.service",
        "cloud-init-hotplugd.service",
    ]
    
    for svc in services:
        rc, out, err = run_cmd(["systemctl", "status", svc, "--no-pager"])
        info["services"][svc] = {
            "active": "active" in out.lower(),
            "status": out.strip()[:200],
        }
        if rc != 0 and "not found" not in err.lower() and "loaded" not in out.lower():
            info["warnings"].append(f"Service {svc}: {err[:100]}")
    
    # Get boot time
    rc, out, err = run_cmd(["systemd-analyze", "time"])
    if rc == 0:
        info["boot_time"] = out.strip()
    
    # Check for failed units
    rc, out, err = run_cmd(["systemctl", "--failed", "--no-pager"])
    if rc == 0 and out.strip():
        info["failed_units"] = out.strip()
        info["warnings"].append("Failed systemd units detected")
    
    return info


def check_network_config() -> Dict[str, Any]:
    """Check network configuration."""
    info = {
        "interfaces": {},
        "netplan": [],
        "networkd": {},
        "errors": [],
        "warnings": [],
    }
    
    # Check netplan
    netplan_dir = Path("/etc/netplan")
    if netplan_dir.exists():
        for f in netplan_dir.glob("*.yaml"):
            info["netplan"].append(str(f))
    
    # Check networkd
    networkd_dir = Path("/etc/systemd/network")
    if networkd_dir.exists():
        for f in networkd_dir.glob("*.network"):
            info["networkd"][f.name] = str(f)
    
    # Get current interfaces
    rc, out, err = run_cmd(["ip", "-j", "addr", "show"])
    if rc == 0:
        try:
            info["interfaces"] = json.loads(out)
        except json.JSONDecodeError:
            pass
    
    return info


def check_disk_space() -> Dict[str, Any]:
    """Check disk space for cloud-init operations."""
    info = {
        "partitions": [],
        "warnings": [],
    }
    
    rc, out, err = run_cmd(["df", "-h", "/", "/var", "/tmp"])
    if rc == 0:
        info["df_output"] = out.strip()
        
        # Parse for low space
        for line in out.strip().split('\n')[1:]:
            parts = line.split()
            if len(parts) >= 5:
                use_pct = parts[4].rstrip('%')
                try:
                    if int(use_pct) > 90:
                        info["warnings"].append(f"Low disk space: {parts[5]} at {use_pct}%")
                except ValueError:
                    pass
    else:
        info["errors"].append(f"df failed: {err}")
    
    return info


def diagnose_all() -> Dict[str, Any]:
    """Run full diagnosis."""
    print_section("Cloud-Init Doctor: Full Diagnosis", "Running comprehensive cloud-init health check...")
    print()
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "platform": platform.platform(),
        "cloud_init": check_cloud_init_status(),
        "cloud_config": check_cloud_config(),
        "boot": check_boot_status(),
        "network": check_network_config(),
        "disk": check_disk_space(),
    }
    
    # Summary
    total_errors = (
        len(results["cloud_init"]["errors"]) +
        len(results["cloud_config"]["errors"]) +
        len(results["boot"]["errors"]) +
        len(results["disk"]["errors"])
    )
    
    total_warnings = (
        len(results["cloud_init"]["warnings"]) +
        len(results["cloud_config"]["warnings"]) +
        len(results["boot"]["warnings"]) +
        len(results["network"]["warnings"]) +
        len(results["disk"]["warnings"])
    )
    
    print(f"\n{colorize('='*60, Colors.BLUE)}")
    print(f"{colorize('DIAGNOSIS SUMMARY', Colors.BOLD + Colors.BLUE)}")
    print(f"{colorize('='*60, Colors.BLUE)}")
    print(f"Timestamp: {results['timestamp']}")
    print(f"Platform: {results['platform']}")
    print(f"Cloud-init: {results['cloud_init']['version']} ({results['cloud_init']['compatibility']})")
    print(f"Status: {results['cloud_init']['status']}")
    print(f"Errors: {total_errors}")
    print(f"Warnings: {total_warnings}")
    print(f"{colorize('='*60, Colors.BLUE)}")
    
    if total_errors == 0 and total_warnings == 0:
        print_success("All checks passed!")
    else:
        if total_errors > 0:
            print_error("ERRORS found:")
            for cat in ["cloud_init", "cloud_config", "boot", "disk"]:
                for e in results[cat]["errors"]:
                    print(f"  - [{cat}] {e}")
        if total_warnings > 0:
            print_warn("WARNINGS:")
            for cat in ["cloud_init", "cloud_config", "boot", "network", "disk"]:
                for w in results[cat]["warnings"]:
                    print(f"  - [{cat}] {w}")
    
    return results


def doctor_menu() -> int:
    """Display Cloud-Init Doctor menu."""
    while True:
        check_shutdown()
        print_section("Cloud-Init Doctor", "Diagnose cloud-init issues on this system")
        print()
        print(f"  {colorize('1', Colors.CYAN)}) Full Diagnosis (all checks)")
        print(f"  {colorize('2', Colors.CYAN)}) Cloud-init Status & Version")
        print(f"  {colorize('3', Colors.CYAN)}) Cloud-init Configuration")
        print(f"  {colorize('4', Colors.CYAN)}) Boot & Service Status")
        print(f"  {colorize('5', Colors.CYAN)}) Network Configuration")
        print(f"  {colorize('6', Colors.CYAN)}) Disk Space")
        print(f"  {colorize('7', Colors.CYAN)}) Save Diagnosis Report (JSON)")
        print(f"  {colorize('0', Colors.GRAY)}) ← Back to Main Menu")
        print()
        
        choice = input(f"  {colorize('Select', Colors.BOLD)} [0]: ").strip() or "0"
        check_shutdown()
        
        if choice == "1":
            diagnose_all()
            input("\nPress Enter to continue...")
        elif choice == "2":
            info = check_cloud_init_status()
            print_section("Cloud-init Status")
            print_info(f"Version: {info['version']}")
            print_info(f"Compatibility: {info['compatibility']}")
            print_info(f"Status: {info['status']}")
            print_info(f"Enabled: {info['enabled']}")
            print_info(f"Running: {info['running']}")
            if info['errors']:
                print_warn("Errors:")
                for e in info['errors']:
                    print(f"  - {e}")
            if info['warnings']:
                print_warn("Warnings:")
                for w in info['warnings']:
                    print(f"  - {w}")
            if 'stages' in info:
                print_info("Stages:")
                for stage, data in info['stages'].items():
                    status = f"{colorize('✓', Colors.GREEN)}" if data['completed'] else f"{colorize('✗', Colors.RED)}"
                    print(f"  {status} {stage}: {data['path']}")
            input("\nPress Enter to continue...")
        elif choice == "3":
            info = check_cloud_config()
            print_section("Cloud-init Configuration")
            print_info(f"Config files found: {len(info['config_files'])}")
            for f in info['config_files']:
                print(f"  - {f}")
            if info['merged_config']:
                print_info("Merged config keys:")
                if isinstance(info['merged_config'], dict):
                    for k in info['merged_config'].keys():
                        print(f"  - {k}")
            if info['warnings']:
                print_warn("Warnings:")
                for w in info['warnings']:
                    print(f"  - {w}")
            input("\nPress Enter to continue...")
        elif choice == "4":
            info = check_boot_status()
            print_section("Boot & Service Status")
            if info.get('boot_time'):
                print_info(f"Boot time: {info['boot_time']}")
            print_info("Cloud-init services:")
            for svc, data in info['services'].items():
                status = f"{colorize('✓ Active', Colors.GREEN)}" if data['active'] else f"{colorize('✗ Inactive', Colors.RED)}"
                print(f"  {status}: {svc}")
            if 'failed_units' in info:
                print_warn(f"Failed units:\n{info['failed_units']}")
            if info['warnings']:
                print_warn("Warnings:")
                for w in info['warnings']:
                    print(f"  - {w}")
            input("\nPress Enter to continue...")
        elif choice == "5":
            info = check_network_config()
            print_section("Network Configuration")
            if info['netplan']:
                print_info("Netplan files:")
                for f in info['netplan']:
                    print(f"  - {f}")
            if info['networkd']:
                print_info("Networkd configs:")
                for name, path in info['networkd'].items():
                    print(f"  - {name}: {path}")
            if info['interfaces']:
                print_info("Interfaces:")
                for iface in info['interfaces']:
                    name = iface.get('ifname', 'unknown')
                    print(f"  - {name}")
            if info['warnings']:
                print_warn("Warnings:")
                for w in info['warnings']:
                    print(f"  - {w}")
            input("\nPress Enter to continue...")
        elif choice == "6":
            info = check_disk_space()
            print_section("Disk Space")
            if info.get('df_output'):
                print(info['df_output'])
            if info['warnings']:
                print_warn("Warnings:")
                for w in info['warnings']:
                    print(f"  - {w}")
            if info['errors']:
                print_error("Errors:")
                for e in info['errors']:
                    print(f"  - {e}")
            input("\nPress Enter to continue...")
        elif choice == "7":
            results = diagnose_all()
            filename = f"cloudseed-doctor-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
            try:
                with open(filename, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                print_success(f"Report saved to: {filename}")
            except Exception as e:
                print_error(f"Error saving report: {e}")
            input("\nPress Enter to continue...")
        elif choice == "0":
            return 0
        else:
            print_error("Invalid selection.")


if __name__ == "__main__":
    raise SystemExit(doctor_menu())