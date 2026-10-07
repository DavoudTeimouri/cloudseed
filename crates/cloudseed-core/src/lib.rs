use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::Path;

/// Represents a CloudSeed configuration.
#[derive(Debug, Deserialize, Serialize)]
pub struct Config {
    /// The version of the configuration format.
    pub version: String,
    /// The name of the project or deployment.
    pub name: String,
    /// The target platform (e.g., aws, azure, gcp, local).
    pub platform: String,
    /// Optional: a list of modules to include.
    #[serde(default)]
    pub modules: Vec<String>,
    /// Optional: custom variables for templating.
    #[serde(default)]
    pub variables: HashMap<String, String>,
    /// Optional: timezone configuration.
    #[serde(default)]
    pub timezone: Option<TimezoneConfig>,
}

/// Timezone configuration for the VM.
#[derive(Debug, Deserialize, Serialize, Default, Clone)]
pub struct TimezoneConfig {
    /// The IANA timezone identifier (e.g., "America/New_York", "Europe/London").
    pub zone: Option<String>,
    /// Whether the timezone was set interactively.
    #[serde(default)]
    pub interactive: bool,
}

impl Config {
    /// Load a configuration from a file.
    pub fn from_file<P: AsRef<Path>>(path: P) -> anyhow::Result<Self> {
        let content = fs::read_to_string(path)?;
        // Try to parse as YAML first, then TOML.
        if let Ok(config) = serde_yaml::from_str(&content) {
            Ok(config)
        } else {
            let config = toml::from_str(&content)?;
            Ok(config)
        }
    }

    /// Generate a list of files to create based on the configuration and a provider.
    /// Returns a vector of (file_path, content).
    pub fn generate_files(&self, provider: &dyn Provider) -> anyhow::Result<Vec<(String, String)>> {
        provider.generate(self)
    }

    /// Validate the configuration and return a list of issues.
    pub fn validate(&self) -> Vec<ValidationIssue> {
        let mut issues = Vec::new();

        if self.version.is_empty() {
            issues.push(ValidationIssue {
                field: "version".to_string(),
                message: "version is required".to_string(),
            });
        }

        if self.name.is_empty() {
            issues.push(ValidationIssue {
                field: "name".to_string(),
                message: "name is required".to_string(),
            });
        }

        if self.platform.is_empty() {
            issues.push(ValidationIssue {
                field: "platform".to_string(),
                message: "platform is required".to_string(),
            });
        }

        // Check for plaintext passwords in variables (example)
        for (key, value) in &self.variables {
            if key.to_lowercase().contains("pass") || key.to_lowercase().contains("password") {
                // This is a very simple check; in reality, we'd check if it's a hash.
                if !value.starts_with('$') && !value.is_empty() {
                    issues.push(ValidationIssue {
                        field: format!("variables.{}", key),
                        message: "plaintext password detected; consider using a hash".to_string(),
                    });
                }
            }
        }

        issues
    }

    /// Apply fixes to the configuration (e.g., hash plaintext passwords).
    pub fn fix_it(&mut self) {
        // Collect keys that need to be fixed to avoid borrowing issues.
        let mut keys_to_fix = Vec::new();
        for (key, value) in &self.variables {
            if (key.to_lowercase().contains("pass") || key.to_lowercase().contains("password"))
                && !value.starts_with('$')
                && !value.is_empty()
            {
                keys_to_fix.push(key.clone());
            }
        }

        // Now fix each key.
        for key in keys_to_fix {
            // Replace with a placeholder hash.
            self.variables
                .insert(key, "$6$rounds=5000$examplesalt$".to_string());
        }
    }
}

/// Represents a validation issue.
#[derive(Debug)]
pub struct ValidationIssue {
    /// The field that has the issue.
    pub field: String,
    /// A description of the issue.
    pub message: String,
}

/// Trait for cloud providers.
pub trait Provider {
    /// Generate files based on the configuration.
    fn generate(&self, config: &Config) -> anyhow::Result<Vec<(String, String)>>;
}
