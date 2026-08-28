"""CloudSeed data model: config dataclass, module catalog, interactive collector.

No third-party dependencies (Python 3 standard library only).
"""

from __future__ import annotations

import json
import signal
import sys
from dataclasses import dataclass, field, asdict
from typing import List, Optional


# Global flag for graceful shutdown
_shutdown_requested = False


def _signal_handler(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    print("\n\n[CloudSeed] Interrupted. Shutting down gracefully...")
    sys.exit(130)


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)


def check_shutdown():
    """Check if shutdown was requested."""
    global _shutdown_requested
    if _shutdown_requested:
        print("\n[CloudSeed] Shutdown requested. Exiting...")
        sys.exit(130)


def print_banner(title: str = "") -> None:
    """Print CloudSeed banner with version and description."""
    from . import __version__
    width = 64
    line = "═" * width
    print(f"\n{line}")
    print(f"  CloudSeed v{__version__}")
    print(f"  ║  cloud-init / Cloudbase-Init VM Template Generator  ║")
    print(f"  ║  Config-only (no ISO) · vSphere · KVM · Physical    ║")
    print(f"  ║  Zero dependencies — Python stdlib only             ║")
    if title:
        print(f"  ║  {title:<54} ║")
    print(f"{line}\n")


def print_sub_banner(title: str, description: str = "") -> None:
    """Print a sub-menu banner with title and optional description."""
    width = 60
    line = "─" * width
    print(f"\n  {title}")
    if description:
        print(f"  {description}")
    print(f"  {line}\n")


@dataclass
class TemplateConfig:
    # selection
    platform: str = "vsphere"          # "vsphere" | "kvm" | "physical"
    os_type: str = "linux"             # "linux" | "windows"
    modules: List[str] = field(default_factory=list)

    # --- identity ---
    hostname: str = ""  # Empty = auto-generate from platform/prefix
    hostname_prefix: str = "vm"        # Prefix for auto-generated hostname
    use_platform_hostname: bool = True  # Let platform (vSphere/KVM) set hostname

    # --- users ---
    username: str = "admin"
    password: str = "ChangeMe!123"
    plaintext_password: bool = False    # emit plaintext instead of hashed (discouraged)
    password_rounds: int = 5000
    sudo: bool = True
    lock_password: bool = False
    ssh_pwauth: bool = False
    disable_root: bool = True

    # --- ssh ---
    ssh_keys: List[str] = field(default_factory=list)

    # --- network ---
    net_mode: str = "dhcp"             # "dhcp" | "static"
    net_interface: str = "eth0"
    net_address: str = ""
    net_netmask: str = "255.255.255.0"
    net_gateway: str = ""
    net_dns: List[str] = field(default_factory=lambda: ["8.8.8.8", "1.1.1.1"])
    net_search: List[str] = field(default_factory=list)
    # Platform-specific: let platform handle network (avoid conflicts)
    let_platform_handle_network: bool = False

    # --- packages ---
    package_upgrade: bool = True
    package_reboot_if_required: bool = False
    packages: List[str] = field(default_factory=list)

    # --- locale / timezone ---
    timezone: str = "UTC"
    locale: str = "en_US.UTF-8"
    keyboard_layout: str = "us"

    # --- disk ---
    grow_device: str = "/dev/sda"
    grow_partition: str = "1"

    # --- ntp ---
    ntp_servers: List[str] = field(default_factory=lambda: ["pool.ntp.org"])
    ntp_pools: List[str] = field(default_factory=list)
    # Platform-specific: let platform handle NTP
    let_platform_handle_ntp: bool = False

    # --- files / commands ---
    write_files: List[dict] = field(default_factory=list)   # {"path","content","permissions"}
    bootcmd: List[str] = field(default_factory=list)
    firstboot: List[str] = field(default_factory=list)     # runcmd
    final_message: str = "CloudSeed: system ready."

    # --- windows sysprep ---
    sysprep: bool = True
    sysprep_organization: str = "MyOrg"
    sysprep_owner: str = "Administrator"
    sysprep_computer_prefix: str = "WIN"
    sysprep_timezone: str = "W. Europe Standard Time"
    sysprep_locale: str = "en-US"
    sysprep_product_key: str = ""
    sysprep_unattended: bool = True   # Fully unattended like vSphere Guest Customization

    # --- vSphere Customization Spec export ---
    export_vsphere_spec: bool = False
    vsphere_spec_name: str = "CloudSeed-Spec"

    # --- vSphere Pre/Post Customization Scripts ---
    vsphere_pre_script: str = ""
    vsphere_post_script: str = ""
    use_sample_scripts: bool = False

    def has(self, mod: str) -> bool:
        return mod in self.modules

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TemplateConfig":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


