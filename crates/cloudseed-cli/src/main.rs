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
const COMMON_TIMEZONES: &[&str] = &[
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
        /// Path to the configuration file or directory
        #[arg(short, long = "config")]
        path: String,

        /// Fix issues automatically
        #[arg(long)]
        fix_it: bool,
    },

    /// Show completion script for the specified shell
    Completion {
        /// Shell to generate completion for (bash, zsh, fish)
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
}

fn run_timezone_selector(config_path: String) -> anyhow::Result<()> {
    // Load existing config
    let config = Config::from_file(&config_path)?;

    println!("Timezone Configuration");
    println!("======================");
    println!();

    // Show current timezone if set
    if let Some(tz) = &config.timezone {
        if let Some(zone) = &tz.zone {
            println!("Current timezone: {}", zone);
        } else {
            println!("Current timezone: (not set)");
        }
    } else {
        println!("Current timezone: (not set)");
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

    let extension = Path::new(config_path)
        .extension()
        .and_then(|s| s.to_str())
        .unwrap_or("");
    let content = if extension == "yaml" || extension == "yml" {
        serde_yaml::to_string(&config)?
    } else {
        toml::to_string(&config)?
    };

    fs::write(config_path, content)
        .map_err(|e| anyhow::anyhow!("failed to write {}: {}", config_path, e))?;
    Ok(format!("Configuration updated: {}", config_path))
}

/// Generate cloud-init files. Returns the text to display to the user.
fn cmd_generate(config_path: &str, output: Option<&str>, dry_run: bool) -> anyhow::Result<String> {
    let config = Config::from_file(config_path)
        .map_err(|e| anyhow::anyhow!("failed to load {}: {}", config_path, e))?;
    let provider = get_provider(&config.platform)?;
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

/// Validate a config. Returns the text to display to the user.
fn cmd_validate(path: &str, fix_it: bool) -> anyhow::Result<String> {
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
        config.fix_it();
        let extension = Path::new(path)
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("");
        let content = if extension == "yaml" || extension == "yml" {
            serde_yaml::to_string(&config)?
        } else {
            toml::to_string(&config)?
        };
        fs::write(path, content)?;
        out.push_str(&format!("\nFixed configuration written to {}", path));
    }
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
        // For simplicity, we'll just note that JSON logs are not implemented yet.
        // In a real implementation, we would use tracing_subscriber::fmt::layer().json()
        eprintln!("JSON logs requested but not implemented; falling back to plain text");
    } else if !cli.quiet {
        builder = builder.with_line_number(true);
    }

    builder.init();

    match cli.command {
        Commands::Generate {
            config,
            output,
            dry_run,
        } => report(cmd_generate(&config, output.as_deref(), dry_run)),
        Commands::Validate { path, fix_it } => report(cmd_validate(&path, fix_it)),
        Commands::Completion { shell } => match cmd_completion(&shell) {
            Ok(script) => print!("{}", script),
            Err(e) => eprintln!("{}", e),
        },
        Commands::Timezone { config } => match run_timezone_selector(config) {
            Ok(()) => println!("Timezone updated successfully."),
            Err(e) => eprintln!("Error: {}", e),
        },
        Commands::Tui { config } => {
            let mut app = tui::App::new(config);
            if let Err(e) = app.run() {
                eprintln!("Failed to run TUI: {}", e);
            }
        }
    }
}

