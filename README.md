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
- **No ISO** is produced — CloudSeed is config-only. Full apply steps in
  [GUIDE.md](GUIDE.md).

## License

MIT
