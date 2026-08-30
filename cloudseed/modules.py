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
    # Template Best Practices
    ("template_best_practices", "Template Best Practices (Cleanup, Logs, Caches, SSH, Machine-ID)", ["linux", "windows"]),
    # Platform compatibility settings
    ("platform_hostname", "Let Platform Set Hostname (vSphere/KVM)", ["linux", "windows"]),
    ("platform_network", "Let Platform Handle Network (Avoid Conflicts)", ["linux", "windows"]),
    ("platform_ntp", "Let Platform Handle NTP", ["linux", "windows"]),
    # vSphere Customization Spec
    ("vsphere_spec", "Export vSphere Customization Spec", ["linux", "windows"]),
    # vSphere Pre/Post Customization Scripts
    ("vsphere_scripts", "vSphere Pre/Post Customization Scripts", ["linux", "windows"]),
]