# --- interactive prompt helpers -------------------------------------------

def _ask(prompt: str, default: str = "") -> str:
    check_shutdown()
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    val = input(prompt).strip()
    check_shutdown()
    return val or default


def _ask_bool(prompt: str, default: bool = False) -> bool:
    check_shutdown()
    d = "Y/n" if default else "y/N"
    val = input(f"{prompt} ({d}): ").strip().lower()
    check_shutdown()
    if not val:
        return default
    return val in ("y", "yes", "true", "1")


def _ask_list(prompt: str) -> List[str]:
    check_shutdown()
    print(f"{prompt} (one per line, blank line to finish):")
    items: List[str] = []
    while True:
        check_shutdown()
        line = input(f"  {len(items) + 1}> ").strip()
        if not line:
            break
        items.append(line)
    return items


def _ask_overwrite(filepath: str) -> str:
    """Ask user what to do when file exists. Returns 'overwrite', 'suffix', or 'skip'."""
    from pathlib import Path
    check_shutdown()
    while True:
        print(f"\n[CloudSeed] File already exists: {filepath}")
        print("  1) Overwrite")
        print("  2) Add suffix (e.g., _1, _2)")
        print("  3) Skip this file")
        choice = input("Select [1]: ").strip() or "1"
        check_shutdown()
        if choice == "1":
            return "overwrite"
        elif choice == "2":
            return "suffix"
        elif choice == "3":
            return "skip"
        print("Invalid selection, try again.")


def _get_unique_path(out_dir: str, filename: str) -> str | None:
    """Get a unique path, asking user if file exists. Returns None if skip."""
    from pathlib import Path
    filepath = Path(out_dir) / filename
    if not filepath.exists():
        return str(filepath)
    
    action = _ask_overwrite(str(filepath))
    if action == "overwrite":
        return str(filepath)
    elif action == "suffix":
        base = filepath.stem
        ext = filepath.suffix
        counter = 1
        while True:
            new_name = f"{base}_{counter}{ext}"
            new_path = filepath.parent / new_name
            if not new_path.exists():
                return str(new_path)
            counter += 1
    elif action == "skip":
        return None


def _choose(prompt: str, options: List[str], allow_back: bool = False) -> str:
    """Choose from options. Returns selected option or 'BACK' if back selected."""
    check_shutdown()
    print_sub_banner(prompt)
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}")
    if allow_back:
        print(f"  0) ← Back")
    while True:
        check_shutdown()
        if allow_back:
            raw = input("Select [1]: ").strip()
        else:
            raw = input("Select [1]: ").strip()
        if not raw:
            return options[0]
        if allow_back and raw == "0":
            return "BACK"
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("Invalid selection, try again.")


def _choose_module(prompt: str, options: List[str], defaults: List[str]) -> List[str]:
    """Multi-select for modules with back option."""
    check_shutdown()
    print_sub_banner(prompt, "Space-separated numbers, 'a' for all, Enter for defaults, 0 to go back")
    for i, opt in enumerate(options, 1):
        default_marker = " ✓" if opt in defaults else ""
        print(f"  {i}) {opt}{default_marker}")
    print("  0) ← Back")
    while True:
        check_shutdown()
        sel = input("\nSelection: ").strip().lower()
        if not sel:
            return defaults
        if sel == "0":
            return "BACK"
        if sel == "a":
            return options
        try:
            idxs = [int(x) for x in sel.split() if x.isdigit()]
            chosen = {options[i - 1] for i in idxs if 1 <= i <= len(options)}
            return [m for m in defaults if m in chosen] + [m for m in chosen if m not in defaults]
        except (ValueError, IndexError):
            print("Invalid selection, try again.")


