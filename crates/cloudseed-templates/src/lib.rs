//! Rendering of the files CloudSeed writes to a target system.
//!
//! The Linux cloud-config is built as typed values and serialized with
//! `serde_yaml`, so quoting, block scalars and escaping are handled by the
//! serializer rather than by hand. The Windows artifacts are fixed formats
//! with a handful of substitutions.

use cloudseed_core::Config;
use serde::Serialize;

/// The cloud-config document written as `user-data`.
#[derive(Debug, Serialize)]
struct CloudConfig<'a> {
    #[serde(skip_serializing_if = "Option::is_none")]
    hostname: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    timezone: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    locale: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    keyboard_layout: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    manage_etc_hosts: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    users: Option<Vec<CloudUser<'a>>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    ssh_pwauth: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    disable_root: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    package_update: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    package_upgrade: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    packages: Option<&'a [String]>,
    #[serde(skip_serializing_if = "Option::is_none")]
    growpart: Option<GrowPart<'a>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    ntp: Option<Ntp<'a>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    network: Option<Network<'a>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    write_files: Option<Vec<CloudFile<'a>>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    bootcmd: Option<&'a [String]>,
    #[serde(skip_serializing_if = "Option::is_none")]
    runcmd: Option<&'a [String]>,
    #[serde(skip_serializing_if = "Option::is_none")]
    final_message: Option<&'a str>,
}

/// A user entry in the cloud-config.
#[derive(Debug, Serialize)]
struct CloudUser<'a> {
    name: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    passwd: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    lock_passwd: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    sudo: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    groups: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    shell: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    ssh_authorized_keys: Option<&'a [String]>,
}

/// The `growpart` module.
#[derive(Debug, Serialize)]
struct GrowPart<'a> {
    mode: &'static str,
    devices: Vec<&'a str>,
    ignore_growroot_disabled: bool,
    partition: &'a str,
}

/// The `ntp` module.
#[derive(Debug, Serialize)]
struct Ntp<'a> {
    enabled: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    servers: Option<&'a [String]>,
}

/// The `network` module (cloud-init network config version 2).
#[derive(Debug, Serialize)]
struct Network<'a> {
    version: u8,
    ethernets: std::collections::BTreeMap<&'a str, NetworkDevice<'a>>,
}

/// One interface in the `network` module.
#[derive(Debug, Serialize)]
struct NetworkDevice<'a> {
    dhcp4: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    addresses: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    gateway4: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    nameservers: Option<Nameservers<'a>>,
}

/// DNS settings for a network device.
#[derive(Debug, Serialize)]
struct Nameservers<'a> {
    addresses: &'a [String],
    #[serde(skip_serializing_if = "Option::is_none")]
    search: Option<&'a [String]>,
}

/// A file to write on the target.
#[derive(Debug, Serialize)]
struct CloudFile<'a> {
    path: &'a str,
    permissions: &'a str,
    content: &'a str,
}

