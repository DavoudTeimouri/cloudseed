# Changelog

All notable changes to CloudSeed will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] - 2026-10-22

### Fixed
- **Exit code on failure**: every command now exits `1` when it fails. Previously `generate`/`validate`/`completion` printed the error but exited `0`, so CI could not detect a failure.
- **`--fix-it` no longer destroys the password**: it now writes a real SHA-512 crypt hash (`$6$...`) with a random salt, using the `password_rounds` from the config. It previously wrote the literal placeholder `$6$rounds=5000$examplesalt$`, which was not a hash of anything and locked the operator out of the target.
- **Documented platforms now work**: `vsphere`, `kvm` and `physical` are accepted. The provider previously only accepted `local`, `aws`, `azure` and `gcp`, so every configuration in the documentation failed with "Unsupported platform".
- **Config format is decided by the file extension**, not guessed by trying YAML and falling back to TOML. A malformed file now reports the format it tried, and an unknown extension is rejected instead of being silently parsed as TOML.
- **Config fields are no longer silently dropped**: `Config` now models the fields the documentation describes. Serde used to ignore all of them, so a documented config generated output that ignored almost everything.
- **The generated cloud-config uses the real configuration**: user name, SSH keys, groups, sudo, packages, timezone, locale, network and files are all rendered. The template previously hardcoded the user `ubuntu` and a truncated, invalid SSH key (`ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...`) that ended up in every generated VM.
- **The `modules` list is honoured**: it was parsed and then never read by any provider.
- **Output layout matches the documentation**: files are written to `out/<platform>-<os>/` with `user-data`, `meta-data`, `cloudseed.yaml` and `README.txt` (plus the Cloudbase-Init and Sysprep artifacts on Windows). Previously a single `user-data.yaml` was written into the output directory.
- **Static networking is emitted** as cloud-init network config version 2, converting the dotted netmask to a prefix length.
- **`--json-logs` actually emits JSON** instead of printing "not implemented" and falling back to plain text.
- **`validate` accepts a directory** of configurations, as its help text claimed.
- **TUI and CLI agree on the supported shells**: the TUI offered only bash, zsh and fish while the CLI also supported powershell and elvish.
- **`Ctrl+C` quits the TUI** from any screen. Previously only `q` on the menu bar worked, so leaving a form took several Esc presses.
- **A field whose module is disabled is reported**: setting `packages` while the `packages` module is off used to be silently dropped. The validator now names the field and the module.
- **An unset timezone is no longer forced to `UTC`**: the timezone has no default now, so the generated cloud-config only carries a `timezone` key when one was configured, and the image default is left alone.
- **The documented config examples are valid again**: the README's main example was missing `version` and `name` and carried a plaintext password, and a `###` heading had been left inside the YAML code block, which broke the example.
- **`--version` works**: the flag was documented but the command had no version, so it was rejected as an unknown argument.
- **`--quiet` actually quiets the output**: it only removed the log line numbers. It now drops the log level to warnings and errors.

### Added
- **`cloudseed detect-cloud-init`**: reports the local cloud-init version and whether CloudSeed supports it.
- **`cloudseed write-to-cloud-init-path`**: writes the generated config to `/etc/cloud/cloud.cfg.d/99-cloudseed.cfg` on a running Linux host.
- **Windows artifacts**: `cloudbase-init.conf`, `cloudbase-init-unattend.conf`, `sysprep-unattend.xml` and `run-sysprep.bat` are now generated, and the cloud-config is written as `user-data` for Cloudbase-Init to consume.
- **vSphere Guest Customization Specification export** (`vsphere-customization-spec.xml`) and the pre/post customization scripts.
- **Validation rules** for unknown platforms, unknown modules, unknown OS types, static networking without an address or gateway, a locked password without an SSH key, and a Windows target without Sysprep.
- **`network_domain`**, `sysprep_*` and `vsphere_*` configuration fields, all of which were previously documented but ignored.
- **`template_best_practices` is now implemented**: it writes a `template-cleanup.sh` / `template-cleanup.bat` golden-image cleanup script and explains in `README.txt` how to seal the image. It is opt-in, because it adds a file.

