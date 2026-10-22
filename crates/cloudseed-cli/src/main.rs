use clap::{CommandFactory, Parser, Subcommand};
use clap_complete::Shell;
use cloudseed_core::{Config, TimezoneConfig};
use cloudseed_providers::get_provider;
use std::fs;
use std::io::Write;
use std::path::Path;
use tracing::Level;
mod tui;

// Common IANA timezone regions
pub(crate) const TIMEZONE_REGIONS: &[&str] = &[
    "Africa",
    "America",
    "Antarctica",
    "Arctic",
    "Asia",
    "Atlantic",
    "Australia",
    "Europe",
    "Indian",
    "Pacific",
];

// Simplified IANA timezone database (common timezones)
pub(crate) const COMMON_TIMEZONES: &[&str] = &[
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Anchorage",
    "America/Phoenix",
    "America/Toronto",
    "America/Vancouver",
    "America/Mexico_City",
    "America/Sao_Paulo",
    "America/Buenos_Aires",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Rome",
    "Europe/Madrid",
    "Europe/Amsterdam",
    "Europe/Stockholm",
    "Europe/Vienna",
    "Europe/Warsaw",
    "Europe/Moscow",
    "Europe/Istanbul",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Asia/Hong_Kong",
    "Asia/Singapore",
    "Asia/Dubai",
    "Asia/Tel_Aviv",
    "Asia/Tehran",
    "Asia/Kolkata",
    "Asia/Bangkok",
    "Asia/Seoul",
    "Australia/Sydney",
    "Australia/Melbourne",
    "Australia/Perth",
    "Australia/Brisbane",
    "Australia/Adelaide",
    "Pacific/Auckland",
    "Pacific/Honolulu",
    "Pacific/Fiji",
    "Atlantic/Reykjavik",
    "Africa/Cairo",
    "Africa/Johannesburg",
    "Africa/Lagos",
    "Indian/Mauritius",
];

/// Shells the completion command accepts.
pub(crate) const SHELLS: &[&str] = &["bash", "zsh", "fish", "powershell", "elvish"];

/// The cloud-init version path where a generated config is written on a
/// running Linux host.
const CLOUD_INIT_PATH: &str = "/etc/cloud/cloud.cfg.d/99-cloudseed.cfg";

/// The oldest cloud-init release CloudSeed generates configuration for.
const MIN_CLOUD_INIT: (u32, u32) = (22, 1);

#[derive(Parser)]
#[command(name = "cloudseed")]
#[command(about = "A tool for generating cloud-init configurations", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,

    /// Increase logging verbosity
    #[arg(short, long, action = clap::ArgAction::Count)]
    verbose: u8,

    /// Decrease logging verbosity
    #[arg(short, long)]
    quiet: bool,

    /// Output logs in JSON format
    #[arg(long)]
    json_logs: bool,
}

#[derive(Subcommand)]
enum Commands {
    /// Generate cloud-init configuration
    Generate {
        /// Path to the configuration file
        #[arg(short, long)]
        config: String,

        /// Output directory
        #[arg(short, long)]
        output: Option<String>,

        /// Dry run: show what would be generated without writing files
        #[arg(long)]
        dry_run: bool,
    },

    /// Validate configuration
    Validate {
        /// Path to the configuration file or a directory of configurations
        #[arg(short, long = "config")]
        path: String,

        /// Fix issues automatically
        #[arg(long)]
        fix_it: bool,
    },

    /// Show completion script for the specified shell
    Completion {
        /// Shell to generate completion for (bash, zsh, fish, powershell, elvish)
        shell: String,
    },

    /// Interactively configure timezone
    Timezone {
        /// Path to the configuration file to update
        #[arg(short, long)]
        config: String,
    },

    /// Launch the terminal user interface (TUI)
    Tui {
        /// Config file the TUI edits (used by the Timezone menu and to pre-fill forms)
        #[arg(short, long)]
        config: Option<String>,
    },

    /// Report the local cloud-init version and its compatibility
    DetectCloudInit,

