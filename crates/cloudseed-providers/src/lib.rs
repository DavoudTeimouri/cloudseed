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
