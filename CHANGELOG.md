# Changelog

All notable changes to CloudSeed will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
