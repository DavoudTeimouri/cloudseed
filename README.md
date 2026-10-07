# CloudSeed

**CloudSeed** generates **cloud-init** (Linux) and **Cloudbase-Init + Sysprep** (Windows) configuration files for VM template provisioning on **VMware vSphere**, **KVM**, and **Physical/Other** platforms.

**Config-only**: CloudSeed emits `user-data`/`meta-data`, Cloudbase-Init conf files, and a Windows Sysprep answer file. It does **not** build an ISO — you apply the config directly (guestinfo/vApp on vSphere, `--cloud-init` on KVM, or drop-in on the golden image). See [GUIDE.md](GUIDE.md).

Native Rust binary — zero runtime dependencies. Single-file executables for Linux and Windows.

## Supported cloud-init versions

| cloud-init version | Status | Notes |
|--------------------|--------|-------|
| **23.x - 24.x** | ✅ Fully supported | Current stable, all modules |
| **22.x** | ✅ Supported | Minor differences in network v2 syntax |
| **21.x** | ⚠️ Limited | Missing some modules (ntp, growpart) |
| **< 21** | ❌ Not supported | Too old for modern config schema |

CloudSeed generates configs compatible with **cloud-init ≥ 22.1**. Run `cloud-init --version` on your golden image to check.

## Install

### Pre-built binaries (recommended)