def collect_interactive() -> TemplateConfig:
    from .modules import MODULES

    setup_signal_handlers()
    
    # Detect cloud-init availability
    from .cli import detect_cloud_init_version
    cloud_init_version = detect_cloud_init_version()
    cloud_init_available = cloud_init_version != "not found"
    
    cfg = TemplateConfig()
    
    while True:  # Main loop - allows returning to main menu
        print_banner("Main Menu")
        
        # Main action menu
        main_actions = [
            "Generate Configuration",
            "Toolbox (External Tools)",
            "Config Validator",
            "Cloud-Init Doctor",
            "Template Maker (Prepare Current Machine as Template)",
            "Exit",
        ]
        action = _choose("Select action:", main_actions)
        
        if action == "Toolbox (External Tools)":
            from .toolbox import toolbox_menu
            toolbox_menu()
            continue  # Return to main menu
        elif action == "Config Validator":
            from .validator import validator_menu
            validator_menu()
            continue
        elif action == "Cloud-Init Doctor":
            from .doctor import doctor_menu
            doctor_menu()
            continue
        elif action == "Template Maker (Prepare Current Machine as Template)":
            from .templatemaker import template_maker_menu
            template_maker_menu()
            continue
        elif action == "Exit":
            print("Goodbye!")
            sys.exit(0)
        
        # Generate Configuration flow with back navigation
        while True:
            platform_choice = _choose("Target platform:", ["vSphere (VMware)", "KVM (libvirt)", "Physical / Other"], allow_back=True)
            if platform_choice == "BACK":
                break  # Back to main menu
            cfg.platform = platform_choice.split()[0].lower()
            if cfg.platform == "physical / other":
                cfg.platform = "physical"
            
            os_choice = _choose("Guest OS:", ["Linux", "Windows"], allow_back=True)
            if os_choice == "BACK":
                continue  # Back to platform selection
            cfg.os_type = os_choice.split()[0].lower()
            
            # Module selection with back
            available = [(mid, lbl) for (mid, lbl, oses) in MODULES if cfg.os_type in oses]
            
            # Warn if cloud-init not available but Linux selected
            if cfg.os_type == "linux" and not cloud_init_available:
                print(f"\n⚠️  WARNING: cloud-init not found on this system!")
                print("  Generated configs require cloud-init on the TARGET VM, not this build machine.")
                print("  This is OK if you're building configs for another VM.")
                print("  Some features (Config Validator, Cloud-Init Doctor) need cloud-init locally.")
                print()
            
            module_options = [lbl for (mid, lbl) in available]
            module_ids = [mid for (mid, lbl) in available]
            defaults = module_ids  # all recommended by default
            
            while True:
                selected_modules = _choose_module("Module Selection", module_options, defaults)
                if selected_modules == "BACK":
                    break  # Back to OS selection
                cfg.modules = selected_modules
                
                # Now configure each module
                if _configure_modules(cfg, available):
                    return cfg  # Success - exit the function
                else:
                    # User chose to go back from module configuration
                    continue
        
        # If we get here, user went back to main menu
        continue


def _configure_modules(cfg: TemplateConfig, available: List[tuple]) -> bool:
    """Configure all selected modules. Returns True if complete, False if user wants to go back."""
    
    # Hostname settings
    if cfg.has("hostname") or cfg.has("platform_hostname"):
        if not _configure_hostname(cfg):
            return False
    
    if cfg.has("users"):
        if not _configure_users(cfg):
            return False
    
    if cfg.has("ssh"):
        if not _configure_ssh(cfg):
            return False
    
    if cfg.has("root"):
        if not _configure_root(cfg):
            return False
    
    if cfg.has("network") or cfg.has("platform_network"):
        if not _configure_network(cfg):
            return False
    
    if cfg.has("packages"):
        if not _configure_packages(cfg):
            return False
    
    if cfg.has("locale"):
        if not _configure_locale(cfg):
            return False
    
    if cfg.has("disk"):
        if not _configure_disk(cfg):
            return False
    
    if cfg.has("ntp") or cfg.has("platform_ntp"):
        if not _configure_ntp(cfg):
            return False
    
    if cfg.has("files"):
        if not _configure_files(cfg):
            return False
    
    if cfg.has("bootcmd"):
        if not _configure_bootcmd(cfg):
            return False
    
    if cfg.has("firstboot"):
        if not _configure_firstboot(cfg):
            return False
    
    if cfg.has("final"):
        if not _configure_final(cfg):
            return False
    
    if cfg.has("sysprep"):
        if not _configure_sysprep(cfg):
            return False
    
    # vSphere Customization Spec
    if cfg.has("vsphere_spec") and cfg.platform == "vsphere":
        if not _configure_vsphere_spec(cfg):
            return False
    
    # vSphere Pre/Post Customization Scripts
    if cfg.has("vsphere_scripts") and cfg.platform == "vsphere":
        if not _configure_vsphere_scripts(cfg):
            return False
    
    return True


