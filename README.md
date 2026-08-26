# cloudseed

Command-line menu app that builds **cloud-init** customization templates for
new VM provisioning on **VMware vSphere** and **KVM** — for both **Linux**
(cloud-init) and **Windows** (Cloudbase-Init).

Zero dependencies (Python 3 standard library only). Runs on Windows and Linux.

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

This writes:
- `meta-data` and `user-data` (Linux cloud-init, for vSphere/KVM seed ISO or NoCloud)
- `cloudbase-init-unattend.conf` + `cloudbase-init.conf` (Windows Cloudbase-Init)
- `README.txt` explaining how to apply each on the chosen platform

## Interactive menu flow

1. Pick target platform: **VMware vSphere** or **KVM**
2. Pick OS: **Linux** or **Windows**
3. Select which cloud-init / Cloudbase-Init modules to include
4. Fill the chosen options (hostname, user, SSH keys, network, packages, ...)
5. Choose output directory
6. Files generated + copy/paste apply instructions printed

## Supported modules

| Module            | Linux | Windows |
|-------------------|:-----:|:-------:|
| hostname          |   x   |    x    |
| user / password   |   x   |    x    |
| SSH authorized keys|  x   |    x    |
| network (dhcp/static)| x |    x    |
| packages          |   x   |    -    |
| timezone          |   x   |    x    |
| disk grow (LVM)   |   x   |    -    |
| NTP               |   x   |    x    |
| first-boot scripts|   x   |    x    |

## Notes on platforms

- **vSphere**: attach the generated `user-data`/`meta-data` as a CD-ROM (config
  drive / seed ISO) using `mkisofs`/`genisoimage`, or via vApp properties.
- **KVM**: use `virsh`/`virt-install` with `--cloud-init user-data=...` or a
  NoCloud seed ISO.
- **Windows**: drop the generated `cloudbase-init*.conf` into
  `C:\Program Files\Cloudbase Solutions\Cloudbase-Init\conf\` before first boot.

## License

MIT