    /// Write the generated config to the local cloud-init config path (requires root)
    WriteToCloudInitPath {
        /// Path to the configuration file
        #[arg(short, long)]
        config: String,

        /// Write to this path instead of the default cloud-init path
        #[arg(long, default_value = CLOUD_INIT_PATH)]
        path: String,
    },
}

fn run_timezone_selector(config_path: String) -> anyhow::Result<()> {
    // Load existing config
    let config = Config::from_file(&config_path)?;

    println!("Timezone Configuration");
    println!("======================");
    println!();

    // Show current timezone if set
    match config.resolved_timezone() {
        Some(zone) => println!("Current timezone: {}", zone),
        None => println!("Current timezone: (not set)"),
    }
    println!();

    // Step 1: Select region
    println!("Step 1: Select region");
    println!("---------------------");
    for (i, region) in TIMEZONE_REGIONS.iter().enumerate() {
        println!("  {}. {}", i + 1, region);
    }
    println!("  {}. Custom IANA timezone", TIMEZONE_REGIONS.len() + 1);
    println!();

    let region_idx = loop {
        print!("Select region [1-{}]: ", TIMEZONE_REGIONS.len() + 1);
        std::io::stdout().flush()?;
        let mut input = String::new();
        std::io::stdin().read_line(&mut input)?;
        let input = input.trim();

        if let Ok(idx) = input.parse::<usize>() {
            if idx >= 1 && idx <= TIMEZONE_REGIONS.len() + 1 {
                break idx - 1;
            }
        }
        println!(
            "Invalid selection. Please enter a number between 1 and {}.",
            TIMEZONE_REGIONS.len() + 1
        );
    };

    let selected_timezone = if region_idx == TIMEZONE_REGIONS.len() {
        // Custom IANA timezone
        print!("Enter IANA timezone (e.g., America/New_York): ");
        std::io::stdout().flush()?;
        let mut input = String::new();
        std::io::stdin().read_line(&mut input)?;
        input.trim().to_string()
    } else {
        // Step 2: Select timezone within region
        let region = TIMEZONE_REGIONS[region_idx];
        let region_timezones: Vec<&str> = COMMON_TIMEZONES
            .iter()
            .filter(|tz| tz.starts_with(&format!("{}/", region)))
            .copied()
            .collect();

        if region_timezones.is_empty() {
            println!(
                "No common timezones found for region {}. Using UTC.",
                region
            );
            "UTC".to_string()
        } else {
            println!();
            println!("Step 2: Select timezone in {}", region);
            println!("{}", "-".repeat(20 + region.len()));
            for (i, tz) in region_timezones.iter().enumerate() {
                println!("  {}. {}", i + 1, tz);
            }
            println!("  {}. Other...", region_timezones.len() + 1);
            println!();

            let tz_idx = loop {
                print!("Select timezone [1-{}]: ", region_timezones.len() + 1);
                std::io::stdout().flush()?;
                let mut input = String::new();
                std::io::stdin().read_line(&mut input)?;
                let input = input.trim();

                if let Ok(idx) = input.parse::<usize>() {
                    if idx >= 1 && idx <= region_timezones.len() + 1 {
                        break idx - 1;
                    }
                }
                println!(
                    "Invalid selection. Please enter a number between 1 and {}.",
                    region_timezones.len() + 1
                );
            };

            if tz_idx == region_timezones.len() {
                // Other
                print!("Enter IANA timezone: ");
                std::io::stdout().flush()?;
                let mut input = String::new();
                std::io::stdin().read_line(&mut input)?;
                input.trim().to_string()
            } else {
                region_timezones[tz_idx].to_string()
            }
        }
    };

    // Confirm
    println!();
    println!("Selected timezone: {}", selected_timezone);
    print!("Confirm? [Y/n]: ");
    std::io::stdout().flush()?;
    let mut input = String::new();
    std::io::stdin().read_line(&mut input)?;
    if !input.trim().is_empty() && !input.trim().eq_ignore_ascii_case("y") {
        println!("Cancelled.");
        return Ok(());
    }

    println!("{}", set_timezone(&config_path, &selected_timezone)?);

    Ok(())
}

