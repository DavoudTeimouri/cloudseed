"""cloudseed CLI: interactive menu + batch JSON mode."""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from typing import List

from . import __version__
from .generate import build_meta_data, build_user_data, generate_all

# Import banner from model
from .model import (
    TemplateConfig,
    collect_interactive,
    load_json,
    print_banner,
    print_section,
    setup_signal_handlers,
)


def _print_generated(written: List[str]) -> None:
    print("\nGenerated files:")
    for p in written:
        print(f"  {p}")
    print()


def _print_warnings(warnings: List[str]) -> None:
    if warnings:
        print("\n⚠️  Warnings:")
        for w in warnings:
            print(f"  - {w}")
        print()


def validate_config(cfg: TemplateConfig) -> List[str]:
    """Validate configuration and return list of warnings."""
    warnings = []

    if cfg.plaintext_password:
        warnings.append("Plaintext password — cloud-init >= 22 rejects plaintext. Use default hashing.")

    if cfg.has("users") and cfg.lock_password and not cfg.ssh_keys and cfg.os_type == "linux":
        warnings.append("Missing SSH keys with password locked — will lock you out!")

    if cfg.has("network") and cfg.net_mode == "static" and not cfg.net_gateway:
        warnings.append("Static network without gateway — may leave VM unreachable.")

    if cfg.os_type == "windows" and cfg.has("sysprep") and not cfg.sysprep:
        warnings.append("Windows without Sysprep — cloning creates duplicate SIDs.")

    if cfg.has("disk") and cfg.grow_device:
        warnings.append(f"Disk grow on {cfg.grow_device}{cfg.grow_partition} — verify device exists on target image.")

    if cfg.has("packages") and cfg.package_upgrade and not cfg.packages:
        warnings.append("Package upgrade enabled but package list empty — upgrade runs but installs nothing extra.")

    return warnings