def _configure_hostname(cfg: TemplateConfig) -> bool:
    print_sub_banner("Hostname Configuration", "Configure how the VM hostname is set")
    cfg.use_platform_hostname = _ask_bool("Let platform (vSphere/KVM) set hostname", cfg.use_platform_hostname)
    if not cfg.use_platform_hostname:
        cfg.hostname_prefix = _ask("Hostname prefix", cfg.hostname_prefix)
        cfg.hostname = _ask("Hostname (blank = auto-generate from prefix)", cfg.hostname)
    return True


def _configure_users(cfg: TemplateConfig) -> bool:
    print_sub_banner("User Configuration", "Create admin user with password and sudo/Administrators access")
    cfg.username = _ask("Username", cfg.username)
    cfg.password = _ask("Password (plaintext; document risk!)", cfg.password)
    cfg.sudo = _ask_bool("Grant sudo (Linux) / Administrators (Windows)", cfg.sudo)
    cfg.lock_password = _ask_bool("Lock password (key-only login)", cfg.lock_password)
    cfg.ssh_pwauth = _ask_bool("Allow SSH password auth", cfg.ssh_pwauth)
    return True


def _configure_ssh(cfg: TemplateConfig) -> bool:
    print_sub_banner("SSH Configuration", "Add SSH authorized keys (one per line)")
    cfg.ssh_keys = _ask_list("SSH public keys (ssh-rsa / ssh-ed25519 ...)")
    return True


def _configure_root(cfg: TemplateConfig) -> bool:
    print_sub_banner("Root Hardening", "Disable root SSH login")
    cfg.disable_root = _ask_bool("Disable root SSH login", cfg.disable_root)
    return True


def _configure_network(cfg: TemplateConfig) -> bool:
    print_sub_banner("Network Configuration", "Configure network - DHCP or static IP with DNS")
    cfg.let_platform_handle_network = _ask_bool("Let platform handle network (avoid conflicts with cloud-init)", cfg.let_platform_handle_network)
    if not cfg.let_platform_handle_network:
        cfg.net_mode = _choose("Network mode:", ["dhcp", "static"], allow_back=False).split()[0]
        if cfg.net_mode == "static":
            cfg.net_interface = _ask("Interface name", cfg.net_interface)
            cfg.net_address = _ask("IP address", cfg.net_address)
            cfg.net_netmask = _ask("Netmask", cfg.net_netmask)
            cfg.net_gateway = _ask("Gateway", cfg.net_gateway)
            cfg.net_dns = _ask_list("DNS servers")
            cfg.net_search = _ask_list("DNS search domains (blank=none)")
    return True


def _configure_packages(cfg: TemplateConfig) -> bool:
    print_sub_banner("Package Configuration", "Install packages and optionally upgrade on first boot")
    cfg.package_upgrade = _ask_bool("Upgrade packages on first boot", cfg.package_upgrade)
    cfg.packages = _ask_list("Packages to install (blank=none)")
    return True


def _configure_locale(cfg: TemplateConfig) -> bool:
    print_sub_banner("Locale & Timezone", "Set timezone, locale, and keyboard layout")
    cfg.timezone = _ask("Timezone", cfg.timezone)
    cfg.locale = _ask("Locale", cfg.locale)
    cfg.keyboard_layout = _ask("Keyboard layout", cfg.keyboard_layout)
    return True


def _configure_disk(cfg: TemplateConfig) -> bool:
    print_sub_banner("Disk Configuration", "Grow root filesystem on first boot")
    cfg.grow_device = _ask("Grow device", cfg.grow_device)
    cfg.grow_partition = _ask("Partition number", cfg.grow_partition)
    return True


