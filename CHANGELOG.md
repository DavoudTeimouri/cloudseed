# Changelog

All notable changes to CloudSeed will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.3] - 2026-09-04

### Added
- GitHub Actions CI/CD pipeline with Python 3.8-3.12 test matrix on Linux and Windows.
- Ruff and mypy configuration for linting and type checking.
- Release automation script (`scripts/release.py`) for synchronized version bumps.
- Homebrew and Chocolatey packaging templates.
- Validator, Doctor, Template Maker, and Toolbox regression tests.

### Changed
- Modernized banner with compact CloudSeed logo, aligned status bar, and cleaner frame layout.
- Reworked menu frames to avoid empty bordered body sections.
- Reworked selector lists (timezone, locale, keyboard, disk) with filtering, paging, custom values, and keyboard hints.
- Documented PyInstaller cross-compilation limitation in `build_dist.py`.
- Expanded `.gitignore` for generated output and local artifacts.

### Fixed
- Removed duplicate startup banner before Main Menu.
- Fixed validator parsing for inline YAML lists such as `bootcmd: [echo hello]`.

## [2.0.2] - 2026-08-31

### Added
- Tab completion for output directory path (readline + glob) - type path and press Tab to autocomplete directories
- Sample scripts: when "Use sample scripts" selected, choosing "No" to customize uses samples as-is without prompting for custom content
- File overwrite-all option (menu option 4) applies to all remaining files in batch generation

### Fixed
- Version metadata consistency: all version files (__init__.py, pyproject.toml, version.txt, PyInstaller VSVersionInfo) now correctly report 2.0.2

## [2.0.1] - 2026-08-31

### Fixed
- Version metadata consistency: all version files (__init__.py, pyproject.toml, version.txt, PyInstaller VSVersionInfo) now correctly report 2.0.1
- Removed "NO ISO -- config files only" phrasing from README.txt generation and documentation
- Template Maker documentation updated: cloud-init clean command now includes --logs flag and explicit machine-id removal steps
- Modern UI banner now displays on every main menu iteration (previously only on first launch)
- Type-ahead filtering for timezone/locale/keyboard selectors: type to filter list in real-time, Enter to select first match, number to pick, Backspace to clear filter

### Changed
- CHANGELOG format: removed emoji and markdown tables; now uses clean structured sections (Added, Changed, Fixed, Removed) per version
- Build metadata: FileVersion and ProductVersion in version.txt updated to 2.0.1.0

## [2.0.0] - 2026-08-29

### Breaking Changes
- Windows Sysprep is now mandatory for Windows configurations. The `sysprep` module has been removed from the toggleable module list. Existing cloudseed.json files must remove `"sysprep"` from their modules array.
- Platform modules (`platform_hostname`, `platform_network`, `platform_ntp`) now default ON. Their cloud-init equivalents (`hostname`, `network`, `ntp`) default OFF. Selecting a platform module automatically skips its configuration prompts and disables the cloud-init equivalent.
- Config validator scans 2 directory levels deep by default (configurable). Accepts quoted paths.
- Output directory structure: cloudseed.json written to output root for reuse; generated configs placed in platform/OS subdirectories (e.g., `out/vsphere-linux/`, `out/kvm-windows/`).

### Added
- Post-export validation flow: after generating configurations, CloudSeed automatically runs the Config Validator on the output directory, displays a summary (warnings/pass/fail), then returns to main menu.
- Full IANA timezone database (~600 zones) with type-ahead filtering. Complete Windows timezone list with same filtering.
- Template Best Practices module (`template_best_practices`): granular OS-specific cleanup controls.
  - Linux: log cleanup, temp directories, SSH host keys, machine-id, package cache, systemd journal, udev persistent rules
  - Windows: Event Logs, Windows Update cache, DriverStore (pnputil)
  - Tooling: VMware Tools/open-vm-tools, qemu-guest-agent toggles
