use cloudseed_core::{Config, Provider};

/// Generates the files for one platform and operating system combination.
pub struct PlatformProvider {
    platform: String,
    os_type: String,
}

impl PlatformProvider {
    /// Create a provider for `platform` (`vsphere`, `kvm` or `physical`).
    pub fn new(platform: &str, os_type: &str) -> Self {
        Self {
            platform: platform.to_string(),
            os_type: os_type.to_string(),
        }
    }

    /// The output subdirectory, e.g. `vsphere-linux`.
    pub fn output_dir(&self) -> String {
        format!("{}-{}", self.platform, self.os_type)
    }
}

impl Provider for PlatformProvider {
    fn generate(&self, config: &Config) -> anyhow::Result<Vec<(String, String)>> {
        let dir = self.output_dir();
        let mut files = Vec::new();

        if self.os_type == "windows" {
            files.push((
                format!("{dir}/cloudbase-init.conf"),
                cloudseed_templates::cloudbase_init(),
            ));
            files.push((
                format!("{dir}/cloudbase-init-unattend.conf"),
                cloudseed_templates::cloudbase_init_unattend(),
            ));
            // Cloudbase-Init consumes the same cloud-config dialect as
            // cloud-init, so the module output is written as user-data too.
            files.push((
                format!("{dir}/user-data"),
                cloudseed_templates::user_data(config)?,
            ));
            if config.sysprep {
                files.push((
                    format!("{dir}/sysprep-unattend.xml"),
                    cloudseed_templates::sysprep_unattend(config),
                ));
                files.push((
                    format!("{dir}/run-sysprep.bat"),
                    cloudseed_templates::run_sysprep(),
                ));
            }
        } else {
            files.push((
                format!("{dir}/user-data"),
                cloudseed_templates::user_data(config)?,
            ));
            files.push((
                format!("{dir}/meta-data"),
                cloudseed_templates::meta_data(config),
            ));
        }

        if self.platform == "vsphere" && config.export_vsphere_spec {
            files.push((
                format!("{dir}/vsphere-customization-spec.xml"),
                cloudseed_templates::vsphere_customization_spec(config),
            ));
        }

        if self.platform == "vsphere" && config.module_enabled("vsphere_scripts") {
            let (pre, post) = sample_scripts(config);
            files.push((format!("{dir}/vsphere-pre-script.sh"), pre));
            files.push((format!("{dir}/vsphere-post-script.sh"), post));
        }

        if config.module_enabled("template_best_practices") {
            if self.os_type == "windows" {
                files.push((
                    format!("{dir}/template-cleanup.bat"),
                    cloudseed_templates::template_cleanup_windows(),
                ));
            } else {
                files.push((
                    format!("{dir}/template-cleanup.sh"),
                    cloudseed_templates::template_cleanup_linux(),
                ));
            }
        }

        files.push((format!("{dir}/README.txt"), readme(config, &dir)));
        files.push((
            format!("{dir}/cloudseed.yaml"),
            config.serialize("cloudseed.yaml")?,
        ));

        Ok(files)
    }
}

/// The pre/post customization scripts shipped with a vSphere export.
fn sample_scripts(config: &Config) -> (String, String) {
    let pre = if config.vsphere_pre_script.is_empty() {
        "#!/bin/sh\n# Runs on the guest before cloud-init applies the configuration.\necho '[CloudSeed] pre-customization script'\n"
            .to_string()
    } else {
        config.vsphere_pre_script.clone()
    };
    let post = if config.vsphere_post_script.is_empty() {
        "#!/bin/sh\n# Runs on the guest after cloud-init applied the configuration.\necho '[CloudSeed] post-customization script'\n"
            .to_string()
    } else {
        config.vsphere_post_script.clone()
    };
    (pre, post)
}

