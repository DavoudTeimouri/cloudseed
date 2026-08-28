"""CloudSeed Config Validator: validate exported configurations don't run after first boot."""

from __future__ import annotations

import os
import json
import sys
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

from .model import TemplateConfig, print_section, print_info, print_warn, print_error, print_success, check_shutdown, colorize, Colors


def _safe_load_yaml(content: str) -> Any:
    """Minimal YAML parser for cloud-config subset (stdlib only)."""
    # Remove comments and blank lines
    lines = []
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Remove inline comments
        if '#' in line:
            line = line.split('#')[0].rstrip()
        if line:
            lines.append(line)
    
    content = '\n'.join(lines)
    if not content:
        return {}
    
    # Simple parser for common cloud-config structures
    # Handles: key: value, key:, - item, nested dicts with 2-space indent
    def parse_value(v: str) -> Any:
        v = v.strip()
        if v.lower() in ('true', 'false'):
            return v.lower() == 'true'
        if v.lower() == 'null' or v == '~':
            return None
        # Number
        try:
            if '.' in v:
                return float(v)
            return int(v)
        except ValueError:
            pass
        # String (remove quotes)
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            return v[1:-1]
        return v
    
    def parse_mapping(lines: List[str], start: int, base_indent: int) -> tuple[Dict[str, Any], int]:
        result = {}
        i = start
        while i < len(lines):
            line = lines[i]
            indent = len(line) - len(line.lstrip())
            if indent < base_indent:
                break
            if indent > base_indent:
                # Should not happen in well-formed YAML
                i += 1
                continue
            
            stripped = line.strip()
            if stripped.startswith('- '):
                # List item - should be handled by caller
                break
            
            if ':' not in stripped:
                i += 1
                continue
            
            key, val = stripped.split(':', 1)
            key = key.strip()
            val = val.strip()
            
            if not val:
                # Could be nested mapping or list
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent > indent:
                        if next_line.strip().startswith('- '):
                            # List
                            items = []
                            j = i + 1
                            while j < len(lines):
                                lj = lines[j]
                                lj_indent = len(lj) - len(lj.lstrip())
                                if lj_indent < next_indent:
                                    break
                                if lj_indent == next_indent and lj.strip().startswith('- '):
                                    item_content = lj.strip()[2:].strip()
                                    items.append(parse_value(item_content))
                                j += 1
                            result[key] = items
                            i = j
                            continue
                        else:
                            # Nested mapping
                            nested, new_i = parse_mapping(lines, i + 1, next_indent)
                            result[key] = nested
                            i = new_i
                            continue
                result[key] = None
            else:
                result[key] = parse_value(val)
            i += 1
        return result, i
    
    all_lines = content.split('\n')
    result, _ = parse_mapping(all_lines, 0, 0)
    return result


def validate_no_persistent_runs(config_dir: str) -> List[str]:
    """Validate that cloud-init configs won't run after first boot.
    
    Checks for:
    - runcmd/bootcmd that could re-run
    - phone_home configurations
    - packages that reinstall
    - scripts that run on every boot
    """
    warnings = []
    config_path = Path(config_dir)
    
    # Check user-data
    user_data_path = config_path / "user-data"
    if user_data_path.exists():
        try:
            with open(user_data_path, 'r') as f:
                content = f.read()
            
            # Parse YAML
            if content.startswith("#cloud-config"):
                yaml_content = content[len("#cloud-config"):].strip()
                if yaml_content:
                    try:
                        data = _safe_load_yaml(yaml_content)
                        if data:
                            warnings.extend(_check_user_data(data))
                    except Exception as e:
                        warnings.append(f"user-data: parse error: {e}")
        except Exception as e:
            warnings.append(f"user-data: read error: {e}")
    
    # Check for cloud-init per-boot scripts
    boot_dirs = [
        "/etc/cloud/cloud.cfg.d",
        "/var/lib/cloud/scripts/per-boot",
        "/var/lib/cloud/scripts/per-once",
        "/var/lib/cloud/scripts/per-instance",
    ]
    
    for d in boot_dirs:
        p = Path(d)
        if p.exists():
            scripts = list(p.glob("*"))
            if scripts:
                warnings.append(f"Found existing cloud-init scripts in {d}: {[s.name for s in scripts]}")
    
    return warnings


def _check_user_data(data: Dict[str, Any]) -> List[str]:
    """Check user-data for problematic configurations."""
    warnings = []
    
    # Check runcmd - these run every boot unless handled
    if "runcmd" in data:
        cmds = data["runcmd"]
        if isinstance(cmds, list) and cmds:
            warnings.append("runcmd present - commands run on first boot only (per-instance). Verify they are idempotent.")
    
    # Check bootcmd - runs early every boot
    if "bootcmd" in data:
        cmds = data["bootcmd"]
        if isinstance(cmds, list) and cmds:
            warnings.append("bootcmd present - commands run on EVERY boot. Ensure they are safe to repeat.")
    
    # Check phone_home
    if "phone_home" in data:
        warnings.append("phone_home configured - will send data on every boot unless disabled.")
    
    # Check package_update/upgrade
    if data.get("package_update") or data.get("package_upgrade"):
        warnings.append("Package update/upgrade enabled - runs on first boot. Ensure target image has package cache.")
    
    # Check for scripts that might run repeatedly
    if "write_files" in data:
        for f in data["write_files"]:
            path = f.get("path", "")
            if "per-boot" in path or "per-once" in path:
                warnings.append(f"write_files targets cloud-init script directory: {path}")
    
    # Check ntp - usually fine but could conflict
    if "ntp" in data:
        warnings.append("NTP configured in cloud-init - may conflict with platform/OS NTP. Consider 'Let Platform Handle NTP'.")
    
    # Check network - could conflict with platform
    if "network" in data:
        warnings.append("Network configured in cloud-init - may conflict with platform network config. Consider 'Let Platform Handle Network'.")
    
    # Check growpart
    if "growpart" in data:
        warnings.append("growpart configured - runs on first boot. Verify target disk layout matches.")
    
    return warnings