/// Set `zone` as the config's timezone and write the file back. Shared by the
/// CLI prompt and the TUI picker so both serialize identically.
fn set_timezone(config_path: &str, zone: &str) -> anyhow::Result<String> {
    let mut config = Config::from_file(config_path)
        .map_err(|e| anyhow::anyhow!("failed to load {}: {}", config_path, e))?;
    config.timezone = Some(TimezoneConfig {
        zone: Some(zone.to_string()),
        interactive: true,
    });

    let content = config.serialize(config_path)?;
    fs::write(config_path, content)
        .map_err(|e| anyhow::anyhow!("failed to write {}: {}", config_path, e))?;
    Ok(format!("Configuration updated: {}", config_path))
}

/// Generate cloud-init files. Returns the text to display to the user.
fn cmd_generate(config_path: &str, output: Option<&str>, dry_run: bool) -> anyhow::Result<String> {
    let config = Config::from_file(config_path)
        .map_err(|e| anyhow::anyhow!("failed to load {}: {}", config_path, e))?;
    let provider = get_provider(&config.platform, &config.os_type)?;
    let files = config
        .generate_files(&*provider)
        .map_err(|e| anyhow::anyhow!("failed to generate files: {}", e))?;

    if dry_run {
        let mut out = format!("Dry run: would generate {} file(s):", files.len());
        for (path, _) in &files {
            out.push_str(&format!("\n  {}", path));
        }
        return Ok(out);
    }

    let output_dir = output.unwrap_or(".");
    let mut out = String::new();
    let mut failures = 0;
    for (path, content) in files {
        let full_path = Path::new(output_dir).join(path);
        if let Some(parent) = full_path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        match fs::write(&full_path, content) {
            Ok(()) => out.push_str(&format!("Generated: {}\n", full_path.display())),
            Err(e) => {
                failures += 1;
                out.push_str(&format!("Failed to write {}: {}\n", full_path.display(), e));
            }
        }
    }
    if failures > 0 {
        return Err(anyhow::anyhow!("{} file(s) failed to write", failures));
    }
    Ok(out.trim_end().to_string())
}

/// Validate a config, or every config in a directory. Returns the text to
/// display to the user.
fn cmd_validate(path: &str, fix_it: bool) -> anyhow::Result<String> {
    let target = Path::new(path);
    if target.is_dir() {
        return cmd_validate_dir(target, fix_it);
    }

    let mut config =
        Config::from_file(path).map_err(|e| anyhow::anyhow!("failed to load {}: {}", path, e))?;
    let issues = config.validate();
    if issues.is_empty() {
        return Ok("Configuration is valid.".to_string());
    }

    let mut out = format!("Validation failed with {} issue(s):", issues.len());
    for issue in &issues {
        out.push_str(&format!("\n  - {}: {}", issue.field, issue.message));
    }

    if fix_it {
        config.fix_it()?;
        let content = config.serialize(path)?;
        fs::write(path, content).map_err(|e| anyhow::anyhow!("failed to write {}: {}", path, e))?;
        out.push_str(&format!("\nFixed configuration written to {}", path));
    }
    Ok(out)
}

/// Validate every config found in `dir`.
fn cmd_validate_dir(dir: &Path, fix_it: bool) -> anyhow::Result<String> {
    let mut configs: Vec<std::path::PathBuf> = Vec::new();
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();
        let is_config = matches!(
            path.extension().and_then(|s| s.to_str()),
            Some("yaml") | Some("yml") | Some("toml")
        );
        if path.is_file() && is_config {
            configs.push(path);
        }
    }
    configs.sort();

    if configs.is_empty() {
        return Ok(format!("No configuration files found in {}", dir.display()));
    }

    let mut out = String::new();
    let mut failed = 0;
    for config_path in &configs {
        let path_str = config_path.to_string_lossy().to_string();
        match cmd_validate(&path_str, fix_it) {
            Ok(text) => {
                out.push_str(&format!("{}: {}\n", path_str, text));
                if !text.starts_with("Configuration is valid") {
                    failed += 1;
                }
            }
            Err(e) => {
                failed += 1;
                out.push_str(&format!("{}: {}\n", path_str, e));
            }
        }
    }
    out.push_str(&format!(
        "\nChecked {} config(s), {} with issues.",
        configs.len(),
        failed
    ));
    Ok(out)
}

