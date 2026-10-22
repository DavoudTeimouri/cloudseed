//! Core configuration model, validation, and generation for CloudSeed.
//!
//! The [`Config`] struct models the fields documented in `README.md`. Every
//! optional field carries a `serde` default so that a minimal config (just
//! `version`, `name`, `platform`) still loads and generates a complete
//! cloud-config.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::Path;

/// Platforms CloudSeed can target.
pub const PLATFORMS: &[&str] = &["vsphere", "kvm", "physical"];

/// Operating systems CloudSeed can generate configuration for.
pub const OS_TYPES: &[&str] = &["linux", "windows"];

/// Modules that can be enabled in a configuration.
///
/// Platform modules (`platform_*`) let the hypervisor own a concern, which
/// suppresses the matching cloud-init module.
pub const MODULES: &[&str] = &[
    "hostname",
    "users",
    "ssh",
    "root",
    "network",
    "packages",
    "locale",
    "disk",
    "ntp",
    "files",
    "bootcmd",
    "firstboot",
    "final",
    "platform_hostname",
    "platform_network",
    "platform_ntp",
    "template_best_practices",
    "vsphere_spec",
    "vsphere_scripts",
];

/// A file to write on the target system.
#[derive(Debug, Deserialize, Serialize, Clone, PartialEq, Default)]
pub struct WriteFile {
    /// Absolute path on the target.
    #[serde(default)]
    pub path: String,
    /// File content.
    #[serde(default)]
    pub content: String,
    /// POSIX permission bits, e.g. `0644`.
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub permissions: String,
}

/// Represents a CloudSeed configuration.
#[derive(Debug, Deserialize, Serialize, Clone, PartialEq)]
pub struct Config {
    /// The version of the configuration format.
    #[serde(default)]
    pub version: String,
    /// The name of the project or deployment.
    #[serde(default)]
    pub name: String,
    /// The target platform: `vsphere`, `kvm` or `physical`.
    #[serde(default)]
    pub platform: String,
    /// The target operating system: `linux` or `windows`.
    #[serde(default = "default_os_type")]
    pub os_type: String,
    /// Modules to include. Empty means "every non-platform module".
    #[serde(default)]
    pub modules: Vec<String>,
    /// Custom variables available to templates.
    #[serde(default)]
    pub variables: HashMap<String, String>,

    // -- Hostname ---------------------------------------------------------
    /// Explicit hostname. Empty means derive it from `hostname_prefix`.
    #[serde(default)]
    pub hostname: String,
    /// Prefix used to derive a hostname when `hostname` is empty.
    #[serde(default = "default_hostname_prefix")]
    pub hostname_prefix: String,
    /// Let the platform set the hostname instead of cloud-init.
    #[serde(default = "default_true")]
    pub use_platform_hostname: bool,

    // -- User -------------------------------------------------------------
    /// Name of the primary user created on the target.
    #[serde(default = "default_username")]
    pub username: String,
    /// Password for the primary user. Plaintext or an existing crypt hash.
    #[serde(default)]
    pub password: String,
    /// Emit the password verbatim instead of hashing it.
    #[serde(default)]
    pub plaintext_password: bool,
    /// SHA-512 crypt rounds used when hashing the password.
    #[serde(default = "default_password_rounds")]
    pub password_rounds: u32,
    /// Give the primary user passwordless sudo.
    #[serde(default = "default_true")]
    pub sudo: bool,
    /// Lock the primary user's password.
    #[serde(default)]
    pub lock_password: bool,
    /// Allow password authentication over SSH.
    #[serde(default = "default_true")]
    pub ssh_pwauth: bool,
    /// Disable root SSH logins.
    #[serde(default = "default_true")]
    pub disable_root: bool,
    /// SSH public keys authorized for the primary user.
    #[serde(default)]
    pub ssh_keys: Vec<String>,

    // -- Network ----------------------------------------------------------
    /// `dhcp` or `static`.
    #[serde(default = "default_net_mode")]
    pub net_mode: String,
    /// Interface to configure in static mode.
    #[serde(default = "default_net_interface")]
    pub net_interface: String,
    /// Static IPv4 address.
    #[serde(default)]
    pub net_address: String,
    /// Static IPv4 netmask.
    #[serde(default = "default_net_netmask")]
    pub net_netmask: String,
    /// Static IPv4 gateway.
    #[serde(default)]
    pub net_gateway: String,
    /// DNS servers.
    #[serde(default = "default_net_dns")]
    pub net_dns: Vec<String>,
    /// DNS search domains.
    #[serde(default)]
    pub net_search: Vec<String>,
    /// DNS domain used when joining an Active Directory domain.
    #[serde(default)]
    pub net_domain: String,
    /// Let the platform configure the network instead of cloud-init.
    #[serde(default)]
    pub let_platform_handle_network: bool,