/// The quick-reference file written next to the generated configuration.
fn readme(config: &Config, dir: &str) -> String {
    let mut out = String::new();
    out.push_str("CloudSeed generated configuration\n");
    out.push_str("==================================\n\n");
    out.push_str(&format!("Platform: {}\n", config.platform));
    out.push_str(&format!("OS:       {}\n", config.os_type));
    out.push_str(&format!("Directory: {dir}\n\n"));

    if config.os_type == "windows" {
        out.push_str("Apply (Windows)\n");
        out.push_str("-----------------\n");
        out.push_str("1. Install Cloudbase-Init on the golden image.\n");
        out.push_str("2. Copy cloudbase-init.conf into the Cloudbase-Init conf directory.\n");
        out.push_str("3. Copy user-data next to it; Cloudbase-Init reads the same\n");
        out.push_str("   cloud-config dialect as cloud-init.\n");
        if config.sysprep {
            out.push_str("4. Copy sysprep-unattend.xml to the image and run run-sysprep.bat as Administrator.\n");
        }
    } else {
        out.push_str("Apply (Linux)\n");
        out.push_str("-------------\\n");
        out.push_str("1. vSphere: set guestinfo.userdata and guestinfo.metadata on the VM.\n");
        out.push_str(
            "   KVM: virt-install --cloud-init user-data=./user-data,meta-data=./meta-data\n",
        );
        out.push_str("2. Or copy user-data into /etc/cloud/cloud.cfg.d/ on the golden image.\n");
    }

    let issues = config.validate();
    if !issues.is_empty() {
        out.push_str("\nWarnings\n--------\n");
        for issue in issues {
            out.push_str(&format!("- {}: {}\n", issue.field, issue.message));
        }
    }

    if config.module_enabled("template_best_practices") {
        out.push_str("\nTemplate preparation\n---------------------\n");
        out.push_str(
            "This image is meant to become a template. Before sealing it, run the\n\
             cleanup script next to this file on the target:\n",
        );
        if config.os_type == "windows" {
            out.push_str("  .\\template-cleanup.bat   (run as Administrator)\n");
            out.push_str(
                "\nIt clears the event logs and the Windows Update cache, removes old\n\
                         drivers from the DriverStore, and clears the machine identity.\n",
            );
        } else {
            out.push_str("  sudo ./template-cleanup.sh\n");
            out.push_str(
                "\nIt truncates the logs, clears the temp directories and the package\n\
                         cache, removes the SSH host keys and the machine-id, and runs\n\
                         `cloud-init clean --machine-id`.\n",
            );
        }
        out.push_str(
            "\nDo this before converting the VM to a template: each clone must get a\n\
                     fresh identity (new machine-id, new SSH host keys, new SID on Windows).\n",
        );
    }

    out
}