/// Emit a shell completion script. Returns the text to display to the user.
fn cmd_completion(shell: &str) -> anyhow::Result<String> {
    let shell = match shell.to_ascii_lowercase().as_str() {
        "bash" => Shell::Bash,
        "zsh" => Shell::Zsh,
        "fish" => Shell::Fish,
        "powershell" => Shell::PowerShell,
        "elvish" => Shell::Elvish,
        other => return Err(anyhow::anyhow!("unsupported shell: {}", other)),
    };

    let mut buffer = Vec::new();
    clap_complete::generate(shell, &mut Cli::command(), "cloudseed", &mut buffer);
    Ok(String::from_utf8_lossy(&buffer).into_owned())
}

/// Report the local cloud-init version and whether CloudSeed supports it.
fn cmd_detect_cloud_init() -> anyhow::Result<String> {
    let output = std::process::Command::new("cloud-init")
        .arg("--version")
        .output();

    let raw = match output {
        Ok(out) => String::from_utf8_lossy(&out.stdout).trim().to_string(),
        Err(e) => {
            return Err(anyhow::anyhow!(
                "cloud-init is not installed or not on PATH: {}",
                e
            ))
        }
    };

    let version = raw
        .split_whitespace()
        .nth(1)
        .ok_or_else(|| anyhow::anyhow!("could not parse cloud-init version from '{}'", raw))?;
    let mut parts = version.split('.');
    let major: u32 = parts
        .next()
        .and_then(|p| p.parse().ok())
        .ok_or_else(|| anyhow::anyhow!("could not parse cloud-init version from '{}'", raw))?;
    let minor: u32 = parts.next().and_then(|p| p.parse().ok()).unwrap_or(0);

    let mut out = String::new();
    out.push_str("=========================\n");
    out.push_str("CLOUD-INIT DETECTION\n");
    out.push_str("=========================\n");
    out.push_str(&format!("Cloud-init: {}\n", version));
    out.push_str(&format!("Status: {}\n", support_status(major, minor)));
    out.push_str(&format!(
        "Generated config requires cloud-init >= {}.{}\n",
        MIN_CLOUD_INIT.0, MIN_CLOUD_INIT.1
    ));
    Ok(out)
}

/// A human-readable support verdict for a cloud-init version.
fn support_status(major: u32, _minor: u32) -> &'static str {
    if major < 21 {
        "not supported (too old for the modern config schema)"
    } else if major == 21 {
        "limited support (some modules unavailable)"
    } else if major == 22 {
        "supported"
    } else if major <= 24 {
        "fully supported (all modules)"
    } else {
        "supported (newer than the tested range; verify the modules you use)"
    }
}

/// Write the generated cloud-config to a cloud-init config path.
fn cmd_write_to_cloud_init_path(config_path: &str, path: &str) -> anyhow::Result<String> {
    let config = Config::from_file(config_path)
        .map_err(|e| anyhow::anyhow!("failed to load {}: {}", config_path, e))?;
    if config.os_type != "linux" {
        return Err(anyhow::anyhow!(
            "cloud-init config paths only apply to linux targets; this config targets {}",
            config.os_type
        ));
    }

    let provider = get_provider(&config.platform, &config.os_type)?;
    let files = config.generate_files(&*provider)?;
    let user_data = files
        .iter()
        .find(|(name, _)| name.ends_with("user-data"))
        .map(|(_, content)| content.clone())
        .ok_or_else(|| anyhow::anyhow!("no user-data was generated for this config"))?;

    if let Some(parent) = Path::new(path).parent() {
        fs::create_dir_all(parent)
            .map_err(|e| anyhow::anyhow!("failed to create {}: {}", parent.display(), e))?;
    }
    fs::write(path, user_data).map_err(|e| anyhow::anyhow!("failed to write {}: {}", path, e))?;
    Ok(format!(
        "Wrote {}\nRun: sudo cloud-init clean --reboot",
        path
    ))
}