### Changed
- **Password hashing uses `sha-crypt`**, adding one dependency. The `handlebars` dependency was dropped: the cloud-config is now built as typed values and serialized with `serde_yaml`, which handles quoting and block scalars correctly.
- **A test guards the documentation**: every `yaml` block in `README.md` and `GUIDE.md` must parse as a valid config and pass validation, so the examples cannot drift away from the code again.
- **The `cloudseed-testutils` crate was removed**; it was empty.
- **The `aws`/`azure`/`gcp` feature flags were removed** from `cloudseed-core`; they were never referenced. The provider surface is now a single `PlatformProvider` parameterised by platform and OS.
- **Shared command functions** (`cmd_generate`, `cmd_validate`, `cmd_completion`, `set_timezone`) are used by both the CLI and the TUI, so the two surfaces cannot drift.

### Removed
- **`cloudseed-core` feature flags** `aws`, `azure`, `gcp` (dead).
- **Dead `render_template` helper** in `cloudseed-templates`.

## [2.1.8] - 2026-10-08

### Added
- **Terminal UI**: `cloudseed tui` runs an interactive ratatui/crossterm interface with a menu bar, command list, and action panel
- **Hierarchical timezone picker**: two-column region→city selection in the TUI, with a trailing `Custom…` entry for free-form IANA zones
- **TUI `--config` flag**: `cloudseed tui --config <path>` selects the file the Timezone menu edits and pre-fills the Generate/Validate forms; defaults to `./cloudseed.yaml` when omitted
- **Unit tests**: 11 TUI tests (form editing, validation, timezone selection, focus) and 14 command-function tests (generate/validate/completion/timezone, including dry-run and error paths)

### Changed
- **Shared command functions**: `cmd_generate`, `cmd_validate`, `cmd_completion`, and `set_timezone` are extracted from `main()` and shared by the CLI and TUI, so both serialize config identically
- **Form validation**: config paths must exist and shells must be `bash`/`zsh`/`fish` before a command runs; errors show inline
- **Error messages**: config load and write failures name the file involved

### Fixed
- **Shell completion is case-insensitive**: `completion ZSH` now works

## [2.1.7] - 2026-10-07

### Added
- **Interactive timezone selector**: Hierarchical region→zone selection (10 IANA regions, 60 common timezones)
- **TimezoneConfig**: New config section with `zone` (IANA identifier) and `interactive` flag
- **CLI command**: `cloudseed timezone --config <file>` for interactive timezone configuration
- **Template integration**: `timezone` field rendered in cloud-init user-data

### Changed
- Config supports `timezone` section in both YAML and TOML formats

## [2.1.6] - 2026-10-06

### Added
- **Rust rewrite**: Complete migration from Python to Rust with modular workspace (cloudseed-cli, cloudseed-core, cloudseed-providers, cloudseed-templates, cloudseed-testutils)
- **Cross-platform binaries**: Native Linux and Windows executables built via Cargo
- **Shell completion**: Bash, Zsh, Fish, PowerShell, and Elvish completion scripts

### Changed
- **CLI structure**: Subcommand-based interface (`generate`, `validate`, `completion`) replacing interactive menu
- **Configuration**: YAML/TOML config files instead of JSON-only
- **Provider abstraction**: Pluggable provider system (local, AWS, Azure, GCP) via feature flags
- **Template engine**: Handlebars-based rendering replacing string templates
- **Validation**: Config validator with `--fix-it` auto-correction for plaintext passwords
- **Distribution**: Single-file binaries via Cargo (no PyInstaller needed)

### Removed
- **Python implementation**: Full removal of `cloudseed/` Python package, `cli.py`, `generate.py`, `model.py`, `validator.py`, `logging_config.py`
- **PyInstaller build**: Replaced with native Cargo release builds
- **Interactive menu**: Batch-only CLI for automation/CI/CD

### Testing
- All Rust crates compile (`cargo check` passes)
- CLI commands verified: generate, validate, completion (bash/zsh/fish/powershell/elvish)
- Configuration validation and fix-it mode tested
- Dry-run and output directory generation verified

## [2.1.5] - 2026-09-12

### Fixed
- **Windows timezone/locale configuration**: `locale` module now enabled for Windows (was Linux-only). Windows gets hierarchical timezone selector (92 zones, 14 regions) + Windows locale list + keyboard layout, matching Linux UX.

### Testing
- All 41 tests pass.

## [2.1.4] - 2026-09-12