- vSphere Customization Spec import guide embedded in generated README.txt with step-by-step vCenter import instructions.
- Pre/Post customization script samples for Linux (bash) and Windows (batch) with multi-line editor; covers Satellite registration, agent installs, AD join, compliance checks, monitoring registration.
- Overwrite-all option in file overwrite prompts (option 4) for batch operations.
- Config validator recursive scan (menu option 2): scans 2+ subdirectory levels for cloudseed.json, lists findings, offers validate/delete/cleanup actions.
- Quoted path support in validator and scanner (e.g., `"C:\My Path"`).

### Template Maker (Prepare Current Machine as Template)
- Multi-confirmation for production safety: typed confirmations required (`PHYSICAL-OK` for physical machines, `NO-ADMIN-OK` for non-root, `I-UNDERSTAND` final).
- Best Practices Checklist: interactive checklist with vendor recommendations per OS/platform (vSphere/KVM/Physical).
- Cleanup script generation: produces standalone `cloudseed-template-cleanup-linux.sh` / `.bat` for manual execution on target VMs.
- Modern consolidated menu: Clean & Prepare, Show Checklist, Generate Script, Remove CloudSeed.

### User Experience
- Modern ASCII banner with box-drawing logo, version, tagline, platform support, zero-dependency badge. Banner now displays on every main menu iteration.
- Box-drawing section headers: consistent framed menus with cyan borders.
- Reverse conflict resolution: selecting a cloud-init module auto-disables its platform equivalent.
- Type-ahead filtering for all selector lists (timezone, locale, keyboard, disk device).

### Validation & Safety
- Platform hostname meta-data fix: `local-hostname` omitted from meta-data when `platform_hostname` enabled (prevents cloud-init + platform conflict).
- Doctor disk space fix: fixed `KeyError: 'errors'` crash in `check_disk_space()`.
- cloudseed.json collision detection: warns before overwriting existing config in platform/OS subdirectory.
- Validator now checks only actual generated files (not potential configs) and validates that cloud-init configurations won't re-run after first boot (per-boot/per-once/per-instance script checks).

### Changed
- Module configuration flow: platform modules skip configuration prompts entirely when selected; cloud-init equivalents auto-disabled and hidden.
- Network configuration: when `platform_network` selected, DHCP/static/DNS prompts skipped.
- NTP configuration: when `platform_ntp` selected, NTP server prompts skipped.
- Windows Sysprep: hidden from module list; only sub-configuration (timezone, locale, product key) shown.

### Fixed
- Doctor KeyError: `check_disk_space()` in `doctor.py` line 251 now initializes `errors` list before use.
- Instance-id + local-hostname conflict: when platform handles hostname, meta-data no longer contains `local-hostname` or `instance-id`.
- Multiple run collision: each run generates unique `iid-<random8>`; collision detection prevents silent overwrites.
- Validation depth: config validator now clearly informs user of 2-level scan depth.

### Build
- Python 3.8+ (stdlib only — zero runtime dependencies)
- PyInstaller for Windows x64 and Linux binaries
- All 14 tests passing (CIDR, module catalog, Linux/Windows user-data, round-trip JSON, password hashing, network static config)

### Documentation Updates
- README.md: v2.0.0 feature highlights, new module table, Template Maker section, validator usage
- GUIDE.md: "Template Best Practices" chapter, vSphere Spec import guide, production warnings, cleanup script usage, explicit cloud-init clean workflow steps
- CHANGELOG.md: detailed entry following professional release format

### Migration Checklist (from 1.5.x)
1. Remove `"sysprep"` from `modules` in any saved `cloudseed.json` (now mandatory for Windows)
2. Re-run module selection — platform modules default ON, cloud-init equivalents OFF
3. Test Template Maker on non-production VM first (new multi-confirm flow)
4. Check generated README.txt for vSphere Spec import steps if using `vsphere_spec`
5. Update CI/CD — output directory structure unchanged (`out/<platform>-<os>/`)

## [1.5.3] - 2026-08-28

