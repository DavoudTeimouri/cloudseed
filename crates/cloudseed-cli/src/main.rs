use clap::{CommandFactory, Parser, Subcommand};
use clap_complete::Shell;
use cloudseed_core::{Config, TimezoneConfig};
use cloudseed_providers::get_provider;
use serde_yaml;
use std::fs;
use std::io::Write;
use std::path::Path;
use toml;
use tracing::Level;

// Common IANA timezone regions
const TIMEZONE_REGIONS: &[&str] = &[
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
}

fn run_timezone_selector(config_path: String) -> anyhow::Result<()> {
    // Load existing config
    let mut config = Config::from_file(&config_path)?;

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

    // Update config
    config.timezone = Some(TimezoneConfig {
        zone: Some(selected_timezone),
        interactive: true,
    });

    // Write back to file
    let path_ref = Path::new(&config_path);
    let extension = path_ref.extension().and_then(|s| s.to_str()).unwrap_or("");
    let content = if extension == "yaml" || extension == "yml" {
        serde_yaml::to_string(&config)?
    } else {
        toml::to_string(&config)?
    };

    fs::write(&config_path, content)?;
    println!("Configuration updated: {}", config_path);

    Ok(())
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
        } => {
            match Config::from_file(&config) {
                Ok(config) => {
                    // Get the provider for the platform.
                    match get_provider(&config.platform) {
                        Ok(provider) => match config.generate_files(&*provider) {
                            Ok(files) => {
                                if dry_run {
                                    println!("Dry run: would generate the following files:");
                                    for (path, _) in &files {
                                        println!("  {}", path);
                                    }
                                } else {
                                    let output_dir = output.unwrap_or_else(|| ".".to_string());
                                    for (path, content) in files {
                                        let full_path = Path::new(&output_dir).join(path);
                                        if let Some(parent) = full_path.parent() {
                                            let _ = fs::create_dir_all(parent);
                                        }
                                        if let Err(e) = fs::write(&full_path, content) {
                                            eprintln!(
                                                "Failed to write file {}: {}",
                                                full_path.display(),
                                                e
                                            );
                                        } else {
                                            println!("Generated: {}", full_path.display());
                                        }
                                    }
                                }
                            }
                            Err(e) => {
                                eprintln!("Failed to generate files: {}", e);
                            }
                        },
                        Err(e) => {
                            eprintln!(
                                "Failed to get provider for platform {}: {}",
                                config.platform, e
                            );
                        }
                    }
                }
                Err(e) => {
                    eprintln!("Failed to load configuration from {}: {}", config, e);
                }
            }
        }
        Commands::Validate { path, fix_it } => {
            match Config::from_file(&path) {
                Ok(mut config) => {
                    let issues = config.validate();
                    if issues.is_empty() {
                        println!("Configuration is valid.");
                    } else {
                        eprintln!("Validation failed with {} issues:", issues.len());
                        for issue in &issues {
                            eprintln!("  - {}: {}", issue.field, issue.message);
                        }
                        if fix_it {
                            println!("Applying fixes...");
                            config.fix_it();
                            // Determine the file extension to decide between YAML and TOML.
                            let path_ref = Path::new(&path);
                            let extension =
                                path_ref.extension().and_then(|s| s.to_str()).unwrap_or("");
                            let fixed_content = if extension == "yaml" || extension == "yml" {
                                match serde_yaml::to_string(&config) {
                                    Ok(s) => s,
                                    Err(e) => {
                                        eprintln!(
                                            "Failed to serialize fixed config to YAML: {}",
                                            e
                                        );
                                        return;
                                    }
                                }
                            } else {
                                // Default to TOML for other extensions or no extension.
                                match toml::to_string(&config) {
                                    Ok(s) => s,
                                    Err(e) => {
                                        eprintln!(
                                            "Failed to serialize fixed config to TOML: {}",
                                            e
                                        );
                                        return;
                                    }
                                }
                            };
                            if let Err(e) = fs::write(&path, fixed_content) {
                                eprintln!("Failed to write fixed configuration to {}: {}", path, e);
                            } else {
                                println!("Fixed configuration written to {}", path);
                            }
                        }
                    }
                }
                Err(e) => {
                    eprintln!("Failed to load configuration from {}: {}", path, e);
                }
            }
        }
        Commands::Completion { shell } => {
            let mut cmd = Cli::command();
            let shell = match shell.as_str() {
                "bash" => Shell::Bash,
                "zsh" => Shell::Zsh,
                "fish" => Shell::Fish,
                "powershell" => Shell::PowerShell,
                "elvish" => Shell::Elvish,
                _ => {
                    eprintln!("Unsupported shell: {}", shell);
                    return;
                }
            };
            clap_complete::generate(shell, &mut cmd, "cloudseed", &mut std::io::stdout());
        }
        Commands::Timezone { config } => match run_timezone_selector(config) {
            Ok(()) => println!("Timezone updated successfully."),
            Err(e) => eprintln!("Error: {}", e),
        },
    }
}
