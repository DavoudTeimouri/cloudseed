# CloudSeed v2.2.0 — Fix / Improve / Feature Plan

Source: code review of `main` @ `44778c1` (v2.1.8) + product roadmap.
All findings verified by running the real release binary.

**Status: all items below are implemented, tested and committed.**

| # | Item | File | Issue | Fix | Status |
|---|------|------|-------|-----|--------|
| 1 | Exit code always 0 | `crates/cloudseed-cli/src/main.rs` | `report()` prints the error to stderr but the process still exits 0. CI cannot detect failure. | `report` returns `i32`; `main` exits with it | Done |
| 2 | `fix_it` destroys the password | `crates/cloudseed-core/src/lib.rs` | Writes the literal `"$6$rounds=5000$examplesalt$"` — a placeholder, not a hash of the password. The real password is lost and the target VM gets an unusable credential. | Real SHA-512 crypt via `sha-crypt` (random salt) | Done |
| 3 | Documented platforms rejected | `crates/cloudseed-providers/src/lib.rs` | README/GUIDE document `vsphere`/`kvm`/`physical`; `get_provider` accepted only `local`/`aws`/`azure`/`gcp`. Every documented config failed. | Accept the documented platform names | Done |
| 4 | Format guessed, not declared | `crates/cloudseed-core/src/lib.rs` | YAML-then-TOML fallback: a TOML file named `.yaml` parses as YAML and silently misbehaves; a malformed YAML file reports a TOML error. | Extension decides format; unknown extension is an error | Done |
| 5 | Config fields silently dropped | `crates/cloudseed-core/src/lib.rs` | `Config` models 6 fields; README documents ~60. Serde ignores the rest, so a README-shaped config generates output that ignores almost everything — with no warning. | Model the documented fields | Done |
| 6 | `variables` never rendered | `crates/cloudseed-providers/src/lib.rs` | Variables are inserted into the template context but the template never references them, so they are invisible in the output. | Render variables into the cloud-config | Done |
| 7 | Fake SSH key shipped | `crates/cloudseed-templates/src/lib.rs` | Template hardcodes `ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...` — a truncated, invalid key that ends up in every generated VM. | Render real keys from config | Done |
| 8 | Hardcoded `ubuntu` user | `crates/cloudseed-templates/src/lib.rs` | User name, groups, sudo and lock flags are fixed in the template; config is ignored. | Render from config | Done |
| 9 | `modules` ignored | `crates/cloudseed-core/src/lib.rs` | `modules` is parsed and then never read by any provider. | Honour modules | Done |
| 10 | Output layout does not match docs | `crates/cloudseed-cli/src/main.rs` | Docs promise `out/<platform>-<os>/{user-data,meta-data,cloudseed.yaml,README.txt}`; the code writes a single `user-data.yaml` into `--output`. | Emit the documented layout | Done |
| 11 | `--json-logs` is a no-op | `crates/cloudseed-cli/src/main.rs` | Flag prints "not implemented" and falls back. | Real JSON logging layer | Done |
| 12 | `--detect-cloud-init` missing | `crates/cloudseed-cli/src/main.rs` | Documented in GUIDE §10, does not exist. | Implement | Done |
| 13 | `--write-to-cloud-init-path` missing | `crates/cloudseed-cli/src/main.rs` | Documented in GUIDE §11, does not exist. | Implement (root-gated) | Done |
| 14 | `validate` rejects directories | `crates/cloudseed-cli/src/main.rs` | Help says "file or directory"; a directory errors with "Is a directory". | Accept a directory, validate each config in it | Done |
| 15 | Stub providers | `crates/cloudseed-providers/src/lib.rs` | `AwsProvider`/`AzureProvider`/`GcpProvider` all call `LocalProvider.generate`. Dead code that looks real. | One real provider per platform family | Done |
| 16 | Empty `cloudseed-testutils` | `crates/cloudseed-testutils/src/lib.rs` | Crate is one blank line. | Remove from the workspace | Done |
| 17 | Dead `render_template` | `crates/cloudseed-templates/src/lib.rs` | Never called. | Remove | Done |
| 18 | `load_template` type bound | `crates/cloudseed-templates/src/lib.rs` | `S: Into<String>` forces name and template to be the same type. | Two independent bounds | Done |
| 19 | Password detection duplicated | `crates/cloudseed-core/src/lib.rs` | Same rule written twice, and it matches any key containing "pass" (catches `compass`). | One helper, tighter rule | Done |
| 20 | Serialization duplicated | `crates/cloudseed-cli/src/main.rs` | YAML-vs-TOML branch written twice. | `core::serialize_config` | Done |
| 21 | Dead feature flags | `crates/cloudseed-core/Cargo.toml` | `aws`/`azure`/`gcp` features on core are never referenced. | Remove from core | Done |
| 22 | TUI shell list out of sync | `crates/cloudseed-cli/src/tui.rs` | TUI offers only bash/zsh/fish; `cmd_completion` also supports powershell/elvish. | Share one list | Done |
| 23 | TUI quit only from menu bar | `crates/cloudseed-cli/src/tui.rs` | `q` quits only on the menu bar; from a form you must Esc back twice. | `Ctrl+C` quits anywhere | Done |
| 24 | `Config` not `Clone` | `crates/cloudseed-core/src/lib.rs` | Blocks passing configs around by value. | Derive `Clone`, `PartialEq` | Done |

### Found while implementing

| # | Item | Status |
|---|------|--------|
| 25 | `template_best_practices` was documented but not implemented | Done — emits a golden-image cleanup script, opt-in |
| 26 | A field whose module is disabled was silently dropped | Done — the validator names the field and the module |
| 27 | The README's main config example did not parse (a `###` heading sat inside the YAML block) and was missing `version`/`name` | Done — plus a test that guards every YAML block in README.md and GUIDE.md |
| 28 | The timezone had a `UTC` default, so an unset timezone looked "set" | Done — no default, the image default is left alone |
| 29 | The cloud-config degenerated to `{}` when no cloud module was enabled | Done — the header is emitted alone |
| 30 | `--version` was documented but the command had no version | Done — a test now checks the documented flags and subcommands exist |
| 31 | `--quiet` only removed the log line numbers | Done — it now drops the log level to warnings and errors |
| 32 | Two workflows both created a release for the same tag, one publishing raw binaries | Done — `release.yml` is the only publisher; `ci.yml` keeps only test and build |
| 33 | A pre-release tag produced an empty release body and a stable release | Done — the tag suffix marks the release as a pre-release, the changelog is looked up by the plain version, and `make_latest` is false for a pre-release |
| 34 | The GitHub API rejects a pre-release that is also marked as the latest release, so the RC was never created | Done — the release is now posted through the API with an explicit payload; `scripts/simulate-release.sh` dry-runs it |
| 35 | The changelog lookup used a regex passed through `awk -v`, and gawk processes escape sequences there, so the pattern became a character class that never matched. It worked under mawk locally and failed on the runners. | Done — the lookup is a literal substring match, and the simulation now runs the step under every awk available |

---

## Explicitly not doing

- SaaS control plane, GUI, ISO builder, native VM provisioning, accounts/RBAC — out of scope
  for a single-file, on-prem, config-only CLI.
- Real AWS/Azure/GCP API calls — the platforms differ in identity, not in generated
  file shape; one provider family covers it.
- `self-update` — distribution polish, not product value.
- TUI multi-step wizard — the CLI is the automation interface; revisit on demand.