### Added
- Selector lists for configuration fields: new generic `_ask_from_list()` helper and specific selectors for fields with known values:
  - `_ask_timezone()` — Linux (IANA) and Windows timezones
  - `_ask_locale()` / `_ask_windows_locale()` — Linux and Windows locale lists
  - `_ask_keyboard_layout()` / `_ask_windows_keyboard()` — Linux keyboard layouts and Windows input method IDs
  - `_ask_grow_device()` / `_ask_partition_number()` — common disk devices and partition numbers
- Applied to interactive configuration: timezone, locale, keyboard layout (Linux & Windows), grow device/partition now show numbered lists with current default marked; user selects by number or types custom value.

### Changed
- Interactive prompts use selector lists: replaced free-text `_ask()` with validated list selectors for fields with known value sets.

## [1.5.2] - 2026-08-28

### Added
- Input validation for network fields: new validation functions (`_is_valid_ip`, `_is_valid_netmask`) and interactive helpers (`_ask_ip`, `_ask_netmask`, `_ask_gateway`, `_ask_dns`) that validate IPv4 addresses, netmasks, gateway, and DNS entries with example hints on invalid input.
- Unique instance-id generation: meta-data now uses a unique `iid-<random8>` per configuration instead of static `iid-cloudseed`, preventing conflicts when deploying multiple VMs from the same config.

### Changed
- Output directory organization: generated files now placed in platform/OS specific subdirectories (e.g., `out/vsphere-linux/`, `out/kvm-windows/`, `out/physical-linux/`) for easier management of multi-platform configurations.
- Network configuration uses validated prompts: IP address, netmask, and gateway fields now validate input and re-prompt with examples (e.g., "Invalid IP address. Example: 192.168.1.100") until valid entry or empty (to keep default).

### Fixed
- Static instance-id collision: fixed hardcoded `iid-cloudseed` in meta-data that would cause cloud-init to skip configuration on subsequent VMs deployed from the same output.

## [1.5.1] - 2026-08-28

### Added
- Interactive module selection with toggle: new multi-select menu (`_choose_module_multi`) where users toggle modules on/off by number, press `c` to configure selected, `a` for all, `n` for none, `0` to go back. Replaces single-pass selection.
- Per-module configuration flow: after pressing `c`, each selected module is configured one-by-one with its own sub-menu (hostname, users, ssh, network, packages, locale, disk, ntp, files, bootcmd, firstboot, final, sysprep, vsphere_spec, vsphere_scripts). Unselected modules use defaults.
- Unified platform module list: all three platform modules (`platform_hostname`, `platform_network`, `platform_ntp`) now appear together in module list for all platforms; no platform-specific filtering.
- Real-time priority conflict resolution: when toggling a platform module (e.g., `platform_hostname`), its cloud-init equivalent (`hostname`) is auto-disabled with info message; vice versa when selecting cloud-init module. Prevents conflicts at selection time.

### Changed
- Module selection UX: from single checklist to persistent toggle menu with immediate visual feedback (green checkmark markers). User sees all options, selects subset, then configures.
- Platform modules always visible: `platform_hostname`, `platform_network`, `platform_ntp` shown for vSphere, KVM, and Physical/Other platforms (previously only vSphere/KVM).
- Defaults: platform modules default ON; cloud-init equivalents (`hostname`, `network`, `ntp`) default OFF but user can explicitly enable them (auto-disables platform module).
- Version bump: 1.4.0 to 1.5.0 across `__init__.py`, `pyproject.toml`, `version.txt`.

### Fixed
- Empty user-data when skipping module config: previously if user accepted all defaults without per-module config, user-data was empty. Now all selected modules are configured sequentially with defaults applied.
- Module configuration order: each selected module's `_configure_*()` runs in defined order; user can go back from any sub-menu to module selection.
- `AttributeError: module 'os' has no attribute 'geteuid'` on Windows: `write_to_cloud_init_path()` and `check_root()` now guard with `platform.system()` check before calling `os.geteuid()`; Windows uses `ctypes.windll.shell32.IsUserAnAdmin()` instead.
- Interactive prompt for `--write-to-cloud-init-path` removed from configuration flow: the prompt "Write user-data directly to /etc/cloud/cloud.cfg.d/99-cloudseed.cfg?" was incorrectly shown during interactive config generation; now only triggers via explicit `--write-to-cloud-init-path` CLI flag (Linux only, requires root).