    // -- Packages ---------------------------------------------------------
    /// Run a package upgrade on first boot.
    #[serde(default = "default_true")]
    pub package_upgrade: bool,
    /// Packages to install on first boot.
    #[serde(default)]
    pub packages: Vec<String>,

    // -- Locale -----------------------------------------------------------
    /// IANA timezone, e.g. `Europe/Berlin`.
    #[serde(
        default = "default_timezone",
        deserialize_with = "deserialize_timezone"
    )]
    pub timezone: Option<TimezoneConfig>,
    /// Locale, e.g. `en_US.UTF-8`.
    #[serde(default = "default_locale")]
    pub locale: String,
    /// Keyboard layout, e.g. `us`.
    #[serde(default = "default_keyboard_layout")]
    pub keyboard_layout: String,

    // -- Disk -------------------------------------------------------------
    /// Device to grow, e.g. `/dev/sda`.
    #[serde(default = "default_grow_device")]
    pub grow_device: String,
    /// Partition to grow on `grow_device`.
    #[serde(default = "default_grow_partition")]
    pub grow_partition: String,

    // -- NTP --------------------------------------------------------------
    /// NTP servers.
    #[serde(default = "default_ntp_servers")]
    pub ntp_servers: Vec<String>,
    /// Let the platform configure NTP instead of cloud-init.
    #[serde(default)]
    pub let_platform_handle_ntp: bool,

    // -- Files and commands -----------------------------------------------
    /// Files written to the target.
    #[serde(default)]
    pub write_files: Vec<WriteFile>,
    /// Commands run on every boot.
    #[serde(default)]
    pub bootcmd: Vec<String>,
    /// Commands run once, on first boot.
    #[serde(default)]
    pub firstboot: Vec<String>,
    /// Message printed to the console when the boot completes.
    #[serde(default)]
    pub final_message: String,

    // -- Sysprep (Windows) ------------------------------------------------
    /// Generate a Sysprep answer file.
    #[serde(default)]
    pub sysprep: bool,
    /// Organization name written into the Sysprep answer file.
    #[serde(default)]
    pub sysprep_organization: String,
    /// Owner name written into the Sysprep answer file.
    #[serde(default)]
    pub sysprep_owner: String,
    /// Prefix for the generated computer name.
    #[serde(default = "default_sysprep_computer_prefix")]
    pub sysprep_computer_prefix: String,
    /// Windows timezone name, e.g. `W. Europe Standard Time`.
    #[serde(default)]
    pub sysprep_timezone: String,
    /// Windows locale, e.g. `en-US`.
    #[serde(default)]
    pub sysprep_locale: String,
    /// Windows product key.
    #[serde(default)]
    pub sysprep_product_key: String,

    // -- vSphere ----------------------------------------------------------
    /// Export a vSphere Guest Customization Specification.
    #[serde(default)]
    pub export_vsphere_spec: bool,
    /// Name of the exported customization specification.
    #[serde(default = "default_vsphere_spec_name")]
    pub vsphere_spec_name: String,
    /// Script run before customization.
    #[serde(default)]
    pub vsphere_pre_script: String,
    /// Script run after customization.
    #[serde(default)]
    pub vsphere_post_script: String,
    /// Include the sample pre/post scripts.
    #[serde(default)]
    pub use_sample_scripts: bool,
}

/// Timezone configuration for the VM.
#[derive(Debug, Deserialize, Serialize, Default, Clone, PartialEq)]
pub struct TimezoneConfig {
    /// The IANA timezone identifier (e.g., "America/New_York", "Europe/London").
    pub zone: Option<String>,
    /// Whether the timezone was set interactively.
    #[serde(default)]
    pub interactive: bool,
}

/// Accepts either a bare timezone string (`timezone: Europe/Berlin`) or the
/// object form (`timezone: {zone: Europe/Berlin, interactive: true}`).
fn deserialize_timezone<'de, D>(deserializer: D) -> Result<Option<TimezoneConfig>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    #[derive(Deserialize)]
    #[serde(untagged)]
    enum Raw {
        Zone(String),
        Object {
            #[serde(default)]
            zone: Option<String>,
            #[serde(default)]
            interactive: bool,
        },
    }

    let raw = Option::<Raw>::deserialize(deserializer)?;
    Ok(raw.map(|r| match r {
        Raw::Zone(zone) => TimezoneConfig {
            zone: Some(zone),
            interactive: false,
        },
        Raw::Object { zone, interactive } => TimezoneConfig { zone, interactive },
    }))
}