def _configure_ntp(cfg: TemplateConfig) -> bool:
    print_sub_banner("NTP Configuration", "Configure NTP time synchronization")
    cfg.let_platform_handle_ntp = _ask_bool("Let platform handle NTP", cfg.let_platform_handle_ntp)
    if not cfg.let_platform_handle_ntp:
        cfg.ntp_servers = _ask_list("NTP servers")
        if not cfg.ntp_servers:
            cfg.ntp_servers = ["pool.ntp.org"]
    return True


def _configure_files(cfg: TemplateConfig) -> bool:
    print_sub_banner("Write Files", "Write arbitrary files to the target system (blank path to finish)")
    while True:
        check_shutdown()
        p = input("  file path (blank to stop): ").strip()
        if not p:
            break
        c = input("  file content: ").strip()
        perm = input("  permissions [0644]: ").strip() or "0644"
        cfg.write_files.append({"path": p, "content": c, "permissions": perm})
    return True


def _configure_bootcmd(cfg: TemplateConfig) -> bool:
    print_sub_banner("Early Boot Commands", "Commands that run early in boot (bootcmd)")
    cfg.bootcmd = _ask_list("bootcmd (early boot commands)")
    return True


def _configure_firstboot(cfg: TemplateConfig) -> bool:
    print_sub_banner("First-Boot Commands", "Commands that run on first boot (runcmd)")
    cfg.firstboot = _ask_list("First-boot commands (runcmd)")
    return True


def _configure_final(cfg: TemplateConfig) -> bool:
    print_sub_banner("Final Message", "Message displayed when cloud-init completes")
    cfg.final_message = _ask("Final message", cfg.final_message)
    return True


def _configure_sysprep(cfg: TemplateConfig) -> bool:
    print_sub_banner("Windows Sysprep", "Generalize Windows for cloning (creates new SID)")
    cfg.sysprep = _ask_bool("Run Sysprep generalize (new SID)", cfg.sysprep)
    if cfg.sysprep:
        cfg.sysprep_unattended = _ask_bool("Fully unattended (like vSphere Guest Customization)", cfg.sysprep_unattended)
        cfg.sysprep_organization = _ask("Organization", cfg.sysprep_organization)
        cfg.sysprep_owner = _ask("Owner", cfg.sysprep_owner)
        cfg.sysprep_computer_prefix = _ask("Computer-name prefix", cfg.sysprep_computer_prefix)
        cfg.sysprep_timezone = _ask("Timezone", cfg.sysprep_timezone)
        cfg.sysprep_locale = _ask("Locale (UI)", cfg.sysprep_locale)
        cfg.sysprep_product_key = input("Product key (blank=skip): ").strip()
        check_shutdown()
    return True


def _configure_vsphere_spec(cfg: TemplateConfig) -> bool:
    print_sub_banner("vSphere Customization Spec Export", "Export vSphere Guest Customization Specification (XML)")
    cfg.export_vsphere_spec = _ask_bool("Export vSphere Customization Spec (XML)", cfg.export_vsphere_spec)
    if cfg.export_vsphere_spec:
        cfg.vsphere_spec_name = _ask("Spec name", cfg.vsphere_spec_name)
    return True


def _configure_vsphere_scripts(cfg: TemplateConfig) -> bool:
    print_sub_banner("vSphere Pre/Post Customization Scripts", "Scripts that run before/after cloud-init during vSphere Guest Customization")
    cfg.use_sample_scripts = _ask_bool("Use sample scripts (customizable)", cfg.use_sample_scripts)
    if cfg.use_sample_scripts:
        print("\nSample Pre-customization script (runs before cloud-init):")
        print("# Example: Register with Satellite, install agents, etc.")
        cfg.vsphere_pre_script = _ask("Pre-customization script (blank to skip)", "")
        print("\nSample Post-customization script (runs after cloud-init):")
        print("# Example: Join domain, run compliance checks, etc.")
        cfg.vsphere_post_script = _ask("Post-customization script (blank to skip)", "")
    return True


def load_json(path: str) -> TemplateConfig:
    with open(path, "r", encoding="utf-8") as fh:
        return TemplateConfig.from_dict(json.load(fh))