## [1.4.0] - 2026-08-28

### Added
- Stdlib-only YAML parser in validator (`_safe_load_yaml`): eliminates `pyyaml` dependency; Config Validator now works in PyInstaller binary without external modules.
- Platform-aware module filtering: vSphere-only modules (`vsphere_spec`, `vsphere_scripts`) only appear when platform = vSphere; hidden for KVM/Physical.
- Template Maker detailed options menu (option 5): shows sub-items for each OS (Linux: cloud-init clean, machine-id, SSH keys, logs; Windows: Sysprep generalize, OOBE, shutdown) with per-platform warnings.
- Template Maker physical machine support with acceptance: physical hardware now allowed with explicit warnings and user confirmation ("at your own risk"); no longer hard-blocked.
- Template Maker Sysprep on physical with acceptance: Windows physical machine can run Sysprep generalize with detailed warnings (new SID, OOBE, driver redetection, local admin requirement).
- Guide Help menu: new main menu option showing configuration reference with all modules, sub-items, defaults, and platform applicability.
- Priority-based module selection: when "Let Platform Handle X" modules selected, conflicting cloud-init modules auto-unselected (higher priority to platform modules).
- Cloud-Init Doctor: no external deps; all diagnosis commands use stdlib subprocess; no `pyyaml` or other dependencies.

### Changed
- Config Validator: replaced `yaml.safe_load` with custom `_safe_load_yaml` (stdlib only); handles cloud-config subset: mappings, lists, scalars, nested dicts.
- Template Maker flow: options 1-4 now allow physical machine with confirmation; option 5 shows detailed sub-configuration before execution.
- Module defaults: platform modules (`platform_hostname`, `platform_network`, `platform_ntp`) now default ON; cloud-init equivalents default OFF when platform module selected.
- Version bump: 1.3.0 to 1.4.0 across `__init__.py`, `pyproject.toml`, `version.txt`.

### Fixed
- Config Validator crash: `ModuleNotFoundError: No module named 'yaml'` in PyInstaller binary fixed by removing PyYAML dependency.
- vSphere modules on non-vSphere: `vsphere_spec` and `vsphere_scripts` no longer appear for KVM/Physical platforms.
- Empty user-data: module configuration now properly populates config fields; generated user-data contains selected modules.
- EOFError handling: `_ask`, `_ask_list`, `_ask_bool` guard against EOF in piped/automated runs (return defaults).
- Template Maker physical block: removed hard error; replaced with explicit acceptance prompts with detailed risk warnings.
- Sysprep on physical: now allowed with acceptance; previously blocked entirely.

## [1.3.0] - 2026-08-28

### Added
- Modern menu UI: removed box-drawing banners from sub-menus; only main menu shows the CloudSeed banner (version, tagline, platform list). Sub-menus use clean section headers (`print_section`) with colored titles and descriptions.
- Color-coded messaging: `print_info` (cyan), `print_success` (green), `print_warn` (yellow), `print_error` (red) using ANSI codes; works on Windows 10+ and Linux terminals.
- Toolbox: Valid SID Changer run only; removed invalid `sidchanger.exe` download; now only "Run SID Changer" option that executes Microsoft's official `Sysprep`-based SID change (or user-provided valid tool) on Windows. Toolbox menu clearly documents that no external download is provided.
- Config Validator integration fix: validator no longer crashes on "Config Validator" menu selection; `_configure_validator` now properly calls `validator.validate_all()` with correct parameters.
- Cloud-Init Doctor integration fix: doctor menu now works; individual check functions accept optional `config_dir` parameter.
- Template Maker updated: uses new colorized section headers instead of banners; consistent back-navigation (`0) ← Back`).