Download from [GitHub Releases](https://github.com/DavoudTeimouri/cloudseed/releases):

```bash
# Linux
curl -L -o cloudseed https://github.com/DavoudTeimouri/cloudseed/releases/latest/download/cloudseed-linux-x86_64
chmod +x cloudseed

# Windows (PowerShell)
Invoke-WebRequest -Uri "https://github.com/DavoudTeimouri/cloudseed/releases/latest/download/cloudseed-windows-x86_64.zip" -OutFile cloudseed.zip
Expand-Archive cloudseed.zip
```

### Build from source

```bash
git clone https://github.com/DavoudTeimouri/cloudseed
cd cloudseed
cargo build --release
# Binary at ./target/release/cloudseed (or cloudseed.exe on Windows)
```

Requires Rust 1.75+ (`rustup install stable`).

## Usage

**Subcommand-based CLI** (batch-only, designed for automation/CI/CD):

```bash
# Generate configuration from YAML/TOML config
cloudseed generate --config config.yaml --output ./out

# Dry-run: preview generated files without writing
cloudseed generate --config config.yaml --dry-run

# Validate configuration (checks for common issues)
cloudseed validate --config config.yaml

# Validate and auto-fix (e.g., plaintext password → hash)
cloudseed validate --config config.yaml --fix-it

# Generate shell completions
cloudseed completion bash > /etc/bash_completion.d/cloudseed
cloudseed completion zsh > ~/.zsh/completions/_cloudseed
cloudseed completion fish > ~/.config/fish/completions/cloudseed.fish
cloudseed completion powershell > cloudseed.ps1
cloudseed completion elvish > ~/.config/elvish/lib/cloudseed.elv
```

### Configuration file (YAML/TOML)

```yaml
# config.yaml
platform: "vsphere"          # vsphere | kvm | physical
os_type: "linux"             # linux | windows
modules:
  - "hostname"
  - "users"
  - "ssh"
  - "network"
  - "packages"
  - "firstboot"

# Hostname
hostname: ""                 # empty = auto-generate from prefix
hostname_prefix: "vm"
use_platform_hostname: true  # let platform set hostname

# User
username: "admin"
password: "ChangeMe!123"     # hashed to $6$ by default
plaintext_password: false
password_rounds: 5000
sudo: true
lock_password: false
ssh_pwauth: false
disable_root: true
ssh_keys:
  - "ssh-rsa AAAA..."

# Network
net_mode: "dhcp"             # dhcp | static
net_interface: "eth0"
net_address: ""
net_netmask: "255.255.255.0"
net_gateway: ""
net_dns:
  - "8.8.8.8"
  - "1.1.1.1"
net_search: []
let_platform_handle_network: false

# Packages
package_upgrade: true
packages:
  - "nginx"

# Locale / Timezone
timezone: "UTC"
locale: "en_US.UTF-8"
keyboard_layout: "us"

### Interactive timezone selection

```bash
# Interactive timezone configuration (region -> zone hierarchy)
cloudseed timezone --config config.yaml
```

# Disk
grow_device: "/dev/sda"
grow_partition: "1"

# NTP
ntp_servers:
  - "pool.ntp.org"
let_platform_handle_ntp: false

# Files
write_files:
  - path: "/etc/foo"
    content: "bar"
    permissions: "0644"

# Commands
bootcmd: []
firstboot:
  - "systemctl enable nginx"

final_message: "CloudSeed: system ready."

# Windows only:
sysprep: true
sysprep_organization: "MyOrg"
sysprep_owner: "Administrator"
sysprep_computer_prefix: "WIN"
sysprep_timezone: "W. Europe Standard Time"
sysprep_locale: "en-US"
sysprep_product_key: ""

# vSphere Customization Spec export:
export_vsphere_spec: false
vsphere_spec_name: "CloudSeed-Spec"

# vSphere Pre/Post Customization Scripts:
vsphere_pre_script: ""
vsphere_post_script: ""
use_sample_scripts: false
```

Minimal Linux example:

```yaml
os_type: "linux"
modules:
  - "hostname"
  - "users"
  - "ssh"
hostname: "web01"
username: "admin"
ssh_keys:
  - "ssh-rsa AAAA..."
```

### Output directory structure

Files are organized into **platform/OS specific subdirectories**:

```
out/
├── vsphere-linux/
│   ├── user-data
│   ├── meta-data
│   ├── cloudseed.yaml
│   └── README.txt
├── kvm-windows/
│   ├── cloudbase-init.conf
│   ├── cloudbase-init-unattend.conf
│   ├── sysprep-unattend.xml
│   ├── run-sysprep.bat
│   ├── cloudseed.yaml
│   └── README.txt
└── physical-linux/
    ├── user-data
    ├── meta-data
    ├── cloudseed.yaml
    └── README.txt
```

**Linux** (`out/<platform>-linux/`):
- `user-data` — cloud-config customization
- `meta-data` — instance identity (hostname)
- `cloudseed.yaml` — the config itself (re-run or tweak later)
- `README.txt` — quick reference with warnings

**Windows** (`out/<platform>-windows/`):
- `cloudbase-init.conf` / `cloudbase-init-unattend.conf` — Cloudbase-Init service config
- `sysprep-unattend.xml` — Sysprep answer file (generates a **new SID**)
- `run-sysprep.bat` — runs Sysprep generalize
- `cloudseed.yaml`, `README.txt`

**vSphere extras** (when enabled, in `out/vsphere-<os>/`):
- `vsphere-customization-spec.xml` — vSphere Guest Customization Specification (XML)
- `vsphere-pre-script.sh/.bat` — Pre-customization script
- `vsphere-post-script.sh/.bat` — Post-customization script

## Supported modules

| Module | Linux | Windows | cloud-init min | Description |
|--------|:-----:|:-------:|:---:|-------------|
| `hostname` | ✅ | ✅ | 22.1 | Set hostname |
| `users` | ✅ | ✅ | 22.1 | Create admin user + password + sudo/Administrators |
| `ssh` | ✅ | ✅ | 22.1 | SSH authorized keys + password auth toggle |
| `root` | ✅ | ❌ | 22.1 | Harden root (disable root SSH login) |
| `network` | ✅ | ✅ | 22.1 | Network (DHCP / static IP, DNS, search domains) |
| `packages` | ✅ | ❌ | 22.1 | Install OS packages / upgrade on first boot |
| `locale` | ✅ | ✅ | 22.1 | Locale + keyboard + timezone |
| `disk` | ✅ | ❌ | 22.1 | Grow root filesystem / LVM (growpart) |
| `ntp` | ✅ | ✅ | 22.1 | NTP time servers + pools |
| `files` | ✅ | ✅ | 22.1 | Write arbitrary files to target |
| `bootcmd` | ✅ | ❌ | 22.1 | Early boot commands |
| `firstboot` | ✅ | ✅ | 22.1 | First-boot commands (runcmd / LocalScripts) |
| `final` | ✅ | ❌ | 22.1 | Final status message on console |
| `template_best_practices` | ✅ | ✅ | N/A | Template cleanup & preparation |

### Platform compatibility modules (avoid cloud-init conflicts)

| Module | Linux | Windows | Description |
|--------|:-----:|:-------:|-------------|
| `platform_hostname` | ✅ | ✅ | Let platform (vSphere/KVM/Physical) set VM hostname (default: on) |
| `platform_network` | ✅ | ✅ | Let platform handle network config (avoid cloud-init conflicts) |
| `platform_ntp` | ✅ | ✅ | Let platform handle NTP (avoid cloud-init conflicts) |

> **Note:** Platform modules appear for all platforms. When a platform module is selected, its cloud-init equivalent is auto-disabled (and vice versa).

### vSphere-specific modules

| Module | Linux | Windows | Description |
|--------|:-----:|:-------:|-------------|
| `vsphere_spec` | ✅ | ✅ | Export vSphere Customization Spec (XML) + import guide |
| `vsphere_scripts` | ✅ | ✅ | vSphere Pre/Post Customization Scripts (with vendor samples) |

## Platform notes

- **vSphere**: Apply Linux via VM **guestinfo** (`guestinfo.userdata` / `guestinfo.metadata`) or drop `user-data` into the golden image's `/etc/cloud/cloud.cfg.d/`. Windows: place `cloudbase-init*.conf` in the Cloudbase-Init conf dir and run `run-sysprep.bat` before sealing. Use exported Customization Spec XML for vSphere Guest Customization (import guide in generated README.txt).
- **KVM**: `virt-install --cloud-init user-data=./user-data,meta-data=./meta-data`, or drop-in on the image. Windows same as vSphere for conf files.
- **Physical / Other**: Standard cloud-init / Cloudbase-Init configs for any provisioning method (PXE, ISO, config drive, etc.)
- **Passwords are hashed by default** with a `$6$` SHA-512 crypt hash (cloud-init rejects plaintext). Use `--plaintext-password` to emit plaintext (discouraged).
- **No ISO** is produced — CloudSeed is config-only. Full apply steps in [GUIDE.md](GUIDE.md).
- **Conflict avoidance**: Enable "Let Platform Handle..." modules to let vSphere/KVM manage hostname/network/NTP instead of cloud-init.

## Command-line flags

| Flag | Effect |
|------|--------|
| `generate --config FILE --output DIR` | Generate config files from YAML/TOML |
| `generate --config FILE --dry-run` | Preview generated files without writing |
| `validate --config FILE` | Validate configuration, print warnings |
| `validate --config FILE --fix-it` | Validate and auto-fix common issues |
| `completion <shell>` | Generate completion script (bash, zsh, fish, powershell, elvish) |
| `--verbose` | Enable verbose output |
| `--quiet` | Suppress non-essential output |
| `--json-logs` | Output logs in JSON format |
| `--version` | Print version and exit |

## Configuration Validator

Validate exported configurations after generation or on existing config directories:

```bash
cloudseed validate --config ./out/vsphere-linux/cloudseed.yaml
cloudseed validate --config ./out/vsphere-linux/cloudseed.yaml --fix-it
```

Checks:
- **No persistent runs**: `runcmd` (per-instance), `bootcmd` (every boot), `phone_home`, package update/upgrade
- **Config consistency**: required fields, module/file matching
- **Windows**: sysprep-unattend.xml (generalize/specialize/oobe passes), Cloudbase-Init configs

## Warnings & Validation

CloudSeed validates your configuration and emits warnings:

- ⚠️ **Plaintext password** — cloud-init ≥ 22 rejects plaintext passwords. Use default hashing (or `--fix-it`).
- ⚠️ **Static network without gateway** — may leave VM unreachable.
- ⚠️ **Missing SSH keys with password locked** — will lock you out if `lock_password=true` and no keys.
- ⚠️ **Windows without Sysprep** — cloning without generalize creates duplicate SIDs.
- ⚠️ **cloud-init version < 22** — some modules (ntp, growpart) may not work.
- ⚠️ **Disk grow on wrong device** — verify `/dev/sda1` exists on target image.
- ⚠️ **Package list empty with upgrade** — upgrade runs but installs nothing extra.

Warnings are printed during generation and written to the output `README.txt`.

## Template creation (Linux + Windows)

For creating a golden image / template:

1. Run CloudSeed with your desired modules
2. Apply the config to a VM (see GUIDE.md)
3. **Linux**: `sudo cloud-init clean --machine-id` then shutdown
4. **Windows**: run `run-sysprep.bat` (as Administrator) — VM shuts down with generalized state
5. Convert VM to template / clone — each clone gets fresh identity

## Migration from Python version (≤ 2.1.5)

- Config format: JSON → **YAML/TOML** (same field names, different syntax)
- CLI: Interactive menu + `--json` → **Subcommands** (`generate`, `validate`, `completion`)
- Interactive menu: **Removed** — use YAML/TOML config files for automation
- Binary: PyInstaller (`build_dist.py`) → **Cargo** (`cargo build --release`)
- Completions: Python-generated → **clap_complete** (native, more shells)

## License

MIT