fn default_os_type() -> String {
    "linux".to_string()
}
fn default_hostname_prefix() -> String {
    "vm".to_string()
}
fn default_true() -> bool {
    true
}
fn default_username() -> String {
    "ubuntu".to_string()
}
fn default_password_rounds() -> u32 {
    5000
}
fn default_net_mode() -> String {
    "dhcp".to_string()
}
fn default_net_interface() -> String {
    "eth0".to_string()
}
fn default_net_netmask() -> String {
    "255.255.255.0".to_string()
}
fn default_net_dns() -> Vec<String> {
    vec!["8.8.8.8".to_string(), "1.1.1.1".to_string()]
}
fn default_locale() -> String {
    "en_US.UTF-8".to_string()
}
fn default_keyboard_layout() -> String {
    "us".to_string()
}
fn default_timezone() -> Option<TimezoneConfig> {
    None
}
fn default_grow_device() -> String {
    "/dev/sda".to_string()
}
fn default_grow_partition() -> String {
    "1".to_string()
}
fn default_ntp_servers() -> Vec<String> {
    vec!["pool.ntp.org".to_string()]
}
fn default_sysprep_computer_prefix() -> String {
    "WIN".to_string()
}
fn default_vsphere_spec_name() -> String {
    "CloudSeed-Spec".to_string()
}

impl Config {
    /// Load a configuration from a file.
    ///
    /// The format is chosen by the file extension: `.yaml`/`.yml` parse as
    /// YAML, `.toml` parses as TOML. No silent format guessing.
    pub fn from_file<P: AsRef<Path>>(path: P) -> anyhow::Result<Self> {
        let path = path.as_ref();
        let content = fs::read_to_string(path)?;
        match extension(path).as_str() {
            "yaml" | "yml" => serde_yaml::from_str(&content)
                .map_err(|e| anyhow::anyhow!("invalid YAML in {}: {}", path.display(), e)),
            "toml" => toml::from_str(&content)
                .map_err(|e| anyhow::anyhow!("invalid TOML in {}: {}", path.display(), e)),
            other => Err(anyhow::anyhow!(
                "unsupported config extension '{other}' in {}; expected .yaml, .yml, or .toml",
                path.display()
            )),
        }
    }

    /// Serialize this config to the format matching `path`'s extension.
    pub fn serialize<P: AsRef<Path>>(&self, path: P) -> anyhow::Result<String> {
        let path = path.as_ref();
        match extension(path).as_str() {
            "yaml" | "yml" => serde_yaml::to_string(self).map_err(anyhow::Error::from),
            "toml" => toml::to_string(self).map_err(anyhow::Error::from),
            other => Err(anyhow::anyhow!(
                "unsupported config extension '{other}' in {}; expected .yaml, .yml, or .toml",
                path.display()
            )),
        }
    }

    /// The hostname to apply, derived from `hostname` or `hostname_prefix`.
    pub fn resolved_hostname(&self) -> String {
        if !self.hostname.is_empty() {
            self.hostname.clone()
        } else if self.name.is_empty() {
            self.hostname_prefix.clone()
        } else {
            format!("{}-{}", self.hostname_prefix, self.name)
        }
    }

    /// The IANA timezone to apply, if any.
    pub fn resolved_timezone(&self) -> Option<String> {
        self.timezone.as_ref().and_then(|tz| tz.zone.clone())
    }

    /// Whether the cloud-init counterpart of a module is enabled.
    ///
    /// An empty module list means every module is enabled, except
    /// `template_best_practices`, which produces an extra artifact and is
    /// opt-in. A platform module suppresses its cloud-init counterpart and
    /// vice versa.
    pub fn module_enabled(&self, module: &str) -> bool {
        let listed = self.modules.iter().any(|m| m == module);
        if !self.modules.is_empty() && !listed {
            return false;
        }
        match module {
            "hostname" => !self.use_platform_hostname,
            "network" => !self.let_platform_handle_network,
            "ntp" => !self.let_platform_handle_ntp,
            // Opt-in: it adds an extra artifact, so it stays off unless asked for.
            "template_best_practices" => listed,
            _ => true,
        }
    }

