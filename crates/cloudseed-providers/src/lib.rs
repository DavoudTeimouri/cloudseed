use cloudseed_core::{Config, Provider};
use cloudseed_templates::TemplateEngine;
use serde_json::{json, Value};
use std::collections::HashMap;

/// Local provider (for local development, testing, etc.).
pub struct LocalProvider;

impl Provider for LocalProvider {
    fn generate(&self, config: &Config) -> anyhow::Result<Vec<(String, String)>> {
        // Prepare the data for the template as a JSON-serializable map.
        let mut data: HashMap<String, Value> = HashMap::new();
        data.insert("hostname".to_string(), json!(config.name));

        // Add timezone if configured.
        if let Some(tz) = &config.timezone {
            if let Some(zone) = &tz.zone {
                data.insert("timezone".to_string(), json!(zone));
            }
        } else {
            data.insert("timezone".to_string(), json!("UTC"));
        }

        // Prepare the default user.
        let mut user = HashMap::new();
        user.insert("name".to_string(), json!("ubuntu"));
        user.insert("sudo".to_string(), json!(vec!["ALL=(ALL) NOPASSWD:ALL"]));
        user.insert("groups".to_string(), json!(vec!["users", "admin"]));
        user.insert("shell".to_string(), json!("/bin/bash"));
        user.insert("lock-passwd".to_string(), json!(false));
        user.insert(
            "ssh-authorized-keys".to_string(),
            json!(vec!["ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ..."]),
        );

        data.insert("users".to_string(), json!(vec![user]));

        // Add variables from the config.
        for (key, value) in &config.variables {
            data.insert(key.clone(), json!(value));
        }

        // Load and render the template.
        let mut engine = TemplateEngine::new();
        engine.load_template("user-data", TemplateEngine::user_data_template())?;
        let user_data = engine.render("user-data", &data)?;

        Ok(vec![("user-data.yaml".to_string(), user_data)])
    }
}

#[cfg(feature = "aws")]
pub struct AwsProvider;
#[cfg(feature = "aws")]
impl Provider for AwsProvider {
    fn generate(&self, config: &Config) -> anyhow::Result<Vec<(String, String)>> {
        // For now, we'll generate the same as local.
        LocalProvider.generate(config)
    }
}

#[cfg(feature = "azure")]
pub struct AzureProvider;
#[cfg(feature = "azure")]
impl Provider for AzureProvider {
    fn generate(&self, config: &Config) -> anyhow::Result<Vec<(String, String)>> {
        LocalProvider.generate(config)
    }
}

#[cfg(feature = "gcp")]
pub struct GcpProvider;
#[cfg(feature = "gcp")]
impl Provider for GcpProvider {
    fn generate(&self, config: &Config) -> anyhow::Result<Vec<(String, String)>> {
        LocalProvider.generate(config)
    }
}

/// Get a provider for the given platform string.
pub fn get_provider(platform: &str) -> anyhow::Result<Box<dyn Provider>> {
    match platform {
        "local" => Ok(Box::new(LocalProvider)),
        #[cfg(feature = "aws")]
        "aws" => Ok(Box::new(AwsProvider)),
        #[cfg(feature = "azure")]
        "azure" => Ok(Box::new(AzureProvider)),
        #[cfg(feature = "gcp")]
        "gcp" => Ok(Box::new(GcpProvider)),
        _ => Err(anyhow::anyhow!("Unsupported platform: {}", platform)),
    }
}
