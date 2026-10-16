# CloudSeed CLI – Logic and Architecture Overview

This document describes the internal logic, data flow, and key design decisions of the CloudSeed CLI project. It is intended to be kept up‑to‑date as the software evolves.

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
CloudSeed CLI is a Rust‑based command‑line tool that generates cloud‑init configuration files (user‑data, meta‑data, etc.) from a declarative YAML/TOML configuration. It supports multiple platforms (local, AWS, Azure, GCP) via a pluggable provider system, and features an interactive TUI for novice users.

The project consists of five main crates in a Cargo workspace:
- `cloudseed-cli` – CLI parsing, command dispatch, TUI, and shared helpers.
- `cloudseed-core` – Configuration model, validation, fix‑it logic, and file generation orchestration.
- `cloudseed-providers` – Platform‑specific implementations (Local, AWS, Azure, GCP) that implement the `Provider` trait.
- `cloudseed-templates` – Handlebars‑based templates used to render cloud‑init snippets.
- `cloudseed-testutils` – Shared test utilities and fixtures.

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
|  - Validation & fix‑it            |
|  - Provider trait                 |
|  - File generation orchestrator   |
+---------------------+       +---------------------+
           |                         |
           v                         v
+---------------------+       +---------------------+
|  Providers          |       |  Templates          |
|  (Local, AWS, …)    |       |  Handlebars files   |
+---------------------+       +---------------------+
```

- The CLI parses subcommands (`generate`, `validate`, `completion`, `timezone`, `tui`) and delegates to functions in `cloudseed-core`.
- The TUI re‑uses the same core functions (`cmd_generate`, `cmd_validate`, `cmd_completion`, `set_timezone`) so CLI and TUI behave identically.
- Providers implement the `Provider` trait (`generate_files`) to return a list of `(path, content)` pairs.
- Templates are Handlebars files rendered with the `Config` as context.

---  
## Core Modules

### `cloudseed_core::Config`
The central data structure:
```rust
pub struct Config {
    pub version: String,          // config schema version
    pub name: String,             // project/deployment name
    pub platform: String,         // target platform (local, aws, azure, gcp)
    pub modules: Vec<String>,     // optional list of enabled modules
    pub variables: HashMap<String, String>, // custom template variables
    pub timezone: Option<TimezoneConfig>,
}
```
`TimezoneConfig` holds an optional IANA zone (`zone: Option<String>`) and an `interactive: bool` flag.

### Validation (`Config::validate`)
Returns a `Vec<ValidationIssue>` where each issue contains:
- `field`: the name of the field that failed validation
- `message`: human‑readable description

Validation rules:
- `version`, `name`, `platform` must be non‑empty.
- No further semantic rules; providers may add their own checks via the `generate_files` step.

### Fix‑It (`Config::fix_it`)
Currently only detects and hashes plaintext passwords:
- Any variable key containing “pass” or “password” whose value does **not** start with `$` is assumed to be a plaintext password.
- The value is replaced with its SHA‑256 hash prefixed with `$sha256$`.

### File Generation (`Config::generate_files`)
1. Obtain a `Box<dyn Provider>` via `cloudseed_providers::get_provider(&config.platform)`.
2. Call `provider.generate(&config)` → returns `Vec<(String, String)>`.
   - The `String` key is the relative file path (e.g., `user-data.yaml`).
   - The `String` value is the rendered file content.

### Provider Trait (`cloudseed_providers::Provider`)
```rust
pub trait Provider: Send + Sync {
    fn generate(&self, config: &Config) -> anyhow::Result<Vec<(String, String)>>;
}
```
Implementations:
- `LocalProvider` – renders templates using the local filesystem (no network calls).
- `AwsProvider`, `AzureProvider`, `GcpProvider` – stubbed or placeholder; they return the same templates as Local for now (the abstraction is ready for real API calls).

### Template Engine (`cloudseed-templates`)
- Uses the [Handlebars](https://handlebarsjs.com/) crate.
- Templates are stored as `*.hbs` files under `cloudseed-templates/templates/`.
- Rendering context is the `Config` serialized to a `Handlebars`‐compatible JSON map (via `serde_json::to_value`).
- Supported helpers: `json`, `default`, `uppercase`, `lowercase`, `trim`, `replace`, etc.

---  
## CLI Entry Point and Command Flow

`src/main.rs`:
1. `Cli::parse()` builds the argument parser (via `clap`).
2. Match on `Cli::command`:
   - `Generate { config, output, dry_run }` → `cmd_generate(&config, output.as_deref(), dry_run)`
   - `Validate { path, fix_it }` → `cmd_validate(&path, fix_it)`
   - `Completion { shell }` → `cmd_completion(&shell)`
   - `Timezone { config }` → `run_timezone_selector(config)`
   - `Tui { config }` → `App::new(config).run()`
3. `report(result)` prints `Ok` to stdout or `Err` to stderr.

### Shared Command Functions
All live in `main.rs` (above `main`):
- `cmd_generate` – loads config, gets provider, calls `generate_files`, formats dry‑run or writes files.
- `cmd_validate` – loads config, calls `validate()`, optionally calls `fix_it()` and rewrites the file.
- `cmd_completion` – maps shell string to `clap_complete::Shell` and invokes `clap_complete::generate`.
- `set_timezone` – loads config, updates `config.timezone`, writes back using the same YAML/TOML detection logic as the config loader.

These functions are **exactly** the same ones the TUI calls via `App::submit_form()`, guaranteeing identical behavior between CLI and TUI.

### Error Handling
Each function returns `anyhow::Result<String>` where the `Ok` string is the user‑facing output (to be printed to stdout) and the `Err` contains an error message (printed to stderr). The `report` helper centralises this printing.

---  
## Configuration Handling
- Supported formats: YAML (`.yaml`, `.yml`) and TOML (`.toml`).
- Loader (`Config::from_file`) tries YAML first; if parsing fails it falls back to TOML.
- Writer chooses format based on file extension (`.yaml`/`.yml` → YAML, else → TOML).
- The TUI always writes using the same detection logic, guaranteeing round‑trip compatibility.

### Default Config Path
When the TUI is launched without `--config`, it defaults to `./cloudseed.yaml` (relative to the current working directory). All path fields in the forms are pre‑filled with this value, making the TUI usable out‑of‑the‑box.

---  
## Terminal User Interface (TUI)

Built with `ratatui` 0.26 and `crossterm` 0.28.

### Screens
- `Screen::MenuBar` – top row, lists `[Generate, Validate, Completion, Timezone]`.
- `Screen::CommandList` – left panel, vertical list of actions for the selected menu (usually a single entry like “Run generate”).
- `Screen::Form` – right panel, shows input fields for the selected command.
- `Screen::Timezone` – two‑column picker (region | city) plus a free‑form IANA entry accessible via the trailing “Custom…” region.
- `Screen::Output` – modal‑like pane that shows the result of the last command (stdout/stderr) with a green/red border.

### Navigation
- **MenuBar**: `←`/`→` to move focus, `Enter` opens the selected menu.
- **CommandList**: `↑`/`↓` to move highlight, `Enter` runs the command, `Esc` returns to MenuBar.
- **Form**: `↑`/`↓` to move between fields, typing edits the focused field, `Enter` submits (after validation), `Esc` returns to MenuBar.
- **Timezone**: `↑`/`↓` moves within the focused column, `←`/`→` switches between region and city columns, `Enter` confirms the selected zone and writes it to the config file, `Esc` returns to the CommandList.
- **Output**: any key returns to the previous screen; `q` from the MenuBar quits the application.

### Validation on Submit
When the user presses Enter in a form:
1. `validate_form(panel, &fields)` is called.
2. If it returns `Some(err)`, the error is placed under the offending field (`field.error = Some(err)`) and submission is aborted.
3. Otherwise the appropriate `cmd_*` function is invoked.
4. The resulting `Ok(text)` or `Err(e)` is stored in `app.output` (with a flag for error) and the screen switches to `Screen::Output`.
5. The output pane shows a header like `Generate: cloudseed.yaml` followed by the command’s stdout or stderr.

### Toasts
Short-lived messages appear in the bottom‑right corner:
- `ToastKind::Success` (green) for successful operations.
- `ToastKind::Error` (red) for failures.
They automatically fade after 4 seconds or can be dismissed with any key press.

### Rendering Loop
- Fixed tick rate of 200 ms (`Duration::from_millis(200)`).
- On each tick, `app.expire_toast()` removes stale toasts.
- The UI is drawn via `ratatui::Terminal::draw`.

### Testability
All UI logic is unit‑testable:
- `App::paint(&mut app, width, height)` renders the app into a `TestBackend` buffer and returns the plain text.
- Tests assert on the presence of specific strings (titles, field labels, values, error messages, status hints, etc.).
- This approach avoids depending on a real terminal while still exercising the exact same draw functions used at runtime.

---  
## Validation and Fix‑It
As described above, validation is field‑based and returns a collection of issues. The fix‑it step is limited to password hashing but is extensible—new rules can be added to `Config::fix_it` and will be automatically applied when the user runs `cloudseed validate --fix-it <path>` or submits the Validate form in the TUI.

---  
## Testing Strategy
### Unit Tests
- Located in `src/main.rs` and `src/tui.rs` under `#[cfg(test)] mod tests`.
- Use standard library `assert!` and `expect()`/`expect_err()`.
- No external test crate is required; this keeps the test suite lightweight and fast.
- Tests cover:
  - Form editing (insert, backspace).
  - Validation error clearing on edit.
  - Completion shell acceptance/rejection (case‑insensitive).
  - Config loading (missing file, empty path).
  - Generate dry‑run vs actual write.
  - `set_timezone` read/write error paths.
  - TUI rendering (menu bar, forms, timezone picker, output pane, validation errors).
  - Focus navigation and screen transitions.
