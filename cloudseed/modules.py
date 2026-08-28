"""Module catalog: every cloud-init / Cloudbase-Init option offered in the menu.

Each module: id, label, the OSes it applies to, and the config field(s) it drives.
Recommended defaults live on TemplateConfig; the menu lets the user override.
"""

# id, label, os list
MODULES = [
    ("hostname", "Set Hostname", ["linux", "windows"]),
    ("users", "Create Admin User + Password + Sudo", ["linux", "windows"]),
    ("ssh", "SSH Authorized Keys + Password Auth Toggle", ["linux", "windows"]),
    ("root", "Harden Root (Disable Root Login)", ["linux"]),
    ("network", "Network (DHCP / Static, DNS)", ["linux", "windows"]),
    ("packages", "Install OS Packages / Upgrade", ["linux"]),
    ("locale", "Locale + Keyboard + Timezone", ["linux"]),
    ("disk", "Grow Root Filesystem / LVM", ["linux"]),
    ("ntp", "NTP Time Servers", ["linux", "windows"]),
    ("files", "Write Arbitrary Files", ["linux", "windows"]),
    ("bootcmd", "Early Boot Commands (bootcmd)", ["linux"]),
    ("firstboot", "First-Boot Commands (runcmd)", ["linux", "windows"]),
    ("final", "Final Status Message", ["linux"]),
    ("sysprep", "Windows Sysprep Generalize (New SID)", ["windows"]),
]
