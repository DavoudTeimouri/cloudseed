# Changelog

All notable changes to CloudSeed are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-08-28

### Added
- **Major release**: Platform-aware configuration with conflict avoidance
- **Hostname handling**: Let vSphere/KVM set VM hostname, or auto-generate from prefix
- **Platform compatibility modules**: Let platform handle hostname, network, NTP to avoid cloud-init conflicts
- **vSphere Customization Spec export**: Generate XML spec for vSphere Guest Customization
- **vSphere Pre/Post Customization Scripts**: Sample scripts (Linux/Windows) for pre/post guest customization
- **Physical/Other platform support**: For bare metal or other provisioning targets
- New CLI: `--write-to-cloud-init-path` writes directly to `/etc/cloud/cloud.cfg.d/`
- New CLI: `--detect-cloud-init` shows version compatibility

### Changed
- **Menu labels**: Human-readable Title Case (e.g., "Set Hostname", "Create Admin User + Password + Sudo")
- **Platform options**: "vSphere (VMware)", "KVM (libvirt)", "Physical / Other"
- **OS options**: "Linux", "Windows"
- **Default hostname**: Empty = auto-generate from platform/prefix
- **Network config**: Optional platform-handled mode to avoid cloud-init conflicts
- **NTP config**: Optional platform-handled mode
- **Output directory**: Default `./cloudseed-out` in current working directory

### Fixed
- Config validation warnings now written to output `README.txt`
- Windows static network without gateway warning

## [0.2.2] - 2026-08-27

### Added
- Human-readable menu labels (Title Case)
- Cloud-init version detection
- Config validation warnings in README output
- Write directly to cloud-init config path

## [0.2.1] - 2026-08-27

### Added
- **SHA-512 password hashing** for the `passwd` field (cloud-init rejects
  plaintext). Resolution chain: host `crypt()` → `openssl passwd -6` →
  pure-stdlib `$6$` fallback (`crypt_sha512.py`).
- `--plaintext-password` flag to opt out of hashing (discouraged).
- **Windows static network**: emits `netsh interface ip set address/add dns`
  as a first-boot command so Cloudbase-Init can apply a static IP without a
  config drive.
- **GitHub Actions CI**: ubuntu + windows, Python 3.8 & 3.12, installs the
  package and runs the pytest suite on push/PR.

### Fixed
- Pure-stdlib SHA-512 fallback no longer hangs on an empty password (the
  repeated-input buffer grew by zero bytes in that case).

## [0.2.0] - 2026-08-26

### Added
- Full **module catalog** (14 modules) with recommended defaults; every module
  is selectable/deselectable in the interactive menu.
- **config-only** output — no seed ISO is built. Linux `user-data`/`meta-data`
  plus Windows `cloudbase-init*.conf` + `sysprep-unattend.xml` +
  `run-sysprep.bat`.
- **Windows Sysprep** answer file that generalizes the image (new SID) — the
  critical step before cloning a Windows VM.
- `GUIDE.md` with apply instructions for vSphere (guestinfo / vApp), KVM
  (`virt-install --cloud-init`), and Windows (Cloudbase-Init + Sysprep).
- `build_dist.py` (PyInstaller one-file) portable binary builder.

### Changed
- Display name is **CloudSeed**; package stays lowercase `cloudseed`.
- Default branch renamed `master` → `main`.

## [0.1.0] - 2026-08-26

### Added
- Initial release: interactive menu + batch (`--json`) CLI that generates
  cloud-init customization config for VMware vSphere and KVM, Linux and Windows.
- Zero-dependency (Python 3 standard library only).
- 8-test baseline suite.