- Run with `cargo test --workspace`.

### Integration / Smoke Tests
- The CI workflow (`ci.yml`) builds the release binary for both `ubuntu-latest` and `windows-latest` and runs:
  - `cargo fmt --check`
  - `cargo test --workspace`
  - `cargo clippy --workspace -- -D warnings`
  - `cargo build --release --package cloudseed-cli`
  - `./target/release/cloudseed-cli --help` (OS‑specific executable name)
- This ensures the binary works on both major platforms.

### Manual Testing
- TUI can be launched with `cloudseed tui --config <path>` (or without argument to use `./cloudseed.yaml`).
- End‑to‑end scenarios: create a minimal config, run `generate --dry-run`, inspect output, run `generate` to write files, inspect written files, run `validate --fix-it`, verify that plaintext passwords are hashed.

---  
## Future Work
- **Provider Implementations**: Flesh out `AwsProvider`, `AzureProvider`, `GcpProvider` to call real APIs (e.g., AWS SSM for parameter store, Azure Key Vault, GCP Secret Manager) when fetching secrets or rendering platform‑specific cloud‑init snippets.
- **Template Library**: Expand the set of Handlebars templates (networking, users, ssh, mounts, etc.) and document them.
- **Interactive Wizard**: Enhance the TUI to guide users through a multi‑step wizard (e.g., select platform → fill base config → review → generate) rather than separate forms.
- **Plugin System**: Allow third‑party crates to register additional providers or template helpers via a feature‑flag‑based discovery mechanism.
- **Output Formats**: Support generating cloud‑init in multiple formats (YAML only currently) and possibly multi‑part (user‑data + vendor‑data).
- **Self‑Updating**: Add a `cloudseed self-update` command that downloads the latest release from GitHub and replaces the binary.
- **Completion Shells**: Add support for `powershell` and `elvish` (already present in the code but not yet advertised in help).
- **Documentation**: Expand this file with sequence diagrams, example configurations, and a FAQ.

---  
*This document should be edited whenever a significant change to the logic, data flow, or public interface is made. Keep it concise but complete enough for a new contributor to understand how the pieces fit together.*  