"""Data model for a VM template customization.

Holds the collected configuration and the interactive collector.
No third-party dependencies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional


# Modules offered in the menu. `os` lists which OS a module applies to.
MODULES = [
    {"id": "hostname", "label": "Set hostname", "os": ["linux", "windows"]},
    {"id": "user", "label": "Create admin user + password", "os": ["linux", "windows"]},
    {"id": "ssh", "label": "Add SSH authorized keys", "os": ["linux", "windows"]},
    {"id": "network", "label": "Configure network (DHCP / static)", "os": ["linux", "windows"]},
    {"id": "packages", "label": "Install OS packages", "os": ["linux"]},
    {"id": "timezone", "label": "Set timezone", "os": ["linux", "windows"]},
    {"id": "growpart", "label": "Grow root filesystem / LVM", "os": ["linux"]},
    {"id": "ntp", "label": "Configure NTP", "os": ["linux", "windows"]},
    {"id": "firstboot", "label": "Run first-boot scripts / commands", "os": ["linux", "windows"]},
]


@dataclass
class TemplateConfig:
    platform: str = "vsphere"          # "vsphere" | "kvm"
    os_type: str = "linux"             # "linux" | "windows"
    modules: List[str] = field(default_factory=list)

    hostname: str = ""
    # user
    username: str = ""
    password: str = ""
    sudo: bool = True
    lock_password: bool = False
    # ssh
    ssh_keys: List[str] = field(default_factory=list)
    # network
    net_mode: str = "dhcp"             # "dhcp" | "static"
    net_interface: str = ""
    net_address: str = ""
    net_netmask: str = ""
    net_gateway: str = ""
    net_dns: List[str] = field(default_factory=list)
    # packages
    packages: List[str] = field(default_factory=list)
    # timezone
    timezone: str = "UTC"
    # growpart
    grow_device: str = "/dev/sda"
    grow_partition: str = "1"
    # ntp
    ntp_servers: List[str] = field(default_factory=list)
    # firstboot
    firstboot: List[str] = field(default_factory=list)

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
    cfg = TemplateConfig()

    cfg.platform = _choose(
        "Target platform:", ["vsphere (VMware)", "kvm (libvirt)"]
    ).split()[0]
    cfg.os_type = _choose("Guest OS:", ["linux", "windows"]).split()[0]

    available = [m for m in MODULES if cfg.os_type in m["os"]]
    print("\nAvailable customization modules:")
    for i, m in enumerate(available, 1):
        print(f"  {i}) {m['label']}")

    sel = input(
        "Enter module numbers to include (space-separated), or 'a' for all: "
    ).strip().lower()
    if sel == "a":
        cfg.modules = [m["id"] for m in available]
    else:
        idxs = [int(x) for x in sel.split() if x.isdigit()]
        cfg.modules = [available[i - 1]["id"] for i in idxs if 1 <= i <= len(available)]

    if cfg.has("hostname"):
        cfg.hostname = _ask("Hostname", "vm-template")

    if cfg.has("user"):
        cfg.username = _ask("Username", "admin")
        cfg.password = _ask("Password (plaintext; document risk!)", "ChangeMe!123")
        cfg.sudo = _ask_bool("Grant sudo (Linux)", True)
        cfg.lock_password = _ask_bool("Lock password (key-only login)", False)

    if cfg.has("ssh"):
        cfg.ssh_keys = _ask_list("SSH public keys (ssh-rsa / ssh-ed25519 ...)")

    if cfg.has("network"):
        cfg.net_mode = _choose("Network mode:", ["dhcp", "static"]).split()[0]
        if cfg.net_mode == "static":
            cfg.net_interface = _ask("Interface name", "eth0")
            cfg.net_address = _ask("IP address", "192.168.1.50")
            cfg.net_netmask = _ask("Netmask", "255.255.255.0")
            cfg.net_gateway = _ask("Gateway", "192.168.1.1")
            cfg.net_dns = _ask_list("DNS servers")

    if cfg.has("packages"):
        cfg.packages = _ask_list("Packages to install")

    if cfg.has("timezone"):
        cfg.timezone = _ask("Timezone", "UTC")

    if cfg.has("growpart"):
        cfg.grow_device = _ask("Grow device", "/dev/sda")
        cfg.grow_partition = _ask("Partition number", "1")

    if cfg.has("ntp"):
        cfg.ntp_servers = _ask_list("NTP servers (blank = distro default skipped)")

    if cfg.has("firstboot"):
        cfg.firstboot = _ask_list("First-boot commands / scripts")

    return cfg


def load_json(path: str) -> TemplateConfig:
    with open(path, "r", encoding="utf-8") as fh:
        return TemplateConfig.from_dict(json.load(fh))