### Changed
- Banner removal: `print_banner()` and `print_sub_banner()` removed from `model.py`; replaced by `print_section()` (colored title + description) and `print_info/print_warn/print_error/print_success()` for consistent messaging.
- EXE metadata updated: `CompanyName` changed to `CloudSeed Project` (removed personal name); `FileVersion=1.3.0.0`, `ProductVersion=1.3.0.0`. All other properties retained (`FileDescription`, `LegalCopyright`, `OriginalFilename`, `ProductName`).
- Version bump: 1.2.0 to 1.3.0 across `__init__.py`, `pyproject.toml`, `version.txt`.
- Menu navigation: all sub-menus show `0) ← Back` with cyan highlight; main menu shows `0) Exit`.

### Fixed
- Config Validator crash: selecting "Config Validator" from main menu no longer throws error; validator now receives proper config directory path and runs full validation suite (Linux cloud-init config, Windows sysprep/Cloudbase-Init, JSON consistency, first-boot persistence checks).
- Toolbox SID Changer: removed broken download; "Run SID Changer" now executes `sysprep /generalize /oobe /shutdown /unattend:<file>` for proper Windows SID regeneration (same as Template Maker Windows path).
- Doctor menu: individual diagnosis checks (status, config, boot, network, disk) now work; full diagnosis saves JSON report option functional.
- Cross-module imports: `validator.py`, `doctor.py`, `templatemaker.py`, `toolbox.py` all import colorized printers from `model` instead of old banner functions.

## [1.2.0] - 2026-08-28

### Added
- Template Maker: new main menu option to prepare the current machine as a VM template:
  - Auto-detects guest OS (`linux`/`windows` via `platform.system()`), virtualization platform (`vsphere`/`kvm`/`physical` via `systemd-detect-virt` + DMI + cloud-init datasource), and admin/root privileges.
  - Linux path: runs `cloud-init clean --machine-id`, removes `/etc/machine-id`, `/var/lib/dbus/machine-id`, `/var/lib/cloud/instance*`, and all `/etc/ssh/ssh_host_*` keys (regenerated on first boot).
  - Windows path: locates `sysprep-unattend.xml` (common paths), executes `sysprep.exe /generalize /oobe /shutdown /unattend:<file>` — VM shuts down with pending generalize; next boot creates fresh SID.
  - CloudSeed removal: uninstalls pip package, deletes binary from `/usr/local/bin`/`/usr/bin`, removes `~/.cloudseed` config directory.
  - Full preparation (option 4): OS-specific clean + CloudSeed removal + `systemctl poweroff` (Linux) or `shutdown /s /t 0` (Windows).
  - Guardrails: refuses to run on physical hardware, requires root/Administrator, confirms destructive actions.
- Professional Windows EXE metadata via PyInstaller `--version-file`:
  - `version.txt` (VSVersionInfo) supplies `FileVersion=1.1.0.0`, `ProductVersion=1.1.0.0`, `CompanyName=Davoud Teimouri`, `FileDescription="CloudSeed - cloud-init / Cloudbase-Init VM Template Generator"`, `LegalCopyright`, `OriginalFilename=cloudseed.exe`, `ProductName=CloudSeed`.
  - Visible in Windows Explorer Properties Details; enables proper version detection by installers/updaters.
- Redesigned banner & sub-banner system (`print_banner`, `print_sub_banner` in `model.py`):
  - Main banner uses box-drawing (`════`) with fixed 64-col layout: version, tagline, platform list, dependency note, dynamic menu title.
  - Sub-banners (`─` lines, 60 cols) show section title + one-line description above every module configuration screen.
  - Consistent visual hierarchy across all menus; no more plain `print("=" * 48)`.
