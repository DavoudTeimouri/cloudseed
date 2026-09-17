"""CloudSeed Config Validator: validate exported configurations don't run first boot."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from .model import (
    Colors,
    check_shutdown,
    colorize,
    print_error,
    print_info,
    print_section,
    print_success,
    print_warn,
)
from .password import hash_password


# Global fix-it mode flag
_FIX_IT_MODE = False


def _safe_load_yaml(content: str) -> Any:
    """Minimal YAML parser cloud-config (stdlib only)."""
    lines = []
    for line in content.split('\n'):
        # Preserve leading whitespace for indentation tracking
        stripped = line.lstrip()
        if not stripped or stripped.startswith('#'):
            continue
        # Remove inline comments
        if '#' in line:
            line = line.split('#')[0].rstrip()
        lines.append(line)

    content = '\n'.join(lines)
    if not content:
        return {}

    # Convert standard YAML list format: key: [item1, item2]
    new_lines = []
    for line in content.split('\n'):
        if ':' in line and ']' in line:
            # key value
            parts = line.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                val = parts[1].strip()
                if val.startswith('[') and val.endswith(']'):
                    items_str = val[1:-1].strip()
                    if items_str:
                        items = [item.strip().strip('"\'') for item in items_str.split(',')]
                    else:
                        items = []
                    new_lines.append(f"{key}:")
                    for item in items:
                        new_lines.append(f"  - {item}")
                    continue
        new_lines.append(line)
    content = '\n'.join(new_lines)

    # Parse cloud-config 2-space indent
    def parse_value(v: str) -> Any:
        v = v.strip()
        if not v:
            return None
        if v.lower() in ('true', 'false'):
            return v.lower() == 'true'
        if v.isdigit():
            return int(v)
        try:
            return float(v)
        except ValueError:
            pass
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            return v[1:-1]
        return v

    def parse_mapping(lines: List[str], i: int, indent: int) -> tuple[Dict[str, Any], int]:
        result = {}
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            current_indent = len(line) - len(line.lstrip())
            if current_indent < indent:
                break
            key_part, sep, val_part = line.partition(':')
            if not sep:
                i += 1
                continue
            key = key_part.rstrip()
            val = val_part.lstrip()
            i += 1
            if val == '':
                # Mapping or list
                if i < len(lines):
                    next_line = lines[i]
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent > indent:
                        if lines[i].lstrip().startswith('- '):
                            # List
                            items = []
                            while i < len(lines):
                                lj = lines[i]
                                lj_indent = len(lj) - len(lj.lstrip())
                                if lj_indent < indent + 2:
                                    break
                                if lj_indent >= indent + 2 and lj.lstrip().startswith('- '):
                                    item_content = lj.strip()[2:].strip()
                                    # Check if this list item is a mapping (has nested key-value pairs)
                                    if ':' in item_content and not item_content.strip().startswith('- '):
                                        # This looks like "key: value" - parse as dict
                                        item_parts = item_content.split(':', 1)
                                        if len(item_parts) == 2:
                                            item_key = item_parts[0].strip()
                                            item_val = item_parts[1].strip()
                                            # Parse the first key-value pair
                                            item_dict = {item_key: parse_value(item_val)}
                                            # Look ahead for more key-value pairs at deeper indent
                                            j = i + 1
                                            while j < len(lines):
                                                next_line = lines[j]
                                                next_indent = len(next_line) - len(next_line.lstrip())
                                                if next_indent <= indent + 2:
                                                    break
                                                if next_indent >= indent + 4 and ':' in next_line:
                                                    nested_parts = next_line.split(':', 1)
                                                    if len(nested_parts) == 2:
                                                        nested_key = nested_parts[0].strip()
                                                        nested_val = nested_parts[1].strip()
                                                        item_dict[nested_key] = parse_value(nested_val)
                                                        j += 1
                                                    else:
                                                        break
                                                else:
                                                    break
                                            items.append(item_dict)
                                            i = j
                                            continue
                                    # Fallback: treat as simple value
                                    items.append(parse_value(item_content))
                                    i += 1
                                else:
                                    break
                            result[key] = items
                        else:
                            # Nested mapping
                            nested, new_i = parse_mapping(lines, i, indent + 2)
                            result[key] = nested
                            i = new_i
                    else:
                        result[key] = None
                else:
                    result[key] = None
            else:
                result[key] = parse_value(val)
        return result, i

    all_lines = content.split('\n')
    result, _ = parse_mapping(all_lines, 0, 0)
    return result


def _simple_yaml_dump(data: Any, indent: int = 0) -> str:
    """Very simple YAML dumper for basic types (used for fixing user-data)."""
    if data is None:
        return 'null'
    if isinstance(data, bool):
        return 'true' if data else 'false'
    if isinstance(data, int):
        return str(data)
    if isinstance(data, str):
        # Escape backslashes and quotes, then wrap in quotes
        escaped = data.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(data, list):
        if not data:
            return '[]'
        lines = []
        for item in data:
            item_yaml = _simple_yaml_dump(item, indent + 2)
            lines.append(f"{' ' * indent}- {item_yaml}")
        return '\n'.join(lines)
    if isinstance(data, dict):
        if not data:
            return '{}'
        lines = []
        for key, value in data.items():
            key_yaml = _simple_yaml_dump(key)
            value_yaml = _simple_yaml_dump(value, indent + 2)
            if isinstance(value, (dict, list)):
                lines.append(f"{' ' * indent}{key_yaml}:")
                lines.append(value_yaml)
            else:
                lines.append(f"{' ' * indent}{key_yaml}: {value_yaml}")
        return '\n'.join(lines)
    return str(data)


def validate_no_persistent_runs(config_dir: str, fix_it: bool = False) -> List[str]:
    """Validate that cloud-init configs won't run after first boot.

    Checks for:
    - runcmd/bootcmd that could re-run
    - phone_home configurations
    - packages that reinstall
    - scripts that run on every boot
    """
    warnings = []
    config_path = Path(config_dir)

    # Check user-data in the generated config directory
    user_data_path = config_path / "user-data"
    if user_data_path.exists():
        try:
            with open(user_data_path) as f:
                content = f.read()
        except Exception as e:
            warnings.append(f"Failed to read user-data: {e}")
            return warnings

        # Check if it's a cloud-config
        if content.startswith("#cloud-config"):
            yaml_content = content[len("#cloud-config"):].lstrip()
            try:
                data = _safe_load_yaml(yaml_content)
            except Exception as e:
                warnings.append(f"Failed to parse user-data YAML: {e}")
                data = {}

            # Fix plaintext password in fix-it mode
            if fix_it and data:
                changed = False
                # Hash password in users[0].passwd
                if "users" in data and isinstance(data["users"], list) and data["users"]:
                    user = data["users"][0]
                    if isinstance(user, dict) and "passwd" in user and user["passwd"]:
                        passwd = user["passwd"]
                        # Assume it's plaintext if it's not already hashed (simple check: not starting with $6$)
                        if not passwd.startswith("$6$"):
                            try:
                                hashed = hash_password(passwd)
                                user["passwd"] = hashed
                                changed = True
                            except Exception:
                                pass  # Keep warning if hashing fails
                # Hash password in chpasswd
                if "chpasswd" in data and isinstance(data["chpasswd"], list):
                    for item in data["chpasswd"]:
                        if isinstance(item, dict) and "password" in item and item["password"]:
                            password = item["password"]
                            if not password.startswith("$6$"):
                                try:
                                    hashed = hash_password(password)
                                    item["password"] = hashed
                                    changed = True
                                except Exception:
                                    pass
                if changed:
                    # Generate new YAML content
                    try:
                        new_yaml = _simple_yaml_dump(data)
                        new_content = "#cloud-config\n" + new_yaml
                        with open(user_data_path, 'w') as f:
                            f.write(new_content)
                    except Exception as e:
                        warnings.append(f"Failed to write fixed user-data: {e}")

            # Check for persistent runs
            if "runcmd" in data:
                cmds = data["runcmd"]
                if isinstance(cmds, list) and cmds:
                    warnings.append("runcmd present - commands run on first boot only (per-instance). Verify idempotent.")

            if "bootcmd" in data:
                cmds = data["bootcmd"]
                if isinstance(cmds, list) and cmds:
                    warnings.append("bootcmd present - commands run on EVERY boot. Ensure safe repeat.")

            if "phone_home" in data:
                warnings.append("phone_home configured - will send data on every boot unless disabled.")

            if data.get("package_update") or data.get("package_upgrade"):
                warnings.append("Package update/upgrade enabled - runs on first boot. Ensure target image package cache.")

            if "write_files" in data:
                for f in data["write_files"]:
                    path = f.get("path", "")
                    if "per-boot" in path or "per-once" in path:
                        warnings.append(f"write_files targets cloud-init script directory: {path}")

            if "ntp" in data:
                warnings.append("NTP configured in cloud-init - may conflict with platform/OS NTP. Consider 'Let Platform Handle NTP'.")

            if "network" in data:
                warnings.append("Network configured in cloud-init - may conflict platform network config. Consider 'Let Platform Handle Network'.")

            if "growpart" in data:
                warnings.append("growpart configured - runs on first boot. Verify target disk layout matches.")

        else:
            # Not a cloud-config, treat as raw user-data (legacy)
            warnings.append("user-data is not a cloud-config; validation skipped.")

    else:
        warnings.append("user-data not found - skipping user-data validation.")

    return warnings


def validate_cloudseed_json(config_dir: str, fix_it: bool = False) -> List[str]:
    """Validate cloudseed.json for consistency."""
    warnings = []
    json_path = Path(config_dir) / "cloudseed.json"

    if not json_path.exists():
        # cloudseed.json may be in parent directory (output root)
        # This is not an error for fresh generations
        return warnings

    try:
        with open(json_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        warnings.append(f"cloudseed.json: invalid JSON: {e}")
        return warnings
    except Exception as e:
        warnings.append(f"cloudseed.json: read error: {e}")
        return warnings

    # Fix-it mode: add missing fields with default values
    if fix_it:
        changed = False
        if "version" not in data:
            data["version"] = "1.0"
            changed = True
        if "modules" not in data:
            data["modules"] = []
            changed = True
        if changed:
            try:
                with open(json_path, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                warnings.append(f"cloudseed.json: failed to write fixed file: {e}")

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

    return warnings


def validate_windows_config(config_dir: str, fix_it: bool = False) -> List[str]:
    """Validate Windows-specific configurations."""
    warnings = []
    config_path = Path(config_dir)

    # Check sysprep files
    sysprep_xml = config_path / "sysprep-unattend.xml"
    sysprep_bat = config_path / "run-sysprep.bat"

    if sysprep_xml.exists():
        try:
            with open(sysprep_xml) as f:
                content = f.read()
        except Exception as e:
            warnings.append(f"sysprep-unattend.xml: read error: {e}")
            content = ""

        # Check generalize pass
        if "generalize" not in content.lower():
            warnings.append("sysprep-unattend.xml: missing generalize pass - SID won't change")
            if fix_it:
                # Cannot auto-fix generalize pass without understanding XML structure
                pass

        # Check specialize pass
        if "specialize" not in content.lower():
            warnings.append("sysprep-unattend.xml: missing specialize pass - computer name won't be set")
            if fix_it:
                pass

        # Check oobe
        if "oobe" not in content.lower():
            warnings.append("sysprep-unattend.xml: missing oobe pass - unattended setup incomplete")
            if fix_it:
                pass
    else:
        warnings.append("sysprep-unattend.xml not found - Windows SID won't be regenerated")
        if fix_it:
            # Cannot auto-create sysprep-unattend.xml without template
            pass

    if not sysprep_bat.exists():
        warnings.append("run-sysprep.bat not found - no easy way to launch Sysprep")
        if fix_it:
            # Cannot auto-create run-sysprep.bat without template
            pass

    # Check Cloudbase-Init configs
    for conf_name in ["cloudbase-init.conf", "cloudbase-init-unattend.conf"]:
        conf_path = config_path / conf_name
        if conf_path.exists():
            try:
                with open(conf_path) as f:
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
            with open(json_path) as f:
                data = json.load(f)
            os_type = data.get("os_type", "linux")
        except Exception:
            pass

    all_warnings.extend(validate_no_persistent_runs(config_dir, fix_it=_FIX_IT_MODE))
    all_warnings.extend(validate_cloudseed_json(config_dir, fix_it=_FIX_IT_MODE))
    if os_type == "windows":
        all_warnings.extend(validate_windows_config(config_dir, fix_it=_FIX_IT_MODE))

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
        print(f"  {colorize('2', Colors.CYAN)}) Scan for cloudseed.json in subdirectories (2 levels deep)")
        print(f"  {colorize('0', Colors.GRAY)}) \u2190 Back to Main Menu")
        print()

        choice = input(f"  {colorize('Select', Colors.BOLD)} [0]: ").strip() or "0"
        check_shutdown()

        if choice == "1":
            path = input("Config directory path [.]: ").strip() or "."
            # Handle quoted paths
            path = path.strip('"\'')
            if not os.path.isdir(path):
                print_error(f"Not a directory: {path}")
            else:
                validate_all(path)
            input("\nPress Enter to continue...")
        elif choice == "2":
            base = input("Base directory to scan [.]: ").strip() or "."
            base = base.strip('"\'')
            if not os.path.isdir(base):
                print_error(f"Not a directory: {base}")
            else:
                scan_subdirs_for_configs(base)
            input("\nPress Enter to continue...")
        elif choice == "0":
            return 0
        else:
            print_error("Invalid selection.")


def scan_subdirs_for_configs(base_dir: str, max_depth: int = 2) -> None:
    """Recursively scan for cloudseed.json in subdirectories up to max_depth."""
    from pathlib import Path

    print_info(f"Scanning {base_dir} (max depth: {max_depth})...")
    print()

    configs = []
    base_path = Path(base_dir)

    def scan(path: Path, depth: int):
        if depth > max_depth:
            return
        # Check for cloudseed.json in this directory
        json_file = path / "cloudseed.json"
        if json_file.exists():
            configs.append(str(json_file))
        # Recurse into subdirectories
        if depth < max_depth:
            try:
                for subdir in path.iterdir():
                    if subdir.is_dir() and not subdir.name.startswith('.'):
                        scan(subdir, depth + 1)
            except PermissionError:
                pass

    scan(base_path, 0)

    if not configs:
        print_warn("No cloudseed.json files found in subdirectories.")
        return

    print_success(f"Found {len(configs)} cloudseed.json file(s):")
    for i, cfg in enumerate(configs, 1):
        print(f"  {colorize(str(i), Colors.CYAN)}) {cfg}")
    print()

    print(f"  {colorize('1', Colors.CYAN)}) Validate all found configs")
    print(f"  {colorize('2', Colors.CYAN)}) Validate specific config")
    print(f"  {colorize('3', Colors.CYAN)}) Delete all found configs (cleanup)")
    print(f"  {colorize('0', Colors.GRAY)}) \u2190 Back")
    print()

    action = input(f"  {colorize('Action', Colors.BOLD)} [0]: ").strip() or "0"

    if action == "1":
        for cfg in configs:
            print_section("Validation", f"Validating: {cfg}")
            validate_all(str(Path(cfg).parent))
    elif action == "2":
        sel = input(f"  {colorize('Select number', Colors.BOLD)}: ").strip()
        if sel.isdigit():
            idx = int(sel)
            if 1 <= idx <= len(configs):
                validate_all(str(Path(configs[idx-1]).parent))
    elif action == "3":
        confirm = input("\u26a0\ufe0f  Type 'DELETE' to confirm removing all found configs: ").strip()
        if confirm == "DELETE":
            for cfg in configs:
                try:
                    os.remove(cfg)
                    print_success(f"Deleted: {cfg}")
                except Exception as e:
                    print_error(f"Failed to delete {cfg}: {e}")
        else:
            print_info("Cancelled.")
    elif action == "0":
        return
    else:
        print_error("Invalid selection.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--fix-it', action='store_true', help='Enable fix-it mode to auto-correct common issues')
    args = parser.parse_args()
    _FIX_IT_MODE = args.fix_it
    raise SystemExit(validator_menu())