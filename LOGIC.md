# CloudSeed CLI – Logic and Architecture Overview

This document describes the internal logic, data flow, and key design decisions of the CloudSeed CLI project. It is kept up-to-date as the software evolves.

## Table of Contents
- [Project Overview](#project-overview)
- [High‑Level Architecture](#high-level-architecture)
- [Core Modules](#core-modules)
- [CLI Entry Point and Command Flow](#cli-entry-point-and-command-flow)
- [Configuration Handling](#configuration-handling)
- [Provider Abstraction](#provider-abstraction)
- [Template Rendering](#template-rendering)
- [Terminal User Interface (TUI)](#terminal-user-interface-tui)
- [Validation and Fix‑It](#validation-and-fix-it)
- [Testing Strategy](#testing-strategy)
- [Future Work](#future-work)

---  
## Project Overview
CloudSeed CLI is a Rust command-line tool that generates **cloud-init** (Linux) and **Cloudbase-Init + Sysprep** (Windows) configuration files for VM template provisioning on **VMware vSphere**, **KVM**, and **Physical/Other** platforms.

The project is a Cargo workspace with four crates:
- `cloudseed-cli` – CLI parsing, command dispatch, TUI, and the shared command functions.
- `cloudseed-core` – Configuration model, validation, fix-it logic, and the `Provider` trait.
- `cloudseed-providers` – Platform/OS-specific file generation.
- `cloudseed-templates` – Rendering of the generated documents.

**Config-only**: CloudSeed emits configuration files, not an ISO. You apply the config directly (guestinfo/vApp on vSphere, `--cloud-init` on KVM, or drop-in on the golden image). See [GUIDE.md](GUIDE.md).

---  
## High‑Level Architecture
```
+---------------------+       +---------------------+
|  CLI (cloudseed-cli)|       |  TUI (same crate)   |
|  - Argument parsing |       |  - Ratatui UI       |
|  - Command dispatch |       |  - Key handling     |
+----------+----------+       +----------+----------+
           |                         |
           v                         v
+---------------------+       +---------------------+
|  Core (cloudseed-core)            |
|  - Config struct                  |
|  - Validation & fix-it            |
|  - Provider trait                 |
+---------------------+       +---------------------+
           |                         |
           v                         v
+---------------------+       +---------------------+
|  Providers          |       |  Templates          |
|  (vsphere/kvm/      |       |  cloud-config,      |
|   physical)         |       |  Sysprep, Conf      |
+---------------------+       +---------------------+
```

- The CLI parses subcommands and delegates to functions in `main.rs`.
- The TUI re-uses the same command functions (`cmd_generate`, `cmd_validate`, `cmd_completion`, `set_timezone`), so CLI and TUI cannot drift.
- The provider decides *which* files to write for a platform/OS pair.
- The templates crate decides *what* each file contains.

---  
## Core Modules

### `cloudseed_core::Config`
The central data structure. It models the fields documented in `README.md`:

| Group | Fields |
|-------|--------|
| Identity | `version`, `name`, `platform`, `os_type`, `modules`, `variables` |
| Hostname | `hostname`, `hostname_prefix`, `use_platform_hostname` |
| User | `username`, `password`, `plaintext_password`, `password_rounds`, `sudo`, `lock_password`, `ssh_pwauth`, `disable_root`, `ssh_keys` |
| Network | `net_mode`, `net_interface`, `net_address`, `net_netmask`, `net_gateway`, `net_dns`, `net_search`, `net_domain`, `let_platform_handle_network` |
| Packages | `package_upgrade`, `packages` |
| Locale | `timezone`, `locale`, `keyboard_layout` |
| Disk | `grow_device`, `grow_partition` |
| NTP | `ntp_servers`, `let_platform_handle_ntp` |
| Files & commands | `write_files`, `bootcmd`, `firstboot`, `final_message` |
| Sysprep (Windows) | `sysprep`, `sysprep_organization`, `sysprep_owner`, `sysprep_computer_prefix`, `sysprep_timezone`, `sysprep_locale`, `sysprep_product_key` |
| vSphere | `export_vsphere_spec`, `vsphere_spec_name`, `vsphere_pre_script`, `vsphere_post_script`, `use_sample_scripts` |

Every optional field carries a `serde` default, so a minimal config (`version`, `name`, `platform`) still loads and generates a complete cloud-config.

`timezone` accepts either form:
```yaml
timezone: "Europe/Berlin"
# or
timezone:
  zone: Europe/Berlin
  interactive: true
```

### Module resolution (`Config::module_enabled`)
An empty `modules` list means every module is enabled. When the list is non-empty, only the listed modules are emitted.

A `platform_*` module and its cloud-init counterpart are mutually exclusive:
- `use_platform_hostname: true` → the `hostname` module is **not** emitted.
- `let_platform_handle_network: true` → the `network` module is **not** emitted.
- `let_platform_handle_ntp: true` → the `ntp` module is **not** emitted.

`template_best_practices` is the one opt-in module: it produces an extra
artifact (the golden-image cleanup script), so it stays off unless it is listed
explicitly.

This keeps cloud-init from fighting the hypervisor over the same concern.

### Validation (`Config::validate`)
Returns `Vec<ValidationIssue>`, each with a `field` and a `message`. Checks:
- `version`, `name`, `platform` are present.
- `platform` is one of `vsphere`, `kvm`, `physical`.
- `os_type` is one of `linux`, `windows`.
- Every entry in `modules` is a known module.
- A password that is neither empty, a crypt hash, nor explicitly plaintext is reported.
- `lock_password` without any `ssh_keys` is reported (locks the operator out).
- Static networking without an address or a gateway is reported.
- A Windows target without `sysprep` is reported (cloned VMs would share a SID).

### Fix-It (`Config::fix_it`)
Hashes a plaintext password with **SHA-512 crypt** (`$6$`) using a random salt, via the `sha-crypt` crate. The rounds come from `password_rounds` (default 5000). A password that is already a crypt hash is left alone, and `plaintext_password: true` is never touched.

The result is a real hash the target system can verify — not a placeholder.

### Provider Trait (`cloudseed_core::Provider`)
```rust
pub trait Provider {
    fn generate(&self, config: &Config) -> anyhow::Result<Vec<(String, String)>>;
}
```
`generate_files` on `Config` is a thin wrapper over it.

---  
## Configuration Handling
- Supported formats: YAML (`.yaml`, `.yml`) and TOML (`.toml`).
- **The file extension decides the format.** There is no format guessing: a TOML file named `.yaml` is a parse error, and a malformed file reports which format it tried. An unknown extension is rejected.
- `Config::serialize(path)` writes back in the format matching the path's extension, so a round-trip preserves the file type.

---  
## Provider Abstraction

`cloudseed-providers` contains one provider, `PlatformProvider`, parameterised by platform and OS:

```rust
PlatformProvider::new("vsphere", "linux")
```

`get_provider(platform, os_type)` validates both against `cloudseed_core::PLATFORMS` and `cloudseed_core::OS_TYPES` and returns the provider. An unknown value is an error that names the accepted values.

### Output layout
Files are written under `out/<platform>-<os>/`:

| File | Linux | Windows |
|------|:-----:|:-------:|
| `user-data` | ✅ | ✅ |
| `meta-data` | ✅ | ❌ |
| `cloudbase-init.conf` | ❌ | ✅ |
| `cloudbase-init-unattend.conf` | ❌ | ✅ |
| `sysprep-unattend.xml` | ❌ | ✅ (when `sysprep`) |
| `run-sysprep.bat` | ❌ | ✅ (when `sysprep`) |
| `vsphere-customization-spec.xml` | ✅ (when `export_vsphere_spec`) | ✅ (when `export_vsphere_spec`) |
| `vsphere-pre-script.sh`, `vsphere-post-script.sh` | ✅ (vSphere) | ✅ (vSphere) |
| `cloudseed.yaml` | ✅ | ✅ |
| `README.txt` | ✅ | ✅ |

`README.txt` lists the apply steps for the target and repeats any validation warnings.

---  
## Template Rendering

`cloudseed-templates` builds each document:

- **`user_data`** — the Linux cloud-config. It is built as typed values and serialized with `serde_yaml`, so quoting, block scalars and escaping are handled by the serializer rather than by hand. Only the enabled modules appear.
- **`meta_data`** — instance identity (`instance-id`, `local-hostname`).
- **`cloudbase_init`** / **`cloudbase_init_unattend`** — Cloudbase-Init service configuration.
- **`sysprep_unattend`** — the Windows unattend answer file with the generalize, specialize and oobeSystem passes.
- **`run_sysprep`** — the batch script that runs Sysprep generalize.
- **`vsphere_customization_spec`** — the vSphere Guest Customization Specification XML.

Static networking is emitted as cloud-init network config **version 2**. The dotted netmask is converted to a prefix length (`255.255.255.0` → `/24`) because v2 uses `address/prefix`.

---  
## CLI Entry Point and Command Flow

`main.rs`:
1. `Cli::parse()` builds the argument parser (via `clap`).
2. Logging is initialised from `--verbose` / `--quiet` / `--json-logs`.
3. The subcommand is dispatched to a function returning `anyhow::Result<String>`.
4. `report(result)` prints the `Ok` text to stdout or the `Err` to stderr and **returns the process exit code** — `0` on success, `1` on failure. CI can therefore branch on the result.

### Commands
| Command | Function | Notes |
|---------|----------|-------|
| `generate` | `cmd_generate` | `--dry-run` lists the files without writing |
| `validate` | `cmd_validate` | Accepts a file or a directory of configs |
| `completion` | `cmd_completion` | Case-insensitive; bash, zsh, fish, powershell, elvish |
| `timezone` | `run_timezone_selector` | Interactive region → city picker |
| `tui` | `tui::App::new(config).run()` | `--config` defaults to `./cloudseed.yaml` |
| `detect-cloud-init` | `cmd_detect_cloud_init` | Runs `cloud-init --version` and reports support |
| `write-to-cloud-init-path` | `cmd_write_to_cloud_init_path` | Writes to `/etc/cloud/cloud.cfg.d/99-cloudseed.cfg` |

### Shared Command Functions
All live in `main.rs`:
- `cmd_generate` – loads the config, gets a provider, generates the files, then either lists them (dry run) or writes them.
- `cmd_validate` – loads the config, validates it, and optionally applies `fix_it` and writes the file back.
- `cmd_completion` – maps a shell name to `clap_complete::Shell` and emits the script.
- `set_timezone` – loads the config, sets `timezone`, writes it back in the original format.

These are exactly the functions the TUI calls, so both surfaces behave identically.

### Error Handling
Each function returns `anyhow::Result<String>`. The `Ok` string is the user-facing output; the `Err` carries the message. `report` centralises printing and the exit code.

---  
## Terminal User Interface (TUI)

Built with `ratatui` 0.26 and `crossterm` 0.28.

### Screens
- `Screen::MenuBar` – top row, lists `[Generate, Validate, Completion, Timezone]`.
- `Screen::CommandList` – left panel, the actions for the selected menu.
- `Screen::Form` – right panel, the input fields for the selected command.
- `Screen::Timezone` – two-column region/city picker with a trailing `Custom…` entry.
- `Screen::Output` – pane showing the result of the last command.

### Navigation
- **MenuBar**: `←`/`→` to move, `Enter` opens, `q`/`Q`/`Esc` quits.
- **CommandList**: `↑`/`↓` to move, `Enter` runs, `Esc` returns.
- **Form**: `↑`/`↓` to move between fields, typing edits, `Enter` submits, `Esc` returns.
- **Timezone**: `↑`/`↓` within a column, `←`/`→` between columns, `Enter` commits, `Esc` returns.
- **`Ctrl+C` quits from any screen.**

### Validation on Submit
`validate_form` checks the form before the command runs: a config path must exist, and a shell must be one of the supported ones. A failure is shown under the offending field and the command does not run.

### Toasts
`ToastKind::Success` (green) and `ToastKind::Error` (red) appear in the bottom-right corner and expire after 4 seconds.

### Testability
`paint(app, width, height)` renders the app into a `ratatui::backend::TestBackend` buffer and returns the plain text, so the render path is asserted in tests without a real terminal.

---  
## Testing Strategy
### Unit Tests
- `crates/cloudseed-cli/src/main.rs` – 21 tests over the command functions: dry run leaves the output directory untouched, the documented output layout is produced, an unknown platform is rejected, a missing file names the path, `--fix-it` replaces a plaintext password with a `$6$` hash and leaves an existing hash alone, a directory of configs is validated, every supported shell is accepted, a field whose module is disabled is reported, the `template_best_practices` cleanup script is emitted only when the module is requested, and `report` returns the right exit code.
- `crates/cloudseed-cli/src/tui.rs` – 18 tests over the UI: form editing, validation errors, the timezone picker, focus navigation, and 8 render tests through `TestBackend`.
- **A documentation guard**: every `yaml` block in `README.md` and `GUIDE.md` must parse as a valid config and pass validation. A broken or stale example fails the build.
- Run with `cargo test --workspace`.

### CI
`.github/workflows/ci.yml` runs on `ubuntu-latest` and `windows-latest`:
- `cargo test --workspace`
- `cargo fmt --check`
- `cargo clippy --workspace -- -D warnings`
- `cargo build --release --package cloudseed-cli`
- `./target/release/cloudseed-cli --help`

---  
## Future Work
- **Provider API calls**: AWS/Azure/GCP secret fetching. The platforms differ in identity, not in generated file shape, so one provider family covers the current scope.
- **Template library**: per-module templates beyond the current single cloud-config.
- **TUI wizard**: a multi-step flow (platform → OS → modules → review → generate) instead of separate forms.
- **Self-update**: `cloudseed self-update` to pull the latest release.
- **Interactive timezone data**: the picker uses a curated list of 60 common zones; the full IANA database would be better.

---  
*This document should be edited whenever a significant change to the logic, data flow, or public interface is made. Keep it concise but complete enough for a new contributor to understand how the pieces fit together.*