def validate_cloudseed_json(config_dir: str) -> List[str]:
    """Validate cloudseed.json for consistency."""
    warnings = []
    json_path = Path(config_dir) / "cloudseed.json"
    
    if not json_path.exists():
        warnings.append("cloudseed.json not found - cannot re-use this configuration")
        return warnings
    
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Check version compatibility
        # Could add version checking here in future
        
        # Check for required fields
        required = ["platform", "os_type", "modules"]
        for field in required:
            if field not in data:
                warnings.append(f"cloudseed.json missing field: {field}")
        
        # Check modules match files present
        modules = data.get("modules", [])
        if "network" in modules:
            if not (Path(config_dir) / "user-data").exists() and data.get("os_type") == "linux":
                warnings.append("network module selected but no user-data found")
        
    except json.JSONDecodeError as e:
        warnings.append(f"cloudseed.json: invalid JSON: {e}")
    except Exception as e:
        warnings.append(f"cloudseed.json: read error: {e}")
    
    return warnings


def validate_windows_config(config_dir: str) -> List[str]:
    """Validate Windows-specific configurations."""
    warnings = []
    config_path = Path(config_dir)
    
    # Check for sysprep files
    sysprep_xml = config_path / "sysprep-unattend.xml"
    sysprep_bat = config_path / "run-sysprep.bat"
    
    if sysprep_xml.exists():
        try:
            with open(sysprep_xml, 'r') as f:
                content = f.read()
            
            # Check for generalize pass
            if "generalize" not in content.lower():
                warnings.append("sysprep-unattend.xml: missing generalize pass - SID won't change")
            
            # Check for specialize pass
            if "specialize" not in content.lower():
                warnings.append("sysprep-unattend.xml: missing specialize pass - computer name won't be set")
            
            # Check for oobe
            if "oobe" not in content.lower():
                warnings.append("sysprep-unattend.xml: missing oobe pass - unattended setup incomplete")
                
        except Exception as e:
            warnings.append(f"sysprep-unattend.xml: read error: {e}")
    else:
        warnings.append("sysprep-unattend.xml not found - Windows SID won't be regenerated")
    
    if not sysprep_bat.exists():
        warnings.append("run-sysprep.bat not found - no easy way to launch Sysprep")
    
    # Check Cloudbase-Init configs
    for conf_name in ["cloudbase-init.conf", "cloudbase-init-unattend.conf"]:
        conf_path = config_path / conf_name
        if conf_path.exists():
            try:
                with open(conf_path, 'r') as f:
                    content = f.read()
                if "username" not in content or "password" not in content:
                    warnings.append(f"{conf_name}: missing username/password configuration")
            except Exception as e:
                warnings.append(f"{conf_name}: read error: {e}")
        else:
            warnings.append(f"{conf_name} not found")
    
    return warnings


def validate_all(config_dir: str) -> List[str]:
    """Run all validations on a config directory."""
    all_warnings = []
    
    print_section("Config Validation", f"Validating: {config_dir}")
    print()
    
    # Determine OS type from cloudseed.json
    json_path = Path(config_dir) / "cloudseed.json"
    os_type = "linux"
    if json_path.exists():
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            os_type = data.get("os_type", "linux")
        except Exception:
            pass
    
    all_warnings.extend(validate_no_persistent_runs(config_dir))
    all_warnings.extend(validate_cloudseed_json(config_dir))
    
    if os_type == "windows":
        all_warnings.extend(validate_windows_config(config_dir))
    
    if not all_warnings:
        print_success("All validations passed!")
    else:
        print_warn(f"Found {len(all_warnings)} warning(s):")
        for w in all_warnings:
            print(f"  - {w}")
    
    print()
    return all_warnings


def validator_menu() -> int:
    """Display validator menu."""
    while True:
        check_shutdown()
        print_section("Config Validator", "Validate exported CloudSeed configurations")
        print()
        print(f"  {colorize('1', Colors.CYAN)}) Validate a config directory")
        print(f"  {colorize('0', Colors.GRAY)}) ← Back to Main Menu")
        print()
        
        choice = input(f"  {colorize('Select', Colors.BOLD)} [0]: ").strip() or "0"
        check_shutdown()
        
        if choice == "1":
            path = input("Config directory path [.]: ").strip() or "."
            if not os.path.isdir(path):
                print_error(f"Not a directory: {path}")
            else:
                validate_all(path)
            input("\nPress Enter to continue...")
        elif choice == "0":
            return 0
        else:
            print_error("Invalid selection.")


if __name__ == "__main__":
    raise SystemExit(validator_menu())