/// Get a provider for the given platform and operating system.
pub fn get_provider(platform: &str, os_type: &str) -> anyhow::Result<Box<dyn Provider>> {
    if !cloudseed_core::PLATFORMS.contains(&platform) {
        return Err(anyhow::anyhow!(
            "Unsupported platform: {}; expected one of {}",
            platform,
            cloudseed_core::PLATFORMS.join(", ")
        ));
    }
    if !cloudseed_core::OS_TYPES.contains(&os_type) {
        return Err(anyhow::anyhow!(
            "Unsupported os_type: {}; expected one of {}",
            os_type,
            cloudseed_core::OS_TYPES.join(", ")
        ));
    }
    Ok(Box::new(PlatformProvider::new(platform, os_type)))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn linux_config() -> cloudseed_core::Config {
        cloudseed_core::Config {
            version: "1.0".to_string(),
            name: "test".to_string(),
            platform: "kvm".to_string(),
            os_type: "linux".to_string(),
            modules: Vec::new(),
            variables: HashMap::new(),
            hostname: String::new(),
            hostname_prefix: "vm".to_string(),
            use_platform_hostname: true,
            username: "ubuntu".to_string(),
            password: String::new(),
            plaintext_password: false,
            password_rounds: 5000,
            sudo: true,
            lock_password: false,
            ssh_pwauth: true,
            disable_root: true,
            ssh_keys: Vec::new(),
            net_mode: "dhcp".to_string(),
            net_interface: "eth0".to_string(),
            net_address: String::new(),
            net_netmask: "255.255.255.0".to_string(),
            net_gateway: String::new(),
            net_dns: vec!["8.8.8.8".to_string()],
            net_search: Vec::new(),
            net_domain: String::new(),
            let_platform_handle_network: false,
            package_upgrade: true,
            packages: Vec::new(),
            timezone: None,
            locale: "en_US.UTF-8".to_string(),
            keyboard_layout: "us".to_string(),
            grow_device: "/dev/sda".to_string(),
            grow_partition: "1".to_string(),
            ntp_servers: vec!["pool.ntp.org".to_string()],
            let_platform_handle_ntp: false,
            write_files: Vec::new(),
            bootcmd: Vec::new(),
            firstboot: Vec::new(),
            final_message: String::new(),
            sysprep: false,
            sysprep_organization: String::new(),
            sysprep_owner: String::new(),
            sysprep_computer_prefix: "WIN".to_string(),
            sysprep_timezone: String::new(),
            sysprep_locale: String::new(),
            sysprep_product_key: String::new(),
            export_vsphere_spec: false,
            vsphere_spec_name: "CloudSeed-Spec".to_string(),
            vsphere_pre_script: String::new(),
            vsphere_post_script: String::new(),
            use_sample_scripts: false,
        }
    }

    fn windows_config() -> cloudseed_core::Config {
        let mut c = linux_config();
        c.platform = "vsphere".to_string();
        c.os_type = "windows".to_string();
        c.sysprep = true;
        c.export_vsphere_spec = true;
        c.modules = vec!["template_best_practices".to_string(), "vsphere_scripts".to_string()];
        c
    }

    #[test]
    fn output_dir_is_platform_os() {
        let p = PlatformProvider::new("vsphere", "linux");
        assert_eq!(p.output_dir(), "vsphere-linux");
        let p = PlatformProvider::new("kvm", "windows");
        assert_eq!(p.output_dir(), "kvm-windows");
    }

    #[test]
    fn get_provider_accepts_documented_platforms() {
        for platform in cloudseed_core::PLATFORMS {
            for os_type in cloudseed_core::OS_TYPES {
                assert!(get_provider(platform, os_type).is_ok());
            }
        }
    }

    #[test]
    fn get_provider_rejects_unknown_platform() {
        assert!(get_provider("aws", "linux").is_err());
        assert!(get_provider("azure", "linux").is_err());
    }

    #[test]
    fn get_provider_rejects_unknown_os_type() {
        assert!(get_provider("vsphere", "macos").is_err());
    }

    #[test]
    fn generate_linux_produces_user_data_meta_data_readme_config() {
        let p = PlatformProvider::new("kvm", "linux");
        let files = p.generate(&linux_config()).unwrap();
        let names: Vec<&str> = files.iter().map(|(n, _)| n.as_str()).collect();
        assert!(names.iter().any(|n| n.ends_with("kvm-linux/user-data")));
        assert!(names.iter().any(|n| n.ends_with("kvm-linux/meta-data")));
        assert!(names.iter().any(|n| n.ends_with("kvm-linux/README.txt")));
        assert!(names.iter().any(|n| n.ends_with("kvm-linux/cloudseed.yaml")));
        // No Windows-only files on Linux.
        assert!(!names.iter().any(|n| n.contains("cloudbase-init")));
        assert!(!names.iter().any(|n| n.contains("sysprep")));
    }

    #[test]
    fn generate_windows_produces_cloudbase_init_and_user_data() {
        let p = PlatformProvider::new("vsphere", "windows");
        let files = p.generate(&windows_config()).unwrap();
        let names: Vec<&str> = files.iter().map(|(n, _)| n.as_str()).collect();
        assert!(names.iter().any(|n| n.ends_with("vsphere-windows/cloudbase-init.conf")));
        assert!(names.iter().any(|n| n.ends_with("vsphere-windows/cloudbase-init-unattend.conf")));
        assert!(names.iter().any(|n| n.ends_with("vsphere-windows/user-data")));
        assert!(names.iter().any(|n| n.ends_with("vsphere-windows/sysprep-unattend.xml")));
        assert!(names.iter().any(|n| n.ends_with("vsphere-windows/run-sysprep.bat")));
    }

    #[test]
    fn generate_template_cleanup_when_module_enabled() {
        let p = PlatformProvider::new("kvm", "linux");
        let files = p.generate(&windows_config()).unwrap();
        let names: Vec<&str> = files.iter().map(|(n, _)| n.as_str()).collect();
        assert!(names.iter().any(|n| n.ends_with("kvm-linux/template-cleanup.sh")));
    }

    #[test]
    fn generate_vsphere_spec_when_export_enabled() {
        let p = PlatformProvider::new("vsphere", "linux");
        let mut c = linux_config();
        c.export_vsphere_spec = true;
        let files = p.generate(&c).unwrap();
        let names: Vec<&str> = files.iter().map(|(n, _)| n.as_str()).collect();
        assert!(names.iter().any(|n| n.ends_with("vsphere-linux/vsphere-customization-spec.xml")));
    }

    #[test]
    fn generate_vsphere_scripts_when_module_enabled() {
        let p = PlatformProvider::new("vsphere", "linux");
        let mut c = linux_config();
        c.modules = vec!["vsphere_scripts".to_string()];
        let files = p.generate(&c).unwrap();
        let names: Vec<&str> = files.iter().map(|(n, _)| n.as_str()).collect();
        assert!(names.iter().any(|n| n.ends_with("vsphere-linux/vsphere-pre-script.sh")));
        assert!(names.iter().any(|n| n.ends_with("vsphere-linux/vsphere-post-script.sh")));
    }

    #[test]
    fn user_data_is_valid_yaml() {
        let p = PlatformProvider::new("kvm", "linux");
        let files = p.generate(&linux_config()).unwrap();
        let user_data = files
            .iter()
            .find(|(n, _)| n.ends_with("kvm-linux/user-data"))
            .map(|(_, c)| c)
            .unwrap();
        // Must start with the cloud-config header and parse as YAML.
        assert!(user_data.starts_with("#cloud-config"));
        let parsed: serde_yaml::Value =
            serde_yaml::from_str(&user_data["#cloud-config\n".len()..]).unwrap();
        assert!(parsed.is_mapping());
    }
}