### Fixed
- **Banner rendering**: Replaced double-line box characters (═║╔╗╚╝) with single-line (─│┌┐└┘┤├) to fix vertical line alignment issues on all terminals.
- **Esc key references removed**: `[Esc]` removed from footer hints since it doesn't work in line-input mode; only `[0]` for back navigation.

### Testing
- All 41 tests pass.

## [2.1.3] - 2026-09-12

### Added
- **Windows hierarchical timezone selection**: Windows now uses the same region→timezone pattern as Linux. Full 92 Windows time zones organized into 14 regions (Europe, Africa, Asia, Australia, Pacific, Americas, etc.) with pagination (20 per page), type-ahead filter, exact match, and numeric selection.

### Changed
- `WINDOWS_TIMEZONES` expanded from 22 to 92 zones (complete Microsoft list).
- Windows timezone selector now matches Linux UX: region list → zone sub-menu with pagination.

### Testing
- All 41 tests pass.

## [2.1.2] - 2026-09-12

### Fixed
- **Full IANA timezone list in static fallback**: `LINUX_TIMEZONES` now contains all 484 zones from zoneinfo, so minimal systems (Python 3.8, no tzdata package) get complete hierarchical region→zone selection with pagination, not truncated 6-zone lists.

### Testing
- All 41 tests pass.

## [2.1.1] - 2026-09-12

### Added
- **Full paginated IANA timezone list**: Each region now shows complete sub-menu of all IANA zones (~480 zones total) with pagination (20 per page). Navigation via `n`/`p` for next/prev page, type-ahead filter, exact match, or numeric selection.

### Changed
- Timezone selector: hierarchical region→zone flow preserved; zone step now displays full region list with page navigation instead of truncated list.

### Fixed
- Timezone sub-menu no longer shows limited subset; full IANA database available per region.

### Testing
- All 41 tests pass.

## [2.1.0] - 2026-09-11

### Changed
- **Borderless banner**: Removed box-drawing borders from `print_banner()` and all menus; clean aligned text only.
- **Numbered module selection**: Reverted to v2.0.4-style line-input selector — toggle by number + Enter to confirm, supports multi-digit module numbers (10+). Empty input (Enter) confirms; `0`/`Esc` returns to previous menu.
- **Complete IANA TZDB timezone list**: Linux timezone selector now uses `zoneinfo.available_timezones()` (~480 zones) with hierarchical region→zone selection. Static fallback for minimal systems retained.
- **Footer**: Removed `[Space] toggle` (Space key not supported in line-input mode); shows `[#] toggle [c] config [a] all [n] none [Enter] OK [0/Esc] back`.

### Fixed
- **`[Esc] Back` navigation**: ESC sequence now handled in line-input mode; returns `BACK` sentinel from module selector.
- Removed misleading `Platform: Vsphere  OS: Linux` from main banner; banner shows only `CloudSeed` name and module count.
- Module selector no longer crashes on EOF (non-TTY stdin) — returns `BACK`.

### Testing
- All 41 tests pass.
- Regression tests: numbered toggle + Enter, multi-digit modules, conflict indicator, EOF handling (tests/test_ui.py).
- Timezone selector tests: hierarchical IANA selection, non-TTY fallback (tests/test_timezone_selector.py).

## [2.1.0] - 2026-09-11

### Changed
- Main banner now names **CloudSeed** explicitly and shows only selected-module count.
- Module selection frame labels platform and OS as target values, not current host values.
- Module selector supports Space to toggle highlighted module; numbered input still toggles directly.

### Fixed
- Removed misleading `Platform: Vsphere  OS: Linux` status from main banner.
- Space key now performs a module toggle instead of being treated as filter text.

### Testing
- 38 tests pass.

## [2.0.4] - 2026-09-10

### Added
- Portable line-input selector (`_ask_from_list`): replaces termios/tty raw input with line-based selection that works in all terminals (SSH, Docker, non-TTY, piped stdin).
- Linux timezone: hierarchical region→zone selection from full IANA database (~600 zones) with static fallback for minimal systems.
- Windows timezone: flat list from WINDOWS_TIMEZONES (no custom entry).
- Added Asia/Tehran to static LINUX_TIMEZONES fallback list.
- New test file: tests/test_timezone_selector.py (11 tests, all passing).

### Changed
- Module selection: line-based selector with numbered options and Space toggle.
- Timezone: full IANA database with region/zone hierarchy.
