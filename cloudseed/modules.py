"""Module catalog: every cloud-init / Cloudbase-Init option offered in the menu.

Each module: id, label, the OSes it applies to, and the config field(s) it drives.
Recommended defaults live on TemplateConfig; the menu lets the user override.
"""

# id, label, os list
MODULES = [
    ("hostname", "Set hostname", ["linux", "windows"]),
    ("users", "Create admin user + password + sudo", ["linux", "windows"]),
    ("ssh", "SSH authorized keys + password auth toggle", ["linux", "windows"]),
    ("root", "Harden root (disable root login)", ["linux"]),
    ("network", "Network (DHCP / static, DNS)", ["linux", "windows"]),
    ("packages", "Install OS packages / upgrade", ["linux"]),
    ("locale", "Locale + keyboard + timezone", ["linux"]),
    ("disk", "Grow root filesystem / LVM", ["linux"]),
    ("ntp", "NTP time servers", ["linux", "windows"]),
    ("files", "Write arbitrary files", ["linux", "windows"]),
    ("bootcmd", "Early boot commands (bootcmd)", ["linux"]),
    ("firstboot", "First-boot commands (runcmd)", ["linux", "windows"]),
    ("final", "Final status message", ["linux"]),
    ("sysprep", "Windows Sysprep generalize (new SID)", ["windows"]),
]
