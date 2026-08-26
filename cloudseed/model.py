"""CloudSeed data model: config dataclass, module catalog, interactive collector.

No third-party dependencies (Python 3 standard library only).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class TemplateConfig:
    # selection
    platform: str = "vsphere"          # "vsphere" | "kvm"
    os_type: str = "linux"             # "linux" | "windows"
    modules: List[str] = field(default_factory=list)

    # --- identity ---
    hostname: str = "vm-template"

    # --- users ---
    username: str = "admin"
    password: str = "ChangeMe!123"
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
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    val = input(prompt).strip()
    return val or default


def _ask_bool(prompt: str, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    val = input(f"{prompt} ({d}): ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes", "true", "1")


def _ask_list(prompt: str) -> List[str]:
    print(f"{prompt} (one per line, blank line to finish):")
    items: List[str] = []
    while True:
        line = input(f"  {len(items) + 1}> ").strip()
        if not line:
            break
        items.append(line)
    return items


def _choose(prompt: str, options: List[str]) -> str:
    print(prompt)
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}")
    while True:
        raw = input("Select [1]: ").strip()
        if not raw:
            return options[0]
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("Invalid selection, try again.")


def collect_interactive() -> TemplateConfig:
    from .modules import MODULES

    cfg = TemplateConfig()
    print("\n(Defaults shown in [brackets]. Press Enter to accept.)")

    cfg.platform = _choose(
        "Target platform:", ["vsphere (VMware)", "kvm (libvirt)"]
    ).split()[0]
    cfg.os_type = _choose("Guest OS:", ["linux", "windows"]).split()[0]

    available = [(mid, lbl) for (mid, lbl, oses) in MODULES if cfg.os_type in oses]
    print("\nAvailable customization modules (defaults preselected):")
    defaults = [m[0] for m in available]  # all recommended by default
    for i, (mid, lbl) in enumerate(available, 1):
        print(f"  {i}) {lbl}")
    sel = input(
        "Modules to include (space-separated numbers, 'a' all, Enter=all): "
    ).strip().lower()
    if sel in ("", "a"):
        cfg.modules = list(defaults)
    else:
        idxs = [int(x) for x in sel.split() if x.isdigit()]
        chosen = {available[i - 1][0] for i in idxs if 1 <= i <= len(available)}
        cfg.modules = [m for m in defaults if m in chosen] + [m for m in chosen if m not in defaults]

    if cfg.has("hostname"):
        cfg.hostname = _ask("Hostname", cfg.hostname)

    if cfg.has("users"):
        cfg.username = _ask("Username", cfg.username)
        cfg.password = _ask("Password (plaintext; document risk!)", cfg.password)
        cfg.sudo = _ask_bool("Grant sudo (Linux)", cfg.sudo)
        cfg.lock_password = _ask_bool("Lock password (key-only login)", cfg.lock_password)
        cfg.ssh_pwauth = _ask_bool("Allow SSH password auth", cfg.ssh_pwauth)

    if cfg.has("ssh"):
        cfg.ssh_keys = _ask_list("SSH public keys (ssh-rsa / ssh-ed25519 ...)")

    if cfg.has("root"):
        cfg.disable_root = _ask_bool("Disable root SSH login", cfg.disable_root)

    if cfg.has("network"):
        cfg.net_mode = _choose("Network mode:", ["dhcp", "static"]).split()[0]
        if cfg.net_mode == "static":
            cfg.net_interface = _ask("Interface name", cfg.net_interface)
            cfg.net_address = _ask("IP address", cfg.net_address)
            cfg.net_netmask = _ask("Netmask", cfg.net_netmask)
            cfg.net_gateway = _ask("Gateway", cfg.net_gateway)
            cfg.net_dns = _ask_list("DNS servers")
            cfg.net_search = _ask_list("DNS search domains (blank=none)")

    if cfg.has("packages"):
        cfg.package_upgrade = _ask_bool("Upgrade packages on first boot", cfg.package_upgrade)
        cfg.packages = _ask_list("Packages to install (blank=none)")

    if cfg.has("locale"):
        cfg.timezone = _ask("Timezone", cfg.timezone)
        cfg.locale = _ask("Locale", cfg.locale)
        cfg.keyboard_layout = _ask("Keyboard layout", cfg.keyboard_layout)

    if cfg.has("disk"):
        cfg.grow_device = _ask("Grow device", cfg.grow_device)
        cfg.grow_partition = _ask("Partition number", cfg.grow_partition)

    if cfg.has("ntp"):
        cfg.ntp_servers = _ask_list("NTP servers")
        if not cfg.ntp_servers:
            cfg.ntp_servers = ["pool.ntp.org"]

    if cfg.has("files"):
        print("Write files: for each, give path then content (blank path ends).")
        while True:
            p = input("  file path (blank to stop): ").strip()
            if not p:
                break
            c = input("  file content: ").strip()
            perm = input("  permissions [0644]: ").strip() or "0644"
            cfg.write_files.append({"path": p, "content": c, "permissions": perm})

    if cfg.has("bootcmd"):
        cfg.bootcmd = _ask_list("bootcmd (early boot commands)")

    if cfg.has("firstboot"):
        cfg.firstboot = _ask_list("First-boot commands (runcmd)")

    if cfg.has("final"):
        cfg.final_message = _ask("Final message", cfg.final_message)

    if cfg.has("sysprep"):
        cfg.sysprep = _ask_bool("Run Sysprep generalize (new SID)", cfg.sysprep)
        if cfg.sysprep:
            cfg.sysprep_organization = _ask("Organization", cfg.sysprep_organization)
            cfg.sysprep_owner = _ask("Owner", cfg.sysprep_owner)
            cfg.sysprep_computer_prefix = _ask("Computer-name prefix", cfg.sysprep_computer_prefix)
            cfg.sysprep_timezone = _ask("Timezone", cfg.sysprep_timezone)
            cfg.sysprep_locale = _ask("Locale (UI)", cfg.sysprep_locale)
            cfg.sysprep_product_key = input("Product key (blank=skip): ").strip()

    return cfg


def load_json(path: str) -> TemplateConfig:
    with open(path, "r", encoding="utf-8") as fh:
        return TemplateConfig.from_dict(json.load(fh))