def detect_cloud_init_version() -> str:
    """Detect cloud-init version on current system."""
    try:
        result = subprocess.run(["cloud-init", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "not found"


def get_cloud_init_compatibility(version_str: str) -> str:
    """Return compatibility info based on version."""
    if version_str == "not found":
        return "cloud-init not installed on this system"
    try:
        # Parse version like "23.4.2", "24.1", or "26.1-0ubuntu1~24.04.1"
        # Extract major version number from the beginning
        major_str = ""
        for c in version_str:
            if c.isdigit():
                major_str += c
            elif major_str:
                break
        if not major_str:
            return "⚠️ Unknown version format"
        major = int(major_str)
        if major >= 24 or major >= 23:
            return "✅ Fully supported (all modules)"
        elif major >= 22:
            return "✅ Supported (minor network v2 differences)"
        elif major >= 21:
            return "⚠️ Limited (missing ntp, growpart modules)"
        else:
            return "❌ Not supported (too old for modern config schema)"
    except (ValueError, IndexError):
        return "⚠️ Unknown version format"


def write_to_cloud_init_path(cfg: TemplateConfig) -> bool:
    """Write user-data directly to /etc/cloud/cloud.cfg.d/99-cloudseed.cfg. Requires root (Linux only)."""
    if platform.system().lower() == "windows":
        print("Error: --write-to-cloud-init-path is Linux only")
        return False
    if os.geteuid() != 0:
        print("Error: Requires root (run with sudo)")
        return False

    target_path = "/etc/cloud/cloud.cfg.d/99-cloudseed.cfg"
    try:
        os.makedirs("/etc/cloud/cloud.cfg.d", exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(build_user_data(cfg))
        print(f"Written to {target_path}")
        print("Run: sudo cloud-init clean --reboot")
        return True
    except Exception as e:
        print(f"Error writing to {target_path}: {e}")
        return False


def run_batch(json_path: str, out_dir: str, plaintext: bool = False,
              print_output: bool = False, write_cloud_init_path: bool = False) -> int:
    cfg = load_json(json_path)
    cfg.plaintext_password = plaintext

    # Default output directory in current path
    if not out_dir:
        out_dir = os.path.join(os.getcwd(), "cloudseed-out")

    warnings = validate_config(cfg)
    _print_warnings(warnings)

    if write_cloud_init_path:
        if cfg.os_type != "linux":
            print("Error: --write-to-cloud-init-path only works for Linux configs")
            return 1
        return 0 if write_to_cloud_init_path(cfg) else 1

    written = generate_all(cfg, out_dir, interactive=False)
    _print_generated(written)

    if print_output:
        print("--- user-data preview ---")
        print(build_user_data(cfg))
        print("--- meta-data preview ---")
        print(build_meta_data(cfg))
    return 0


def run_interactive(out_dir: str, plaintext: bool = False,
                    write_cloud_init_path: bool = False) -> int:
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()

    result = collect_interactive()

    # If collect_interactive returns an int (from submenu), return it
    if isinstance(result, int):
        return result

    cfg = result
    cfg.plaintext_password = plaintext

    # Default output directory in current path
    if not out_dir:
        default_out = os.path.join(os.getcwd(), "cloudseed-out")
        # Enable tab completion for directory paths
        try:
            import glob
            import readline

            def complete_path(text, state):
                # Expand user and variables
                text = os.path.expanduser(text)
                # Find matching directories
                matches = [d for d in glob.glob(text + '*') if os.path.isdir(d)]
                if state < len(matches):
                    return matches[state]
                return None

            readline.set_completer_delims(' \t\n')
            readline.set_completer(complete_path)
            readline.parse_and_bind('tab: complete')
        except ImportError:
            pass  # readline not available (Windows default Python)

        out_dir = input(f"\nOutput directory [{default_out}]: ").strip() or default_out

    warnings = validate_config(cfg)
    _print_warnings(warnings)

    if write_cloud_init_path:
        if cfg.os_type != "linux":
            print("Error: --write-to-cloud-init-path only works for Linux configs")
            return 1
        return 0 if write_to_cloud_init_path(cfg) else 1

    written = generate_all(cfg, out_dir, interactive=True)
    _print_generated(written)

    print("\n--- user-data preview ---")
    print(build_user_data(cfg))
    print("--- meta-data preview ---")
    print(build_meta_data(cfg))

    # Post-export: run validator on the generated config
    print_section("Post-Export Validation", "Running config validator on generated files...")
    # Find the platform/OS subdir that was created
    plat_name = "vsphere" if cfg.platform == "vsphere" else cfg.platform
    subdir = os.path.join(out_dir, f"{plat_name}-{cfg.os_type}")
    if os.path.isdir(subdir):
        from .validator import validate_all
        validate_all(subdir)
    else:
        # Fallback to out_dir
        from .validator import validate_all
        validate_all(out_dir)

    # Return to main menu instead of exiting
    print("\n" + "=" * 50)
    input("Press Enter to return to Main Menu...")
    return run_interactive(out_dir, plaintext, write_cloud_init_path)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cloudseed",
        description="Generate cloud-init / Cloudbase-Init VM templates "
                    "for vSphere and KVM (Linux + Windows). Config-only (no ISO).",
    )
    p.add_argument("--version", action="version", version=f"CloudSeed {__version__}")
    p.add_argument("--json", metavar="FILE",
                   help="Apply a saved config (JSON) and generate files (batch mode).")
    p.add_argument("--out", metavar="DIR", default="",
                   help="Output directory (default ./cloudseed-out in current path).")
    p.add_argument("--plaintext-password", action="store_true",
                   help="Emit the password in plaintext instead of a $6$ SHA-512 hash (discouraged).")
    p.add_argument("--print", action="store_true",
                   help="(batch) also print generated contents to stdout.")
    p.add_argument("--detect-cloud-init", action="store_true",
                   help="Detect installed cloud-init version on current system and show compatibility.")
    p.add_argument("--write-to-cloud-init-path", action="store_true",
                   help="Write generated user-data directly to /etc/cloud/cloud.cfg.d/99-cloudseed.cfg (Linux only, requires root).")
    return p


def main(argv: List[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(argv)

    # Handle --detect-cloud-init early
    if args.detect_cloud_init:
        version = detect_cloud_init_version()
        compat = get_cloud_init_compatibility(version)
        print(f"cloud-init version: {version}")
        print(f"Compatibility: {compat}")
        return 0

    if args.json:
        return run_batch(args.json, args.out, args.plaintext_password,
                         args.print, args.write_to_cloud_init_path)

    return run_interactive(args.out, args.plaintext_password, args.write_to_cloud_init_path)


if __name__ == "__main__":
    raise SystemExit(main())