    /// The effective module list, after applying platform overrides.
    pub fn effective_modules(&self) -> Vec<&'static str> {
        MODULES
            .iter()
            .copied()
            .filter(|m| self.module_enabled(m))
            .collect()
    }

    /// Validate the configuration and return a list of issues.
    pub fn validate(&self) -> Vec<ValidationIssue> {
        let mut issues = Vec::new();

        if self.version.is_empty() {
            issues.push(issue("version", "version is required"));
        }
        if self.name.is_empty() {
            issues.push(issue("name", "name is required"));
        }
        if self.platform.is_empty() {
            issues.push(issue("platform", "platform is required"));
        } else if !PLATFORMS.contains(&self.platform.as_str()) {
            issues.push(issue(
                "platform",
                format!(
                    "unknown platform '{}'; expected one of {}",
                    self.platform,
                    PLATFORMS.join(", ")
                ),
            ));
        }
        if !OS_TYPES.contains(&self.os_type.as_str()) {
            issues.push(issue(
                "os_type",
                format!(
                    "unknown os_type '{}'; expected one of {}",
                    self.os_type,
                    OS_TYPES.join(", ")
                ),
            ));
        }

        for module in &self.modules {
            if !MODULES.contains(&module.as_str()) {
                issues.push(issue("modules", format!("unknown module '{}'", module)));
            }
        }

        // Password handling.
        if !self.password.is_empty() && !self.plaintext_password && !is_crypt_hash(&self.password) {
            issues.push(issue(
                "password",
                "password is stored in plaintext; hash it or set plaintext_password: true",
            ));
        }

        // A locked password with no SSH key locks the operator out.
        if self.lock_password && self.ssh_keys.is_empty() {
            issues.push(issue(
                "lock_password",
                "lock_password is enabled but no ssh_keys are configured; the operator would be locked out",
            ));
        }

        // Static networking needs an address and a gateway.
        if self.net_mode == "static" {
            if self.net_address.is_empty() {
                issues.push(issue(
                    "net_address",
                    "net_address is required in static mode",
                ));
            }
            if self.net_gateway.is_empty() {
                issues.push(issue(
                    "net_gateway",
                    "net_gateway is required in static mode; without it the target may be unreachable",
                ));
            }
        }

        // Windows templates need Sysprep to avoid duplicate SIDs.
        if self.os_type == "windows" && !self.sysprep {
            issues.push(issue(
                "sysprep",
                "windows target without sysprep: cloned VMs will share a SID",
            ));
        }

        // A field that belongs to a disabled module is silently dropped.
        let ignored: [(&str, bool, &str); 7] = [
            ("password", !self.password.is_empty(), "users"),
            ("ssh_keys", !self.ssh_keys.is_empty(), "ssh"),
            ("net_address", !self.net_address.is_empty(), "network"),
            ("packages", !self.packages.is_empty(), "packages"),
            ("timezone", self.resolved_timezone().is_some(), "locale"),
            ("write_files", !self.write_files.is_empty(), "files"),
            ("firstboot", !self.firstboot.is_empty(), "firstboot"),
        ];
        for (field, present, module) in ignored {
            if present && !self.module_enabled(module) {
                issues.push(issue(
                    field,
                    format!(
                        "'{field}' is set but the '{module}' module is disabled, so it will not be applied"
                    ),
                ));
            }
        }

        issues
    }

    /// Apply fixes to the configuration.
    ///
    /// Currently hashes a plaintext password with SHA-512 crypt. Returns an
    /// error if the password cannot be hashed.
    pub fn fix_it(&mut self) -> anyhow::Result<()> {
        if self.password.is_empty() || self.plaintext_password || is_crypt_hash(&self.password) {
            return Ok(());
        }

        let params = sha_crypt::Sha512Params::new(self.password_rounds as usize)
            .map_err(|_| anyhow::anyhow!("invalid password_rounds: {}", self.password_rounds))?;
        let hashed = sha_crypt::sha512_simple(&self.password, &params)
            .map_err(|_| anyhow::anyhow!("failed to hash password"))?;
        self.password = hashed;
        Ok(())
    }

    /// Generate the list of files to create for this configuration.
    pub fn generate_files(&self, provider: &dyn Provider) -> anyhow::Result<Vec<(String, String)>> {
        provider.generate(self)
    }
}

/// Serialize `config` to the format implied by `path`'s extension.
pub fn serialize_config<P: AsRef<Path>>(config: &Config, path: P) -> anyhow::Result<String> {
    config.serialize(path)
}

/// The lowercase file extension of `path`, or an empty string.
fn extension(path: &Path) -> String {
    path.extension()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_ascii_lowercase()
}

/// Whether a value looks like a crypt hash rather than a plaintext password.
fn is_crypt_hash(value: &str) -> bool {
    value.starts_with('$') && value.split('$').count() >= 3
}

/// A configuration issue found by [`Config::validate`].
#[derive(Debug, Clone, PartialEq)]
pub struct ValidationIssue {
    /// The field that has the issue.
    pub field: String,
    /// A description of the issue.
    pub message: String,
}

fn issue(field: &str, message: impl Into<String>) -> ValidationIssue {
    ValidationIssue {
        field: field.to_string(),
        message: message.into(),
    }
}

/// Trait for cloud providers.
pub trait Provider {
    /// Generate files based on the configuration.
    fn generate(&self, config: &Config) -> anyhow::Result<Vec<(String, String)>>;
}
