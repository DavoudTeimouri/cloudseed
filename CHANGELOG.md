# Changelog

All notable changes to CloudSeed will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-08-28

### Added
- **Toolbox menu** — external tools for VM customization:
  - *Download SID Changer*: fetches `sidchanger.exe` (stratus/sidchanger) to change Windows Machine SID without full Sysprep. Copy to target VM, run as Administrator, reboot.
  - *Run SID Changer*: executes the downloaded tool locally (Windows only, requires Administrator).
- **Config Validator** — validates exported configurations *after generation* or on existing config directories:
  - Checks `runcmd` (per-instance), `bootcmd` (every boot), `phone_home`, package update/upgrade won't re-run unexpectedly.
  - Verifies `cloudseed.json` consistency: required fields, module/file matching.
  - Windows: validates `sysprep-unattend.xml` has generalize/specialize/oobe passes; Cloudbase-Init configs have username/password.
- **Cloud-Init Doctor** — diagnoses cloud-init issues on a **running system** (requires cloud-init installed locally):
  - Full diagnosis: cloud-init status/version/stages, merged config query, systemd services (all cloud-init units), failed units, netplan/networkd, current interfaces, disk space with low-space warnings.
  - Individual checks: status, configuration, boot/services, network, disk.
  - Save diagnosis report as JSON for CI/CD integration.
- **Main Menu restructuring** — interactive entry point now shows: Generate Configuration | Toolbox | Config Validator | Cloud-Init Doctor | Exit.
- **Graceful shutdown on Ctrl+C** — signal handlers (SIGINT, SIGTERM) print "[CloudSeed] Interrupted. Shutting down gracefully..." and exit with code 130 at any prompt.
- **Overwrite protection** — when an output file already exists, CloudSeed asks: Overwrite / Add suffix (`_1`, `_2`…) / Skip.
- **Cloud-init detection & compatibility** — on Linux module selection, if cloud-init is not installed locally, CloudSeed warns that generated configs require cloud-init on the **target VM**, not the build machine. Some features (Validator, Doctor) need cloud-init locally.
- **Windows EXE icon** — custom CloudSeed icon (blue cloud with green seed) embedded in the PyInstaller binary.
- **Banner on every menu** — "CloudSeed v{version} / cloud-init / Cloudbase-Init VM Template Generator / {Menu Title}".

### Changed
- **Output directory default** now `./cloudseed-out` in current working directory (was ambiguous).
- **collect_interactive()** returns `TemplateConfig` or `int` (submenu exit code); CLI handles both.
- **generate_all()** accepts `interactive` flag to control overwrite prompts (batch mode skips prompts).
- **README.md** — added Toolbox, Config Validator, Cloud-Init Doctor sections; updated module tables; added overwrite protection note; added SID Changer workaround docs.
- **GUIDE.md** — added complete workflows for Toolbox (SID Changer), Config Validator (with example output), Cloud-Init Doctor (with example output and CI/CD usage); added banner/menu overview; added graceful shutdown note.

### Fixed
- **Windows static network first-boot** — `netsh` commands now emitted correctly in `firstboot` when `net_mode=static` and `os_type=windows`.
- **vSphere Customization Spec XML** — fixed hostname/domain/nic sections for both Linux and Windows; added proper XML escaping.
- **Sample pre/post scripts** — Linux shebang and Windows `@echo off` preserved; user customizations appended after samples.

## [1.0.0] - 2026-08-27

### Added
- **Platform-aware hostname** — let vSphere/KVM set VM hostname (default), auto-generate from prefix when cloud-init sets it.
- **Conflict avoidance modules** — "Let Platform Handle Network/NTP/Hostname" prevent cloud-init vs platform conflicts.
- **Physical/Other platform** — support bare metal, PXE, config drive, etc.
- **vSphere Customization Spec export** — XML for vCenter Guest Customization Specifications.
- **vSphere Pre/Post Customization Scripts** — sample scripts (Linux bash / Windows bat) for pre-customization (register Satellite, install agents, configure repos) and post-customization (join AD domain, compliance checks, monitoring).
- **Human-readable menu** — Title Case labels, proper platform/OS names.
- **Default output dir** — `./cloudseed-out` in current path.
- **Warnings in README.txt** — validation warnings written to output.
- **All steps/configurations in README/GUIDE** — comprehensive docs.
- **Config output to cloud-init path directly** — `--write-to-cloud-init-path` writes user-data to `/etc/cloud/cloud.cfg.d/99-cloudseed.cfg` (Linux, requires root).
- **cloud-init version detection** — `--detect-cloud-init` shows installed version and compatibility.

### Changed
- **Single-file binary via PyInstaller** — `python build_dist.py` produces `dist/cloudseed` (Linux) / `dist/cloudseed.exe` (Windows).
- **Zero third-party dependencies** — Python stdlib only (PyInstaller is build-time only).
- **Config-only output** — no ISO produced.

### Fixed
- **Password hashing** — default `$6$` SHA-512 crypt via host `crypt()` → `openssl passwd -6` → pure-stdlib fallback; `--plaintext-password` opt-out.
- **Windows Sysprep** — fully unattended answer file (generalize + specialize + oobe) like vSphere Guest Customization.
- **cloud-init network v2** — correct static DHCP/ethernets rendering.

## [0.2.1] - 2026-08-26

### Fixed
- **GitHub Actions release workflow** — publishes both `cloudseed-linux-x86_64.zip` and `cloudseed-windows-x86_64.zip`.
- **Windows build step** — fixed PowerShell build in workflow.
- **upload_url sharing** — fixed between build jobs via `needs.build-linux.outputs.upload_url`.

## [0.2.0] - 2026-08-25

### Added
- **Interactive menu** — platform → OS → modules → per-module overrides.
- **Batch mode** — `--json` reads saved config, generates files without prompts.
- **Core modules** — hostname, users, ssh, root, network, packages, locale, disk, ntp, files, bootcmd, firstboot, final, sysprep.
- **Platform modules** — platform_hostname, platform_network, platform_ntp.
- **vSphere modules** — vsphere_spec, vsphere_scripts.
- **Windows support** — Cloudbase-Init conf, Sysprep unattend.xml, run-sysprep.bat.
- **JSON config persistence** — `cloudseed.json` written every run for re-use.

## [0.1.0] - 2026-08-24

### Added
- Initial project structure.
- cloud-init YAML emitter (stdlib only).
- TemplateConfig dataclass.
- Basic CLI with argparse.