/// Print a command result to stdout or stderr.
fn report(result: anyhow::Result<String>) {
    match result {
        Ok(text) => println!("{}", text),
        Err(e) => eprintln!("{}", e),
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
        /// Write `body` to a fresh file named after `label` and return its path.
        fn new(label: &str, body: &str) -> Self {
            static N: AtomicU32 = AtomicU32::new(0);
            let dir = std::env::temp_dir();
            let path = dir.join(format!(
                "cloudseed-{}-{}-{}.yaml",
                label,
                std::process::id(),
                N.fetch_add(1, Ordering::Relaxed)
            ));
            fs::write(&path, body).expect("write temp config");
            Self { path }
        }

        fn as_str(&self) -> &str {
            self.path.to_str().expect("utf-8 temp path")
        }
    }

    impl Drop for TempConfig {
        fn drop(&mut self) {
            let _ = fs::remove_file(&self.path);
        }
    }

    /// A minimal config that parses under both the YAML and TOML readers.
    const VALID: &str = "version: \"1.0\"\nname: demo\nplatform: local\n";

    #[test]
    fn cmd_completion_emits_a_script_for_supported_shells() {
        let script = cmd_completion("bash").expect("bash completion");
        assert!(script.contains("cloudseed"), "{}", script);
    }

    #[test]
    fn cmd_completion_rejects_unknown_shell() {
        let err = cmd_completion("tcsh").expect_err("tcsh must be rejected");
        assert!(err.to_string().contains("unsupported shell"), "{}", err);
    }

    #[test]
    fn cmd_completion_is_case_insensitive() {
        assert!(cmd_completion("ZSH").is_ok());
    }

    #[test]
    fn cmd_validate_reports_a_valid_config() {
        let cfg = TempConfig::new("valid", VALID);
        let out = cmd_validate(cfg.as_str(), false).expect("valid config");
        assert!(out.contains("valid"), "{}", out);
    }

    #[test]
    fn cmd_validate_reports_issues_without_fix_it() {
        // Parses, but validate() flags the plaintext password.
        let cfg = TempConfig::new(
            "broken",
            "version: \"1.0\"\nname: demo\nplatform: local\nvariables:\n  db_password: hunter2\n",
        );
        let out = cmd_validate(cfg.as_str(), false).expect("loadable with issues");
        assert!(out.contains("plaintext password"), "{}", out);
    }

    #[test]
    fn cmd_validate_fix_it_rewrites_the_file() {
        let cfg = TempConfig::new(
            "fixit",
            "version: \"1.0\"\nname: demo\nplatform: local\nvariables:\n  db_password: hunter2\n",
        );
        let before = fs::read_to_string(&cfg.path).unwrap();
        let out = cmd_validate(cfg.as_str(), true).expect("fixable config");
        let after = fs::read_to_string(&cfg.path).unwrap();

        assert!(out.contains("plaintext password"), "{}", out);
        assert!(out.contains("Fixed configuration"), "{}", out);
        assert_ne!(before, after, "fix_it must rewrite the file");
        // The rewritten file must still parse and no longer report the issue.
        let recheck = cmd_validate(cfg.as_str(), false).expect("rewritten config parses");
        assert!(!recheck.contains("plaintext password"), "{}", recheck);
    }

    #[test]
    fn cmd_validate_names_the_file_it_could_not_load() {
        let err = cmd_validate("/nonexistent/cloudseed.yaml", false).expect_err("missing file");
        assert!(
            err.to_string().contains("/nonexistent/cloudseed.yaml"),
            "{}",
            err
        );
    }

    #[test]
    fn cmd_generate_dry_run_lists_files_without_writing() {
        let cfg = TempConfig::new("dryrun", VALID);
        let out_dir = TempConfig::new("dryrun-out", "");
        let before = fs::read(&out_dir.path).unwrap();

        let out = cmd_generate(cfg.as_str(), Some(out_dir.as_str()), true).expect("dry run");
        assert!(out.contains("Dry run"), "{}", out);
        assert!(out.contains("user-data.yaml"), "{}", out);
        // The output directory must be untouched by a dry run.
        assert_eq!(fs::read(&out_dir.path).unwrap(), before);
    }

    #[test]
    fn cmd_generate_writes_the_file() {
        let cfg = TempConfig::new("write", VALID);
        let out_dir = TempConfig::new("write-out", "");
        fs::remove_file(&out_dir.path).expect("drop placeholder");

        let out = cmd_generate(cfg.as_str(), Some(out_dir.as_str()), false).expect("generate");
        assert!(out.contains("Generated:"), "{}", out);

        let written = out_dir.path.join("user-data.yaml");
        assert!(written.exists(), "expected {}", written.display());
        assert!(fs::read_to_string(&written)
            .unwrap()
            .contains("#cloud-config"));

        fs::remove_dir_all(&out_dir.path).ok();
    }

    #[test]
    fn cmd_generate_names_the_file_it_could_not_load() {
        let err = cmd_generate("/nonexistent/cloudseed.yaml", None, true).expect_err("missing");
        assert!(
            err.to_string().contains("/nonexistent/cloudseed.yaml"),
            "{}",
            err
        );
    }

    #[test]
    fn cmd_generate_rejects_an_unsupported_platform() {
        let cfg = TempConfig::new(
            "platform",
            "version: \"1.0\"\nname: demo\nplatform: vsphere-linux\n",
        );
        let err = cmd_generate(cfg.as_str(), None, true).expect_err("unknown platform");
        assert!(err.to_string().contains("vsphere-linux"), "{}", err);
    }

    #[test]
    fn set_timezone_writes_the_zone_and_stays_parseable() {
        let cfg = TempConfig::new("tz", VALID);
        let msg = set_timezone(cfg.as_str(), "Asia/Tokyo").expect("set timezone");
        assert!(msg.contains("Configuration updated"), "{}", msg);

        let after = fs::read_to_string(&cfg.path).unwrap();
        assert!(after.contains("Asia/Tokyo"), "{}", after);
        assert!(cmd_validate(cfg.as_str(), false).is_ok());
    }

    #[test]
    fn set_timezone_reports_a_missing_file() {
        let err = set_timezone("/nonexistent/cloudseed.yaml", "Asia/Tokyo").expect_err("missing");
        assert!(
            err.to_string().contains("/nonexistent/cloudseed.yaml"),
            "{}",
            err
        );
    }

    #[test]
    fn set_timezone_round_trips_through_toml() {
        let toml_path =
            std::env::temp_dir().join(format!("cloudseed-toml-{}.toml", std::process::id()));
        fs::write(
            &toml_path,
            "version = \"1.0\"\nname = \"demo\"\nplatform = \"local\"\n",
        )
        .expect("write toml config");

        set_timezone(toml_path.to_str().unwrap(), "Europe/Lisbon").expect("set timezone");
        let after = fs::read_to_string(&toml_path).unwrap();
        assert!(after.contains("Europe/Lisbon"), "{}", after);
        assert!(cmd_validate(toml_path.to_str().unwrap(), false).is_ok());

        fs::remove_file(&toml_path).ok();
    }
}