/// Render the Linux `user-data` cloud-config for `config`.
///
/// Only the modules enabled in the configuration appear in the output.
pub fn user_data(config: &Config) -> anyhow::Result<String> {
    let mut doc = CloudConfig {
        hostname: None,
        timezone: None,
        locale: None,
        keyboard_layout: None,
        manage_etc_hosts: None,
        users: None,
        ssh_pwauth: None,
        disable_root: None,
        package_update: None,
        package_upgrade: None,
        packages: None,
        growpart: None,
        ntp: None,
        network: None,
        write_files: None,
        bootcmd: None,
        runcmd: None,
        final_message: None,
    };

    if config.module_enabled("hostname") {
        doc.hostname = Some(config.resolved_hostname());
        doc.manage_etc_hosts = Some(true);
    }

    if config.module_enabled("locale") {
        doc.timezone = config.resolved_timezone();
        doc.locale = Some(&config.locale);
        doc.keyboard_layout = Some(&config.keyboard_layout);
    }

    if config.module_enabled("users") {
        let mut user = CloudUser {
            name: &config.username,
            passwd: None,
            lock_passwd: None,
            sudo: None,
            groups: None,
            shell: Some("/bin/bash"),
            ssh_authorized_keys: None,
        };
        if !config.password.is_empty() {
            user.passwd = Some(&config.password);
        }
        if config.lock_password {
            user.lock_passwd = Some(true);
        }
        if config.sudo {
            user.sudo = Some("ALL=(ALL) NOPASSWD:ALL");
            user.groups = Some("users, admin");
        }
        if config.module_enabled("ssh") && !config.ssh_keys.is_empty() {
            user.ssh_authorized_keys = Some(&config.ssh_keys);
        }
        doc.users = Some(vec![user]);
    }

    if config.module_enabled("ssh") {
        doc.ssh_pwauth = Some(config.ssh_pwauth);
    }
    if config.module_enabled("root") {
        doc.disable_root = Some(config.disable_root);
    }

    if config.module_enabled("packages") {
        doc.package_update = Some(config.package_upgrade);
        doc.package_upgrade = Some(config.package_upgrade);
        if !config.packages.is_empty() {
            doc.packages = Some(&config.packages);
        }
    }

    if config.module_enabled("disk") {
        doc.growpart = Some(GrowPart {
            mode: "auto",
            devices: vec![&config.grow_device],
            ignore_growroot_disabled: false,
            partition: &config.grow_partition,
        });
    }

    if config.module_enabled("ntp") {
        doc.ntp = Some(Ntp {
            enabled: true,
            servers: if config.ntp_servers.is_empty() {
                None
            } else {
                Some(&config.ntp_servers)
            },
        });
    }

    if config.module_enabled("network") {
        let dhcp4 = config.net_mode != "static";
        let device = NetworkDevice {
            dhcp4,
            addresses: if dhcp4 {
                None
            } else {
                Some(vec![cidr(&config.net_address, &config.net_netmask)?])
            },
            gateway4: if dhcp4 || config.net_gateway.is_empty() {
                None
            } else {
                Some(&config.net_gateway)
            },
            nameservers: if config.net_dns.is_empty() && config.net_search.is_empty() {
                None
            } else {
                Some(Nameservers {
                    addresses: &config.net_dns,
                    search: if config.net_search.is_empty() {
                        None
                    } else {
                        Some(&config.net_search)
                    },
                })
            },
        };
        let mut ethernets = std::collections::BTreeMap::new();
        ethernets.insert(config.net_interface.as_str(), device);
        doc.network = Some(Network {
            version: 2,
            ethernets,
        });
    }

    if config.module_enabled("files") && !config.write_files.is_empty() {
        doc.write_files = Some(
            config
                .write_files
                .iter()
                .map(|f| CloudFile {
                    path: &f.path,
                    permissions: if f.permissions.is_empty() {
                        "0644"
                    } else {
                        &f.permissions
                    },
                    content: &f.content,
                })
                .collect(),
        );
    }

    if config.module_enabled("bootcmd") && !config.bootcmd.is_empty() {
        doc.bootcmd = Some(&config.bootcmd);
    }
    if config.module_enabled("firstboot") && !config.firstboot.is_empty() {
        doc.runcmd = Some(&config.firstboot);
    }
    if config.module_enabled("final") && !config.final_message.is_empty() {
        doc.final_message = Some(&config.final_message);
    }

    let mut out = String::from("#cloud-config\n# Generated by CloudSeed. See cloudseed.yaml for the source configuration.\n");
    let body = serde_yaml::to_string(&doc)?;
    // An empty document serializes to `{}`; emit the header alone instead, so
    // the result is always a valid cloud-config.
    if body.trim() != "{}" {
        out.push_str(&body);
    }
    Ok(out)
}

/// Combine an IPv4 address and a dotted netmask into CIDR notation.
///
/// cloud-init network config version 2 uses `address/prefix` rather than a
/// separate netmask, so the netmask is converted to a prefix length.
fn cidr(address: &str, netmask: &str) -> anyhow::Result<String> {
    let prefix = netmask_to_prefix(netmask)
        .ok_or_else(|| anyhow::anyhow!("invalid netmask '{}'", netmask))?;
    Ok(format!("{}/{}", address, prefix))
}

/// The prefix length of a dotted-decimal IPv4 netmask.
fn netmask_to_prefix(netmask: &str) -> Option<u32> {
    let mut prefix = 0u32;
    let mut seen_zero = false;
    for octet in netmask.split('.') {
        let value: u32 = octet.parse().ok()?;
        if value > 255 {
            return None;
        }
        for bit in (0..8).rev() {
            if value & (1 << bit) != 0 {
                if seen_zero {
                    return None;
                }
                prefix += 1;
            } else {
                seen_zero = true;
            }
        }
    }
    Some(prefix)
}

/// Render the Linux `meta-data` instance identity file.
pub fn meta_data(config: &Config) -> String {
    let hostname = config.resolved_hostname();
    format!("instance-id: {}\nlocal-hostname: {}\n", hostname, hostname)
}

