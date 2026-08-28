# CloudSeed

Command-line menu app that builds **cloud-init** customization configuration for new VM provisioning on **VMware vSphere** and **KVM** — for both **Linux** (cloud-init) and **Windows** (Cloudbase-Init + Sysprep).

**Config-only:** CloudSeed emits `user-data`/`meta-data`, Cloudbase-Init conf files and a Windows Sysprep answer file. It does **not** build an ISO — you apply the config directly (guestinfo/vApp on vSphere, `--cloud-init` on KVM, or drop-in on the golden image). See [GUIDE.md](GUIDE.md).

Zero dependencies (Python 3 standard library only). A portable single-file binary is available via `python build_dist.py` (PyInstaller). Runs on Windows and Linux.

## Supported cloud-init versions

| cloud-init version | Status | Notes |
|-------------------|--------|-------|
| **23.x - 24.x** | ✅ Fully supported | Current stable, all modules |
| **22.x** | ✅ Supported | Minor differences in network v2 syntax |
| **21.x** | ⚠️ Limited | Missing some modules (ntp, growpart) |
| **< 21** | ❌ Not supported | Too old for modern config schema |

CloudSeed generates configs compatible with **cloud-init ≥ 22.1**. The interactive menu and batch mode will warn if your target image runs an older version. Run `cloud-init --version` on your golden image to check.

## Install

```bash
git clone <repo-url> cloudseed
cd cloudseed
pip install -e .
```

Or just run it (no install needed):

```bash
python -m cloudseed
```

## Usage

Interactive menu:

```bash
cloudseed            # or: python -m cloudseed
```

Non-interactive (batch) — feed config as JSON:

```bash
cloudseed --json config.json --out ./out
```

This writes (config-only, no ISO):
- **Linux**: `user-data`, `meta-data`, `cloudseed.json`, `README.txt`
- **Windows**: `cloudbase-init.conf`, `cloudbase-init-unattend.conf`, `sysprep-unattend.xml`, `run-sysprep.bat`, `cloudseed.json`, `README.txt`

## Interactive menu flow

1. Pick target platform: **VMware vSphere** or **KVM**
2. Pick OS: **Linux** or **Windows**
3. Multi-select cloud-init / Cloudbase-Init **modules** (all recommended by default; deselect any)
4. For each selected module, defaults are shown — press Enter to accept or type an override
5. Choose output directory (created in current path if not exists)
6. Files generated + apply instructions printed (see GUIDE.md)

## Supported modules (all configurations)

| Module | Linux | Windows | cloud-init min | Description |
|--------|:-----:|:-------:|:---:|-------------|
| `hostname` | ✅ | ✅ | 22.1 | Set hostname |
| `users` | ✅ | ✅ | 22.1 | Create admin user + password + sudo/Administrators |
| `ssh` | ✅ | ✅ | 22.1 | SSH authorized keys + password auth toggle |
| `root` | ✅ | ❌ | 22.1 | Harden root (disable root SSH login) |
| `network` | ✅ | ✅ | 22.1 | Network (DHCP / static IP, DNS, search domains) |
| `packages` | ✅ | ❌ | 22.1 | Install OS packages / upgrade on first boot |
| `locale` | ✅ | ❌ | 22.1 | Locale + keyboard + timezone |
| `disk` | ✅ | ❌ | 22.1 | Grow root filesystem / LVM (growpart) |
| `ntp` | ✅ | ✅ | 22.1 | NTP time servers + pools |
| `files` | ✅ | ✅ | 22.1 | Write arbitrary files to target |
| `bootcmd` | ✅ | ❌ | 22.1 | Early boot commands (bootcmd) |
| `firstboot` | ✅ | ✅ | 22.1 | First-boot commands (runcmd / LocalScripts) |
| `final` | ✅ | ❌ | 22.1 | Final status message on console |
| `sysprep` | ❌ | ✅ | N/A | Windows Sysprep generalize (new SID) |

## Notes on platforms

- **vSphere**: apply Linux via VM **guestinfo** (`guestinfo.userdata` / `guestinfo.metadata`) or drop `user-data` into the golden image's `/etc/cloud/cloud.cfg.d/`. Windows: place `cloudbase-init*.conf` in the Cloudbase-Init conf dir and run `run-sysprep.bat` before sealing.
- **KVM**: `virt-install --cloud-init user-data=./user-data,meta-data=./meta-data`, or drop-in on the image. Windows same as vSphere for conf files.
- **Passwords are hashed by default** with a `$6$` SHA-512 crypt hash (cloud-init rejects plaintext). Resolution: host `crypt()` → `openssl passwd -6` → pure-stdlib fallback. Use `--plaintext-password` to emit plaintext (discouraged).
- **No ISO** is produced — CloudSeed is config-only. Full apply steps in [GUIDE.md](GUIDE.md).

