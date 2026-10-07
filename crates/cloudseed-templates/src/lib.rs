use handlebars::Handlebars;
use serde_json::Value;

/// Render a Handlebars template with the given data.
pub fn render_template(template: &str, data: &Value) -> anyhow::Result<String> {
    let mut reg = Handlebars::new();
    reg.register_template_string("t", template)?;
    Ok(reg.render("t", &data)?)
}

/// A simple template engine that can load templates from a directory.
#[derive(Debug, Default)]
pub struct TemplateEngine {
    /// The handlebars registry.
    reg: Handlebars<'static>,
}

impl TemplateEngine {
    /// Create a new TemplateEngine.
    pub fn new() -> Self {
        Self::default()
    }

    /// Load a template from a string.
    pub fn load_template<S: Into<String>>(&mut self, name: S, template: S) -> anyhow::Result<()> {
        let name_str = name.into();
        let template_str = template.into();
        self.reg.register_template_string(name_str.as_str(), template_str.as_str())?;
        Ok(())
    }

    /// Render a template by name with the given data.
    pub fn render<T: serde::Serialize>(&self, name: &str, data: &T) -> anyhow::Result<String> {
        Ok(self.reg.render(name, &data)?)
    }

    /// Get the default user-data template.
    pub fn user_data_template() -> &'static str {
        r#"
#cloud-config
hostname: {{hostname}}
timezone: {{timezone}}
users:
  - name: ubuntu
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    groups: users, admin
    shell: /bin/bash
    lock-passwd: false
    ssh-authorized-keys:
      - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...
"#
    }
}