/// Render the Cloudbase-Init service configuration for Windows.
pub fn cloudbase_init() -> String {
    cloudbase_init_with("cloudbase-init.conf")
}

/// Render the Cloudbase-Init unattend configuration for Windows.
pub fn cloudbase_init_unattend() -> String {
    cloudbase_init_with("cloudbase-init-unattend.conf")
}

fn cloudbase_init_with(config_loc: &str) -> String {
    format!(
        "[DEFAULT]\n\
username=Administrator\n\
password=CloudSeed\n\
port=62379\n\
plugins=cloudbaseinit.metadata.service, cloudbaseinit.userdata.service, cloudbaseinit.diskmanager.service, cloudbaseinit.networkmanager.service, cloudbaseinit.sethostname.service\n\
debug=true\n\
log_file=C:\\Program Files\\Cloudbase Solutions\\Cloudbase-Init\\log\\cloudbase-init.log\n\
metadata_services=cloudbaseinit.metadata.service\n\
userdata_services=cloudbaseinit.userdata.service\n\
plugins_loc=LocalScriptsPlugin\n\
config_loc=C:\\Program Files\\Cloudbase Solutions\\Cloudbase-Init\\conf\\{config_loc}\n"
    )
}

/// Render the Sysprep answer file for Windows.
pub fn sysprep_unattend(config: &Config) -> String {
    let computer_name = if config.sysprep_computer_prefix.is_empty() {
        config.name.clone()
    } else {
        format!("{}-{}", config.sysprep_computer_prefix, config.name)
    };
    let timezone = if config.sysprep_timezone.is_empty() {
        "UTC".to_string()
    } else {
        config.sysprep_timezone.clone()
    };
    let admin_password = if config.password.is_empty() {
        "CloudSeed".to_string()
    } else {
        config.password.clone()
    };

    format!(
        r#"<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend">
    <settings pass="generalize">
        <component name="Microsoft-Windows-Deployment" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <RunSynchronous>
                <RunSynchronousCommand wcm:action="add">
                    <Order>1</Order>
                    <Description>Generalize the image</Description>
                    <Path>cmd.exe</Path>
                    <CommandLine>sysprep /generalize /oobe /quiet /quit</CommandLine>
                </RunSynchronousCommand>
            </RunSynchronous>
        </component>
    </settings>
    <settings pass="specialize">
        <component name="Microsoft-Windows-Deployment" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <RunSynchronous>
                <RunSynchronousCommand wcm:action="add">
                    <Order>1</Order>
                    <Description>Set the computer name</Description>
                    <Path>cmd.exe</Path>
                    <CommandLine>wmic computersystem where name="%computername%" rename {computer_name}</CommandLine>
                </RunSynchronousCommand>
            </RunSynchronous>
        </component>
    </settings>
    <settings pass="oobeSystem">
        <component name="Microsoft-Windows-Deployment" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <UserAccounts>
                <AdministratorPassword>
                    <Value>{admin_password}</Value>
                    <PlainText>true</PlainText>
                </AdministratorPassword>
            </UserAccounts>
            <TimeZone>{timezone}</TimeZone>
            <OOBE>
                <HideEULAPage>true</HideEULAPage>
                <HideLocalAccountScreen>true</HideLocalAccountScreen>
                <HideOEMRegistrationScreen>true</HideOEMRegistrationScreen>
                <HideOnlineAccountScreens>true</HideOnlineAccountScreens>
                <HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE>
                <ProtectYourPC>3</ProtectYourPC>
                <SkipMachineOOBE>true</SkipMachineOOBE>
                <SkipUserOOBE>true</SkipUserOOBE>
            </OOBE>
        </component>
    </settings>
</unattend>
"#
    )
}

/// Render the batch script that runs Sysprep generalize on a Windows image.
pub fn run_sysprep() -> String {
    r#"@echo off
REM Runs Sysprep in generalize mode so the image can be cloned safely.
REM The resulting VM gets a new SID, new hostname and a new machine ID.

echo [CloudSeed] Running Sysprep generalize...
C:\Windows\System32\Sysprep\Sysprep.exe /generalize /oobe /quiet /quit
echo [CloudSeed] Sysprep finished. The system will shut down.
"#
    .to_string()
}