## Command-line flags

| Flag | Effect |
|------|--------|
| *(none)* | Interactive menu (platform → OS → modules → per-module overrides). |
| `--json FILE` | Batch mode: read a saved config and generate files. No prompts. |
| `--out DIR` | Output directory (default `./cloudseed-out` in current path). |
| `--plaintext-password` | Emit the password verbatim instead of a `$6$` SHA-512 hash. Discouraged — cloud-init rejects plaintext on most images. |
| `--print` | (batch) also print generated contents to stdout. |
| `--version` | Print `CloudSeed <version>` and exit. |
| `--detect-cloud-init` | Detect installed cloud-init version on current system and show compatibility. |
| `--write-to-cloud-init-path` | (interactive) write generated user-data directly to `/etc/cloud/cloud.cfg.d/99-cloudseed.cfg` (requires root). |

## Configuration reference (JSON / `--json`)

`cloudseed.json` is written alongside every run and is the full config — you can edit it and re-run with `--json` (no menu). Key fields:

```jsonc
{
  "platform": "vsphere",          // "vsphere" | "kvm"
  "os_type": "linux",             // "linux" | "windows"
  "modules": ["hostname","users","ssh","network","packages","firstboot"],
  "hostname": "web01",
  "username": "admin",
  "password": "ChangeMe!123",     // hashed to $6$ by default
  "plaintext_password": false,    // true => emit plaintext (see flag)
  "password_rounds": 5000,
  "sudo": true,
  "lock_password": false,
  "ssh_pwauth": false,
  "disable_root": true,
  "ssh_keys": ["ssh-rsa AAAA..."],
  "net_mode": "dhcp",             // "dhcp" | "static"
  "net_interface": "eth0",
  "net_address": "", "net_netmask": "255.255.255.0", "net_gateway": "",
  "net_dns": ["8.8.8.8","1.1.1.1"],
  "net_search": [],
  "package_upgrade": true, "packages": ["nginx"],
  "timezone": "UTC",
  "locale": "en_US.UTF-8", "keyboard_layout": "us",
  "grow_device": "/dev/sda", "grow_partition": "1",
  "ntp_servers": ["pool.ntp.org"],
  "write_files": [{"path":"/etc/foo","content":"bar","permissions":"0644"}],
  "bootcmd": [], "firstboot": ["systemctl enable nginx"],
  "final_message": "CloudSeed: system ready.",
  // Windows only:
  "sysprep": true, "sysprep_organization": "MyOrg",
  "sysprep_owner": "Administrator", "sysprep_computer_prefix": "WIN",
  "sysprep_timezone": "W. Europe Standard Time", "sysprep_locale": "en-US",
  "sysprep_product_key": ""
}
```

Minimal Linux example:

```json
{"os_type":"linux","modules":["hostname","users","ssh"],
 "hostname":"web01","username":"admin","ssh_keys":["ssh-rsa AAAA..."]}
```

Re-run without the menu:

```bash
cloudseed --json out/cloudseed.json --out out2
```

## Warnings & Validation

CloudSeed validates your configuration and emits warnings:

- ⚠️ **Plaintext password** — cloud-init ≥ 22 rejects plaintext passwords. Use default hashing.
- ⚠️ **Static network without gateway** — may leave VM unreachable.
- ⚠️ **Missing SSH keys with password locked** — will lock you out if `lock_password=true` and no keys.
- ⚠️ **Windows without Sysprep** — cloning without generalize creates duplicate SIDs.
- ⚠️ **cloud-init version < 22** — some modules (ntp, growpart) may not work.
- ⚠️ **Disk grow on wrong device** — verify `/dev/sda1` exists on target image.
- ⚠️ **Package list empty with upgrade** — upgrade runs but installs nothing extra.

Warnings are printed during interactive/batch mode and also written to the output `README.txt`.

## Output directory

By default CloudSeed creates `./cloudseed-out/` in the **current working directory**. The directory contains all generated files plus a `README.txt` with apply instructions specific to your configuration.

## Template creation (Linux + Windows)

For creating a golden image / template:
1. Run CloudSeed with your desired modules
2. Apply the config to a VM (see GUIDE.md)
3. **Linux**: `sudo cloud-init clean --machine-id` then shutdown
4. **Windows**: run `run-sysprep.bat` (as Administrator) — VM shuts down with generalized state
5. Convert VM to template / clone — each clone gets fresh identity

## License

MIT