- Full back-navigation in interactive flow:
  - `_choose(prompt, options, allow_back=True)` adds `0) ← Back` entry; returns sentinel `"BACK"`.
  - `_choose_module(prompt, options, defaults)` multi-select also supports `0` to return to previous step.
  - Navigation stack: Main Menu → Platform → OS → Module Selection → per-module config; user can back out at any level without restarting.

### Changed
- `collect_interactive()` rewritten as a state machine with nested `while True` loops instead of linear recursion; returns `TemplateConfig` only when configuration is complete.
- Module configuration split into 14 private `_configure_<module>()` functions (hostname, users, ssh, root, network, packages, locale, disk, ntp, files, bootcmd, firstboot, final, sysprep, vsphere_spec, vsphere_scripts). Each prints its own sub-banner and returns `bool` (False = user wants to go back).
- Entry points updated: `toolbox_menu()`, `validator_menu()`, `doctor_menu()`, `template_maker_menu()` now return to main menu via `continue` instead of recursive `collect_interactive()` calls.
- README.md: added Template Maker section with full workflow examples; updated main menu screenshot; documented back-navigation and banner style.
- GUIDE.md: added sections for Toolbox, Config Validator with example output, Cloud-Init Doctor with example output and CI/CD usage, complete workflows, banner/menu overview, graceful shutdown.

### Fixed
- Module selection crash: `_configure_modules` was unpacking `available` as 3-tuple but caller passed 2-tuple `(label, id)`. Removed unused unpacking; module IDs now derived from `cfg.modules` directly.
- EOFError in automated test pipe: `_ask`/`_ask_list`/`_ask_bool` now guard against EOF when stdin is not a TTY (returns default).
- PyInstaller icon warning on Linux: `--icon` still passed but PyInstaller emits "Ignoring icon; supported only on Windows and macOS!" — harmless, binary works.

## [1.1.0] - 2026-08-28

### Added
- Toolbox menu: external tools for VM customization:
  - Download SID Changer: fetches `sidchanger.exe` (stratus/sidchanger) to change Windows Machine SID without full Sysprep. Copy to target VM, run as Administrator, reboot.
  - Run SID Changer: executes the downloaded tool locally (Windows only, requires Administrator).
- Config Validator: validates exported configurations after generation or on existing config directories:
  - Checks `runcmd` (per-instance), `bootcmd` (every boot), `phone_home`, package update/upgrade won't re-run unexpectedly.
  - Verifies `cloudseed.json` consistency: required fields, module/file matching.
  - Windows: validates `sysprep-unattend.xml` has generalize/specialize/oobe passes; Cloudbase-Init configs have username/password.
- Cloud-Init Doctor: diagnoses cloud-init issues on a running system (requires cloud-init installed locally):
  - Full diagnosis: cloud-init status/version/stages, merged config query, systemd services (all cloud-init units), failed units, netplan/networkd, current interfaces, disk space with low-space warnings.
  - Individual checks: status, configuration, boot/services, network, disk.
  - Save diagnosis report as JSON for CI/CD integration.
- Main Menu restructuring: interactive entry point now shows: Generate Configuration | Toolbox | Config Validator | Cloud-Init Doctor | Exit.
- Graceful shutdown on Ctrl+C: signal handlers (SIGINT, SIGTERM) print "[CloudSeed] Interrupted. Shutting down gracefully..." and exit with code 130 at any prompt.
- Overwrite protection: when an output file already exists, CloudSeed asks: Overwrite / Add suffix (`_1`, `_2`…) / Skip.
- Cloud-init detection & compatibility: on Linux module selection, if cloud-init is not installed locally, CloudSeed warns that generated configs require cloud-init on the target VM, not the build machine. Some features (Validator, Doctor) need cloud-init locally.
- Windows EXE icon: custom CloudSeed icon (blue cloud with green seed) embedded in the PyInstaller binary.
- Banner on every menu: "CloudSeed v{version} / cloud-init / Cloudbase-Init VM Template Generator / {Menu Title}".