fn main() {
    let cli = Cli::parse();

    // Initialize logging
    let verbosity = match cli.verbose {
        0 => Level::INFO,
        1 => Level::DEBUG,
        2 => Level::TRACE,
        _ => Level::TRACE,
    };

    let mut builder = tracing_subscriber::fmt::fmt()
        .with_max_level(verbosity)
        .with_target(false);

    if cli.json_logs {
        tracing_subscriber::fmt()
            .json()
            .with_max_level(verbosity)
            .init();
    } else {
        if !cli.quiet {
            builder = builder.with_line_number(true);
        }
        builder.init();
    }

    let result = match cli.command {
        Commands::Generate {
            config,
            output,
            dry_run,
        } => cmd_generate(&config, output.as_deref(), dry_run),
        Commands::Validate { path, fix_it } => cmd_validate(&path, fix_it),
        Commands::Completion { shell } => cmd_completion(&shell).map(|script| {
            print!("{}", script);
            String::new()
        }),
        Commands::Timezone { config } => run_timezone_selector(config).map(|_| String::new()),
        Commands::Tui { config } => {
            let mut app = tui::App::new(config);
            match app.run() {
                Ok(()) => Ok(String::new()),
                Err(e) => Err(anyhow::anyhow!("failed to run TUI: {}", e)),
            }
        }
        Commands::DetectCloudInit => cmd_detect_cloud_init(),
        Commands::WriteToCloudInitPath { config, path } => {
            cmd_write_to_cloud_init_path(&config, &path)
        }
    };

    std::process::exit(report(result));
}

