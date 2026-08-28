# Changelog

All notable changes to CloudSeed will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-08-28

### Added
- **Template Maker** — new main menu option to prepare the **current machine as a VM template**:
  - Auto-detects guest OS (`linux`/`windows` via `platform.system()`), virtualization platform (`vsphere`/`kvm`/`physical` via `systemd-detect-virt` + DMI + cloud-init datasource), and admin/root privileges.
  - **Linux path**: runs `cloud-init clean --machine-id`, removes `/etc/machine-id`, `/var/lib/dbus/machine-id`, `/var/lib/cloud/instance*`, and all `/etc/ssh/ssh_host_*` keys (regenerated on first boot).
  - **Windows path**: locates `sysprep-unattend.xml` (common paths), executes `sysprep.exe /generalize /oobe /shutdown /unattend:<file>` — VM shuts down with pending generalize; next boot creates fresh SID.
  - **CloudSeed removal**: uninstalls pip package, deletes binary from `/usr/local/bin`/`/usr/bin`, removes `~/.cloudseed` config directory.
  - **Full preparation** (option 4): OS-specific clean + CloudSeed removal + `systemctl poweroff` (Linux) or `shutdown /s /t 0` (Windows).
  - Guardrails: refuses to run on physical hardware, requires root/Administrator, confirms destructive actions.

- **Professional Windows EXE metadata** via PyInstaller `--version-file`:
  - `version.txt` (VSVersionInfo) supplies `FileVersion=1.1.0.0`, `ProductVersion=1.1.0.0`, `CompanyName=Davoud Teimouri`, `FileDescription="CloudSeed - cloud-init / Cloudbase-Init VM Template Generator"`, `LegalCopyright`, `OriginalFilename=cloudseed.exe`, `ProductName=CloudSeed`.
  - Visible in Windows Explorer → Properties → Details; enables proper version detection by installers/updaters.

- **Redesigned banner & sub-banner system** (`print_banner`, `print_sub_banner` in `model.py`):
  - Main banner uses box-drawing (`════`) with fixed 64-col layout: version, tagline, platform list, dependency note, dynamic menu title.
  - Sub-banners (`─` lines, 60 cols) show section title + one-line description above every module configuration screen.
  - Consistent visual hierarchy across all menus; no more plain `print("=" * 48)`.

- **Full back-navigation** in interactive flow:
  - `_choose(prompt, options, allow_back=True)` adds `0) ← Back` entry; returns sentinel `"BACK"`.
  - `_choose_module(prompt, options, defaults)` multi-select also supports `0` to return to previous step.
  - Navigation stack: Main Menu → Platform → OS → Module Selection → per-module config; user can back out at any level without restarting.

### Changed
- **`collect_interactive()` rewritten** as a state machine with nested `while True` loops instead of linear recursion; returns `TemplateConfig` only when configuration is complete.
- **Module configuration split** into 14 private `_configure_<module>()` functions (hostname, users, ssh, root, network, packages, locale, disk, ntp, files, bootcmd, firstboot, final, sysprep, vsphere_spec, vsphere_scripts). Each prints its own sub-banner and returns `bool` (False = user wants to go back).
- **Entry points updated**: `toolbox_menu()`, `validator_menu()`, `doctor_menu()`, `template_maker_menu()` now return to main menu via `continue` instead of recursive `collect_interactive()` calls.
- **README.md** — added Template Maker section with full workflow examples; updated main menu screenshot; documented back-navigation and banner style.
- **GUIDE.md** — added §14 (Toolbox), §15 (Config Validator with example output), §16 (Cloud-Init Doctor with example output and CI/CD usage), §17–19 (complete workflows), §20 (validate/diagnose after deployment), §21 (banner/menu overview), §22 (graceful shutdown).

### Fixed
- **Module selection crash** — `_configure_modules` was unpacking `available` as 3-tuple but caller passed 2-tuple `(label, id)`. Removed unused unpacking; module IDs now derived from `cfg.modules` directly.
- **EOFError in automated test pipe** — `_ask`/`_ask_list`/`_ask_bool` now guard against EOF when stdin is not a TTY (returns default).
- **PyInstaller icon warning on Linux** — `--icon` still passed but PyInstaller emits “Ignoring icon; supported only on Windows and macOS!” — harmless, binary works.

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
- **`collect_interactive()`** returns `TemplateConfig` or `int` (submenu exit code); CLI handles both.
- **`generate_all()`** accepts `interactive` flag to control overwrite prompts (batch mode skips prompts).
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