### Changed
- Output directory default now `./cloudseed-out` in current working directory (was ambiguous).
- `collect_interactive()` returns `TemplateConfig` or `int` (submenu exit code); CLI handles both.
- `generate_all()` accepts `interactive` flag to control overwrite prompts (batch mode skips prompts).
- README.md: added Toolbox, Config Validator, Cloud-Init Doctor sections; updated module tables; added overwrite protection note; added SID Changer workaround docs.
- GUIDE.md: added complete workflows for Toolbox (SID Changer), Config Validator (with example output), Cloud-Init Doctor (with example output and CI/CD usage); added banner/menu overview; added graceful shutdown note.

### Fixed
- Windows static network first-boot: `netsh` commands now emitted correctly in `firstboot` when `net_mode=static` and `os_type=windows`.
- vSphere Customization Spec XML: fixed hostname/domain/nic sections for both Linux and Windows; added proper XML escaping.
- Sample pre/post scripts: Linux shebang and Windows `@echo off` preserved; user customizations appended after samples.

## [1.0.0] - 2026-08-27

### Added
- Platform-aware hostname: let vSphere/KVM set VM hostname (default), auto-generate from prefix when cloud-init sets it.
- Conflict avoidance modules: "Let Platform Handle Network/NTP/Hostname" prevent cloud-init vs platform conflicts.
- Physical/Other platform: support bare metal, PXE, config drive, etc.
- vSphere Customization Spec export: XML for vCenter Guest Customization Specifications.
- vSphere Pre/Post Customization Scripts: sample scripts (Linux bash / Windows bat) for pre-customization (register Satellite, install agents, configure repos) and post-customization (join AD domain, compliance checks, monitoring).
- Human-readable menu: Title Case labels, proper platform/OS names.
- Default output dir: `./cloudseed-out` in current path.
- Warnings in README.txt: validation warnings written to output.
- All steps/configurations in README/GUIDE: comprehensive docs.
- Config output to cloud-init path directly: `--write-to-cloud-init-path` writes user-data to `/etc/cloud/cloud.cfg.d/99-cloudseed.cfg` (Linux, requires root).
- cloud-init version detection: `--detect-cloud-init` shows installed version and compatibility.

### Changed
- Single-file binary via PyInstaller: `python build_dist.py` produces `dist/cloudseed` (Linux) / `dist/cloudseed.exe` (Windows).
- Zero third-party dependencies: Python stdlib only (PyInstaller is build-time only).
- Config-only output: no ISO produced.

### Fixed
- Password hashing: default `$6$` SHA-512 crypt via host `crypt()` → `openssl passwd -6` → pure-stdlib fallback; `--plaintext-password` opt-out.
- Windows Sysprep: fully unattended answer file (generalize + specialize + oobe) like vSphere Guest Customization.
- cloud-init network v2: correct static DHCP/ethernets rendering.

## [0.2.1] - 2026-08-26

### Fixed
- GitHub Actions release workflow: publishes both `cloudseed-linux-x86_64.zip` and `cloudseed-windows-x86_64.zip`.
- Windows build step: fixed PowerShell build in workflow.
- upload_url sharing: fixed between build jobs via `needs.build-linux.outputs.upload_url`.

## [0.2.0] - 2026-08-25

### Added
- Interactive menu: platform → OS → modules → per-module overrides.
- Batch mode: `--json` reads saved config, generates files without prompts.
- Core modules: hostname, users, ssh, root, network, packages, locale, disk, ntp, files, bootcmd, firstboot, final, sysprep.
- Platform modules: platform_hostname, platform_network, platform_ntp.
- vSphere modules: vsphere_spec, vsphere_scripts.
- Windows support: Cloudbase-Init conf, Sysprep unattend.xml, run-sysprep.bat.
- JSON config persistence: `cloudseed.json` written every run for re-use.

## [0.1.0] - 2026-08-24

### Added
- Initial project structure.
- cloud-init YAML emitter (stdlib only).
- TemplateConfig dataclass.
- Basic CLI with argparse.