/// The Linux script that prepares a golden image for templating.
pub fn template_cleanup_linux() -> String {
    r#"#!/bin/sh
# Prepares a Linux image to become a golden image.
# Run as root on the target, just before shutting the VM down.
#
# Each clone must get a fresh identity, so the machine-id, the SSH host keys
# and the cloud-init state are removed here.

set -e

echo "[CloudSeed] truncating logs"
find /var/log -type f -name '*.log' -exec truncate -s 0 {} + 2>/dev/null || true
journalctl --rotate 2>/dev/null || true
journalctl --vacuum-time=1s 2>/dev/null || true

echo "[CloudSeed] clearing temp files"
rm -rf /tmp/* /var/tmp/* 2>/dev/null || true

echo "[CloudSeed] clearing package cache"
if command -v apt-get >/dev/null 2>&1; then apt-get clean; fi
if command -v dnf >/dev/null 2>&1; then dnf clean all; fi
if command -v yum >/dev/null 2>&1; then yum clean all; fi
if command -v zypper >/dev/null 2>&1; then zypper clean --all; fi

echo "[CloudSeed] removing SSH host keys"
rm -f /etc/ssh/ssh_host_* 2>/dev/null || true

echo "[CloudSeed] removing persistent network rules"
rm -f /etc/udev/rules.d/70-persistent-net.rules 2>/dev/null || true

echo "[CloudSeed] clearing machine identity"
rm -f /etc/machine-id /var/lib/dbus/machine-id 2>/dev/null || true
if command -v cloud-init >/dev/null 2>&1; then
    cloud-init clean --machine-id --logs --seed
fi

echo "[CloudSeed] done. Shut the VM down and convert it to a template."
"#
    .to_string()
}

/// The Windows script that prepares a golden image for templating.
pub fn template_cleanup_windows() -> String {
    r#"@echo off
REM Prepares a Windows image to become a golden image.
REM Run as Administrator on the target, just before shutting the VM down.
REM
REM Each clone must get a fresh identity, so the event logs, the update cache
REM and the old drivers are cleared here.

echo [CloudSeed] clearing event logs
wevtutil cl System
wevtutil cl Security
wevtutil cl Application

echo [CloudSeed] clearing Windows Update cache
if exist C:\Windows\SoftwareDistribution\Download del /q /s C:\Windows\SoftwareDistribution\Download\* >nul 2>&1

echo [CloudSeed] removing old drivers
for /f "skip=1 tokens=3" %%a in ('pnputil /enum-drivers ^| findstr /i "Published Name"') do (
    echo Removing %%a
    pnputil /delete-driver %%a /uninstall /force >nul 2>&1
)

echo [CloudSeed] done. Shut the VM down and convert it to a template.
"#
    .to_string()
}

/// The vSphere Guest Customization Specification for `config`.
pub fn vsphere_customization_spec(config: &Config) -> String {
    let hostname = config.resolved_hostname();
    let org = if config.sysprep_organization.is_empty() {
        "CloudSeed".to_string()
    } else {
        config.sysprep_organization.clone()
    };
    let owner = if config.sysprep_owner.is_empty() {
        "Administrator".to_string()
    } else {
        config.sysprep_owner.clone()
    };
    let timezone = config
        .resolved_timezone()
        .unwrap_or_else(|| "UTC".to_string());
    let domain = if config.net_domain.is_empty() {
        "".to_string()
    } else {
        config.net_domain.clone()
    };
    let dns_servers = config.net_dns.join("\n        ");
    let dns_suffixes = config.net_search.join("\n        ");

    format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<VMware:CustomizationSpec xmlns="vmware" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="CustomizationSpec">
    <Info>
        <Name>{spec_name}</Name>
        <Description>Generated by CloudSeed</Description>
    </Info>
    <GlobalSettings>
        <TimeZone>{timezone}</TimeZone>
    </GlobalSettings>
    <Identity>
        <AdminPassword>{admin_password}</AdminPassword>
        <Domain>AD</Domain>
        <DomainAdmin>{owner}</DomainAdmin>
        <DomainAdminPassword>{admin_password}</DomainAdminPassword>
        <JoinDomain>domain.local</JoinDomain>
    </Identity>
    <HostName>
        <HostName>{hostname}</HostName>
        <DomainName>{domain}</DomainName>
    </HostName>
    <GlobalRoutingSettings>
        <DnsSuffixList>
{dns_suffixes}
        </DnsSuffixList>
        <DnsServerList>
{dns_servers}
        </DnsServerList>
    </GlobalRoutingSettings>
    <Organization>
        <OrgName>{org}</OrgName>
        <FullName>{owner}</FullName>
    </Organization>
</VMware:CustomizationSpec>
"#,
        spec_name = config.vsphere_spec_name,
        admin_password = if config.password.is_empty() {
            "CloudSeed".to_string()
        } else {
            config.password.clone()
        },
    )
}
