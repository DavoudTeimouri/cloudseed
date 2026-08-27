# Changelog

All notable changes to CloudSeed are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/) and this project adheres to
[Semantic Versioning](https://semver.org/).

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