/// Print a command result to stdout or stderr. Returns the process exit code.
fn report(result: anyhow::Result<String>) -> i32 {
    match result {
        Ok(text) => {
            if !text.is_empty() {
                println!("{}", text);
            }
            0
        }
        Err(e) => {
            eprintln!("{}", e);
            1
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU32, Ordering};

    /// A config file path unique to this test, removed on drop.
    struct TempConfig {
        path: std::path::PathBuf,
    }

    impl TempConfig {
        /// Write `body` to a fresh file named after `label` and return it.
        fn new(label: &str, body: &str) -> Self {
            static N: AtomicU32 = AtomicU32::new(0);
            let dir = std::env::temp_dir();
            let path = dir.join(format!(
                "cloudseed-{}-{}-{}.yaml",
                label,
                std::process::id(),
                N.fetch_add(1, Ordering::Relaxed)
            ));
            fs::write(&path, body).expect("write config");
            Self { path }
        }

        fn path_str(&self) -> String {
            self.path.to_string_lossy().to_string()
        }
    }

    impl Drop for TempConfig {
        fn drop(&mut self) {
            let _ = fs::remove_file(&self.path);
        }
    }

    /// A minimal valid config.
    fn minimal_config() -> &'static str {
        "version: \"1.0\"\nname: test\nplatform: kvm\n"
    }

    #[test]
    fn generate_dry_run_lists_files_without_writing() {
        let cfg = TempConfig::new("dry", minimal_config());
        let out_dir = std::env::temp_dir().join(format!("cs-out-{}", std::process::id()));
        let out = cmd_generate(&cfg.path_str(), Some(out_dir.to_str().unwrap()), true).unwrap();
        assert!(out.contains("Dry run"), "got: {}", out);
        assert!(out.contains("user-data"), "got: {}", out);
        assert!(!out_dir.exists(), "dry run must not create the output dir");
    }

    #[test]
    fn generate_writes_the_documented_layout() {
        let cfg = TempConfig::new("layout", minimal_config());
        let out_dir = std::env::temp_dir().join(format!("cs-layout-{}", std::process::id()));
        let _ = fs::remove_dir_all(&out_dir);
        cmd_generate(&cfg.path_str(), Some(out_dir.to_str().unwrap()), false).unwrap();
        let sub = out_dir.join("kvm-linux");
        assert!(sub.join("user-data").is_file(), "user-data missing");
        assert!(sub.join("meta-data").is_file(), "meta-data missing");
        assert!(
            sub.join("cloudseed.yaml").is_file(),
            "cloudseed.yaml missing"
        );
        assert!(sub.join("README.txt").is_file(), "README.txt missing");
        let _ = fs::remove_dir_all(&out_dir);
    }

    #[test]
    fn generate_rejects_an_unknown_platform() {
        let cfg = TempConfig::new("plat", "version: \"1.0\"\nname: t\nplatform: local\n");
        let err = cmd_generate(&cfg.path_str(), None, true).unwrap_err();
        assert!(
            err.to_string().contains("Unsupported platform"),
            "got: {}",
            err
        );
    }

    #[test]
    fn generate_rejects_a_missing_file() {
        let err = cmd_generate("/nonexistent/cloudseed.yaml", None, true).unwrap_err();
        assert!(err.to_string().contains("failed to load"), "got: {}", err);
    }

    #[test]
    fn validate_accepts_a_minimal_config() {
        let cfg = TempConfig::new("valid", minimal_config());
        assert_eq!(
            cmd_validate(&cfg.path_str(), false).unwrap(),
            "Configuration is valid."
        );
    }

    #[test]
    fn validate_reports_a_plaintext_password() {
        let cfg = TempConfig::new(
            "plain",
            "version: \"1.0\"\nname: t\nplatform: kvm\npassword: hunter2\n",
        );
        let out = cmd_validate(&cfg.path_str(), false).unwrap();
        assert!(out.contains("plaintext"), "got: {}", out);
    }

    #[test]
    fn fix_it_hashes_the_password() {
        let cfg = TempConfig::new(
            "fix",
            "version: \"1.0\"\nname: t\nplatform: kvm\npassword: hunter2\n",
        );
        cmd_validate(&cfg.path_str(), true).unwrap();
        let after = fs::read_to_string(&cfg.path).unwrap();
        assert!(!after.contains("hunter2"), "password survived unhashed");
        assert!(
            after.contains("$6$"),
            "no sha512 crypt hash written: {}",
            after
        );
    }

    #[test]
    fn validate_does_not_warn_about_an_unset_timezone() {
        // The timezone has no default, so an unset timezone is not "set".
        let cfg = TempConfig::new(
            "notz",
            "version: \"1.0\"\nname: t\nplatform: kvm\nmodules:\n  - hostname\n",
        );
        let out = cmd_validate(&cfg.path_str(), false).unwrap();
        assert!(
            !out.contains("timezone"),
            "unset timezone was reported: {}",
            out
        );
    }

    /// Every `yaml` code block in the documentation must be a valid config.
    ///
    /// This keeps the docs and the code from drifting apart: a config example
    /// that no longer parses, or that omits a required field, fails the build.
    #[test]
    fn documentation_examples_are_valid_configs() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .and_then(|p| p.parent())
            .expect("workspace root");

        for doc in ["README.md", "GUIDE.md"] {
            let path = root.join(doc);
            let text = fs::read_to_string(&path)
                .unwrap_or_else(|e| panic!("read {}: {}", path.display(), e));

            for (i, block) in yaml_blocks(&text).iter().enumerate() {
                let config: Config = serde_yaml::from_str(block).unwrap_or_else(|e| {
                    panic!("{} yaml block {} is not a valid config: {}", doc, i + 1, e)
                });
                // The examples must also be internally consistent.
                let issues = config.validate();
                assert!(
                    issues.is_empty(),
                    "{} yaml block {} has validation issues: {:?}",
                    doc,
                    i + 1,
                    issues
                );
            }
        }
    }

    /// The bodies of every ```yaml fenced block in `text`.
    fn yaml_blocks(text: &str) -> Vec<String> {
        let mut blocks = Vec::new();
        let mut current: Option<String> = None;
        for line in text.lines() {
            if current.is_none() {
                if line.trim() == "```yaml" {
                    current = Some(String::new());
                }
            } else if line.trim() == "```" {
                blocks.push(current.take().expect("open block"));
            } else if let Some(block) = current.as_mut() {
                block.push_str(line);
                block.push('\n');
            }
        }
        blocks
    }

    #[test]
    fn validate_reports_a_field_whose_module_is_disabled() {
        let cfg = TempConfig::new(
            "ignored",
            "version: \"1.0\"\nname: t\nplatform: kvm\nmodules:\n  - hostname\npackages:\n  - nginx\n",
        );
        let out = cmd_validate(&cfg.path_str(), false).unwrap();
        assert!(
            out.contains("'packages' is set but the 'packages' module is disabled"),
            "got: {}",
            out
        );
    }

    #[test]
    fn template_best_practices_emits_a_cleanup_script() {
        let cfg = TempConfig::new(
            "tbp",
            "version: \"1.0\"\nname: t\nplatform: kvm\nmodules:\n  - template_best_practices\n",
        );
        let out_dir = std::env::temp_dir().join(format!("cs-tbp-{}", std::process::id()));
        let _ = fs::remove_dir_all(&out_dir);
        cmd_generate(&cfg.path_str(), Some(out_dir.to_str().unwrap()), false).unwrap();
        let sub = out_dir.join("kvm-linux");
        assert!(
            sub.join("template-cleanup.sh").is_file(),
            "cleanup script missing"
        );
        let readme = fs::read_to_string(sub.join("README.txt")).unwrap();
        assert!(
            readme.contains("template-cleanup.sh"),
            "README does not mention the cleanup script: {}",
            readme
        );
        let _ = fs::remove_dir_all(&out_dir);
    }

    #[test]
    fn template_best_practices_is_absent_by_default() {
        let cfg = TempConfig::new("notbp", minimal_config());
        let out_dir = std::env::temp_dir().join(format!("cs-notbp-{}", std::process::id()));
        let _ = fs::remove_dir_all(&out_dir);
        cmd_generate(&cfg.path_str(), Some(out_dir.to_str().unwrap()), false).unwrap();
        assert!(
            !out_dir.join("kvm-linux/template-cleanup.sh").exists(),
            "cleanup script written without the module"
        );
        let _ = fs::remove_dir_all(&out_dir);
    }

    #[test]
    fn fix_it_leaves_an_already_hashed_password_alone() {
        let hash = "$6$rounds=5000$abcdefgh$0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcd";
        let cfg = TempConfig::new(
            "hashed",
            &format!(
                "version: \"1.0\"\nname: t\nplatform: kvm\npassword: \"{}\"\n",
                hash
            ),
        );
        cmd_validate(&cfg.path_str(), true).unwrap();
        let after = fs::read_to_string(&cfg.path).unwrap();
        assert!(after.contains(hash), "hash was rewritten: {}", after);
    }

    #[test]
    fn validate_accepts_a_directory() {
        let dir = std::env::temp_dir().join(format!("cs-dir-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        fs::write(dir.join("a.yaml"), minimal_config()).unwrap();
        fs::write(dir.join("notes.txt"), "ignored").unwrap();
        let out = cmd_validate(dir.to_str().unwrap(), false).unwrap();
        assert!(out.contains("a.yaml"), "got: {}", out);
        assert!(out.contains("Checked 1 config(s)"), "got: {}", out);
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn completion_accepts_every_supported_shell() {
        for shell in ["bash", "zsh", "fish", "powershell", "elvish", "BASH"] {
            assert!(
                cmd_completion(shell).is_ok(),
                "shell {} was rejected",
                shell
            );
        }
    }

    #[test]
    fn completion_rejects_an_unknown_shell() {
        let err = cmd_completion("tcsh").unwrap_err();
        assert!(
            err.to_string().contains("unsupported shell"),
            "got: {}",
            err
        );
    }

    #[test]
    fn set_timezone_writes_the_zone() {
        let cfg = TempConfig::new("tz", minimal_config());
        cmd_generate(&cfg.path_str(), None, true).unwrap();
        set_timezone(&cfg.path_str(), "Europe/Rome").unwrap();
        let after = fs::read_to_string(&cfg.path).unwrap();
        assert!(after.contains("Europe/Rome"), "got: {}", after);
        assert!(after.contains("interactive: true"), "got: {}", after);
    }

    #[test]
    fn set_timezone_reports_a_missing_file() {
        let err = set_timezone("/nonexistent/cloudseed.yaml", "UTC").unwrap_err();
        assert!(err.to_string().contains("failed to load"), "got: {}", err);
    }

    #[test]
    fn report_returns_a_nonzero_exit_code_on_failure() {
        assert_eq!(report(Ok("fine".to_string())), 0);
        assert_eq!(report(Err(anyhow::anyhow!("boom"))), 1);
    }
}
