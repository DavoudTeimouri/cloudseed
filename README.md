# CloudSeed

Command-line menu app that builds **cloud-init** customization configuration for
new VM provisioning on **VMware vSphere** and **KVM** — for both **Linux**
(cloud-init) and **Windows** (Cloudbase-Init + Sysprep).

**Config-only:** CloudSeed emits `user-data`/`meta-data`, Cloudbase-Init conf
files and a Windows Sysprep answer file. It does **not** build an ISO — you
apply the config directly (guestinfo/vApp on vSphere, `--cloud-init` on KVM, or
drop-in on the golden image). See [GUIDE.md](GUIDE.md).

Zero dependencies (Python 3 standard library only). A portable single-file
binary is available via `python build_dist.py` (PyInstaller). Runs on Windows
and Linux.

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
- Linux: `user-data`, `meta-data`, `cloudseed.json`, `README.txt`
- Windows: `cloudbase-init.conf`, `cloudbase-init-unattend.conf`,
  `sysprep-unattend.xml`, `run-sysprep.bat`, `cloudseed.json`, `README.txt`

## Interactive menu flow

1. Pick target platform: **VMware vSphere** or **KVM**
2. Pick OS: **Linux** or **Windows**
3. Multi-select cloud-init / Cloudbase-Init **modules** (all recommended by default; deselect any)
4. For each selected module, defaults are shown — press Enter to accept or type an override
5. Choose output directory
6. Files generated + apply instructions printed (see GUIDE.md)

## Supported modules

| Module              | Linux | Windows | Notes |
|---------------------|:-----:|:-------:|-------|
| hostname            |   x   |    x    | |
| users + sudo        |   x   |    x    | |
| SSH keys / pw-auth  |   x   |    x    | |
| root hardening      |   x   |    -    | disable root SSH |
| network (dhcp/static)| x  |    x    | DNS, search |
| packages / upgrade  |   x   |    -    | |
| locale + keyboard   |   x   |    -    | + timezone |
| disk grow / LVM     |   x   |    -    | growpart |
| NTP                 |   x   |    x    | |
| write files         |   x   |    x    | arbitrary files |
| bootcmd             |   x   |    -    | early boot |
| first-boot (runcmd) |   x   |    x    | |
| final message       |   x   |    -    | |
| Sysprep (new SID)   |   -   |    x    | generalize + answer file |

## Notes on platforms

- **vSphere**: apply Linux via VM **guestinfo** (`guestinfo.userdata` /
  `guestinfo.metadata`) or drop `user-data` into the golden image's
  `/etc/cloud/cloud.cfg.d/`. Windows: place `cloudbase-init*.conf` in the
  Cloudbase-Init conf dir and run `run-sysprep.bat` before sealing.
- **KVM**: `virt-install --cloud-init user-data=./user-data,meta-data=./meta-data`,
  or drop-in on the image. Windows same as vSphere for conf files.
- **Passwords are hashed by default** with a `$6$` SHA-512 crypt hash
  (cloud-init rejects plaintext). Resolution: host `crypt()` → `openssl passwd -6`
  → pure-stdlib fallback. Use `--plaintext-password` to emit plaintext (discouraged).
- **No ISO** is produced — CloudSeed is config-only. Full apply steps in
  [GUIDE.md](GUIDE.md).

## Command-line flags

| Flag | Effect |
|------|--------|
| *(none)* | Interactive menu (platform → OS → modules → per-module overrides). |
| `--json FILE` | Batch mode: read a saved config and generate files. No prompts. |
| `--out DIR` | Output directory (default `./out` in interactive mode). |
| `--plaintext-password` | Emit the password verbatim instead of a `$6$` SHA-512 hash. Discouraged — cloud-init rejects plaintext on most images. |
| `--print` | (batch) also print generated contents to stdout. |
| `--version` | Print `CloudSeed <version>` and exit. |

## Configuration reference (JSON / `--json`)

`cloudseed.json` is written alongside every run and is the full config — you
can edit it and re-run with `--json` (no menu). Key fields:

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

## License

MIT
