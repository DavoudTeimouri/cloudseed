"""Render a TemplateConfig into cloud-init / Cloudbase-Init / Sysprep files.

Config-only output: no ISO is produced. Minimal YAML emitter (no PyYAML).
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List

from .model import TemplateConfig, _ask_overwrite, print_info, print_warn

# --- minimal YAML emitter --------------------------------------------------

def _needs_quote(s: str) -> bool:
    if s == "":
        return True
    unsafe = set("#':{}[],&*?|<>=!%@`\"\\")
    if s[0] in unsafe or s[-1] in unsafe or any(c in unsafe for c in s):
        return True
    if s.lower() in ("true", "false", "null", "yes", "no", "on", "off"):
        return True
    if s.strip() != s:
        return True
    return False


def _scalar(s: Any) -> str:
    if isinstance(s, bool):
        return "true" if s else "false"
    s = str(s)
    if _needs_quote(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def yaml_dump(obj: Any, indent: int = 0) -> str:
    pad = "  " * indent
    lines: List[str] = []
    if isinstance(obj, dict):
        if not obj:
            return pad + "{}"
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                if isinstance(v, dict) and v or isinstance(v, list) and v:
                    lines.append(f"{pad}{k}:")
                    lines.append(yaml_dump(v, indent + 1))
                else:
                    lines.append(f"{pad}{k}: {'{}' if isinstance(v, dict) else '[]'}")
            else:
                lines.append(f"{pad}{k}: {_scalar(v)}")
    elif isinstance(obj, list):
        if not obj:
            return pad + "[]"
        for item in obj:
            if isinstance(item, (dict, list)):
                body = yaml_dump(item, indent + 1).split("\n")
                lines.append(f"{pad}- {body[0].lstrip()}")
                lines.extend(body[1:])
            else:
                lines.append(f"{pad}- {_scalar(item)}")
    else:
        lines.append(f"{pad}{_scalar(obj)}")
    return "\n".join(lines)


# --- cloud-config (Linux user-data) ---------------------------------------

def build_user_data(cfg: TemplateConfig) -> str:
    top: Dict[str, Any] = {}

    # Hostname - only set in cloud-init if NOT letting platform handle it
    if cfg.has("hostname") and cfg.hostname and not cfg.use_platform_hostname:
        top["hostname"] = cfg.hostname

    if cfg.has("users") and cfg.username:
        from .password import hash_password
        passwd = cfg.password
        if not cfg.plaintext_password:
            passwd = hash_password(cfg.password, cfg.password_rounds)
        user: Dict[str, Any] = {"name": cfg.username, "groups": "sudo" if cfg.sudo else None}
        if cfg.sudo:
            user["sudo"] = "ALL=(ALL) NOPASSWD:ALL"
        user["lock_passwd"] = cfg.lock_password
        if not cfg.lock_password:
            user["passwd"] = passwd
        if cfg.has("ssh") and cfg.ssh_keys:
            user["ssh_authorized_keys"] = cfg.ssh_keys
        top["users"] = [{k: v for k, v in user.items() if v is not None}]

    if cfg.has("ssh"):
        top["ssh_pwauth"] = cfg.ssh_pwauth
        if cfg.ssh_keys and not (cfg.has("users") and cfg.username):
            top["ssh_authorized_keys"] = cfg.ssh_keys

    if cfg.has("root") and cfg.disable_root:
        top["disable_root"] = True

    if cfg.has("packages"):
        top["package_update"] = True
        top["package_upgrade"] = cfg.package_upgrade
        if cfg.packages:
            top["packages"] = cfg.packages
        if cfg.package_reboot_if_required:
            top["package_reboot_if_required"] = True

    if cfg.has("locale"):
        top["timezone"] = cfg.timezone
        top["locale"] = cfg.locale
        top["keyboard"] = {"layout": cfg.keyboard_layout}

    if cfg.has("disk") and cfg.grow_device:
        top["growpart"] = {"mode": "auto",
                           "devices": [f"{cfg.grow_device}{cfg.grow_partition}"]}

    # NTP - only set in cloud-init if NOT letting platform handle it
    if cfg.has("ntp") and cfg.ntp_servers and not cfg.let_platform_handle_ntp:
        ntp: Dict[str, Any] = {}
        if cfg.ntp_servers:
            ntp["servers"] = cfg.ntp_servers
        if cfg.ntp_pools:
            ntp["pools"] = cfg.ntp_pools
        top["ntp"] = ntp

    if cfg.has("files") and cfg.write_files:
        top["write_files"] = [
            {"path": f["path"], "content": f["content"],
             "permissions": f.get("permissions", "0644")}
            for f in cfg.write_files
        ]

    # Network - only set in cloud-init if NOT letting platform handle it
    if cfg.has("network") and cfg.net_mode == "static" and cfg.os_type == "windows":
        # Cloudbase-Init applies static netsvc via first-boot; Linux uses cloud-config.
        cmds = [
            f'netsh interface ip set address name="{cfg.net_interface or "Ethernet"}" '
            f'static {cfg.net_address} {cfg.net_netmask} {cfg.net_gateway}'
        ]
        for d in cfg.net_dns:
            cmds.append(f'netsh interface ip add dns name="{cfg.net_interface or "Ethernet"}" '
                        f'{d} index=1')
        if cfg.has("firstboot"):
            cfg.firstboot = cfg.firstboot + cmds
        else:
            cfg.firstboot = cmds
            if "firstboot" not in cfg.modules:
                cfg.modules.append("firstboot")

    if cfg.has("network") and cfg.net_mode == "static" and cfg.os_type == "linux" and not cfg.let_platform_handle_network:
        iface = cfg.net_interface or "eth0"
        eth: Dict[str, Any] = {"dhcp4": False,
                               "addresses": [f"{cfg.net_address}/{_cidr(cfg.net_netmask)}"]}
        if cfg.net_gateway:
            eth["gateway4"] = cfg.net_gateway
        if cfg.net_dns:
            eth["nameservers"] = {"addresses": cfg.net_dns}
            if cfg.net_search:
                eth["nameservers"]["search"] = cfg.net_search
        top["network"] = {"version": 2, "ethernets": {iface: eth}}

    if cfg.has("bootcmd") and cfg.bootcmd:
        top["bootcmd"] = cfg.bootcmd

    if cfg.has("firstboot") and cfg.firstboot:
        top["runcmd"] = cfg.firstboot

    if cfg.has("final") and cfg.final_message:
        top["final_message"] = cfg.final_message

    return "#cloud-config\n" + _render_top(top)


def _render_top(top: Dict[str, Any]) -> str:
    order = [
        "hostname", "users", "disable_root", "ssh_pwauth", "ssh_authorized_keys",
        "package_update", "package_upgrade", "package_reboot_if_required",
        "packages", "timezone", "locale", "keyboard", "growpart", "ntp",
        "write_files", "network", "bootcmd", "runcmd", "final_message",
    ]
    ordered = {k: top[k] for k in order if k in top}
    for k in top:
        if k not in ordered:
            ordered[k] = top[k]
    return yaml_dump(ordered, 0)


def _cidr(netmask: str) -> int:
    try:
        bits = "".join(f"{int(o):08b}" for o in netmask.split("."))
        return bits.count("1")
    except Exception:
        return 24


def build_meta_data(cfg: TemplateConfig) -> str:
    lines = []
    # Only write instance-id if platform is NOT handling hostname
    # When platform handles hostname, it also provides instance-id via metadata service
    if not cfg.use_platform_hostname:
        instance_id = f"iid-{uuid.uuid4().hex[:8]}"
        lines.append(f"instance-id: {instance_id}")
    # Only write local-hostname if platform is NOT handling it
    if not cfg.use_platform_hostname:
        lines.append("local-hostname: " + (cfg.hostname or "cloudseed-vm"))
    return "\n".join(lines) + "\n"


# --- Cloudbase-Init (Windows) ---------------------------------------------

def _ini(conf: Dict[str, str]) -> str:
    return "\n".join(f"{k}: {v}" for k, v in conf.items()) + "\n"


def build_cloudbase_conf(cfg: TemplateConfig, unattend: bool) -> str:
    conf: Dict[str, str] = {}
    if cfg.has("users") and cfg.username:
        from .password import hash_password
        pw = cfg.password
        if not cfg.plaintext_password:
            pw = hash_password(cfg.password, cfg.password_rounds)
        conf["username"] = cfg.username
        conf["password"] = pw
        conf["groups"] = "Administrators"
        conf["first_logon_behaviour"] = "always"
        conf["inject_user_password"] = "True"

    plugins = [
        "cloudbaseinit.plugins.common.sethostname.SetHostNamePlugin",
        "cloudbaseinit.plugins.common.createuser.CreateUserPlugin",
        "cloudbaseinit.plugins.common.setuserpassword.SetUserPasswordPlugin",
        "cloudbaseinit.plugins.common.sshpublickeys.SetUserSSHPublicKeysPlugin",
        "cloudbaseinit.plugins.common.networkconfig.NetworkConfigPlugin",
        "cloudbaseinit.plugins.common.ntpclient.SetNtpClientPlugin",
        "cloudbaseinit.plugins.common.localscripts.LocalScriptsPlugin",
    ]
    conf["plugins"] = ",".join(plugins)
    conf["local_scripts_path"] = (
        "C:\\Program Files\\Cloudbase Solutions\\Cloudbase-Init\\LocalScripts"
    )
    conf["allow_reboot"] = "True"
    conf["metadata_services"] = (
        "cloudbaseinit.metadata.services.configdrive.ConfigDrive"
        if not unattend else
        "cloudbaseinit.metadata.services.winrmconfigdrive.WinRmConfigDrive"
    )
    return _ini(conf)


# --- Windows Sysprep answer file (specialize = new SID) --------------------

def build_sysprep_unattend(cfg: TemplateConfig) -> str:
    if not cfg.sysprep:
        return ""
    pk = f"<ProductKey>{cfg.sysprep_product_key}</ProductKey>" if cfg.sysprep_product_key else ""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend">
  <settings pass="generalize">
    <component name="Microsoft-Windows-PnpSysprep" processorArchitecture="amd64"
               publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/Unattend" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <PersistAllDeviceInstalls>false</PersistAllDeviceInstalls>
      <DoNotCleanUpNonPresentDevices>false</DoNotCleanUpNonPresentDevices>
    </component>
    <component name="Microsoft-Windows-Security-SPP" processorArchitecture="amd64"
               publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/Unattend" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <SkipRearm>1</SkipRearm>
    </component>
  </settings>
  <settings pass="specialize">
    <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64"
               publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/Unattend" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <ComputerName>{cfg.sysprep_computer_prefix}-*</ComputerName>
      <ProductKey>{cfg.sysprep_product_key}</ProductKey>
      <RegisteredOrganization>{cfg.sysprep_organization}</RegisteredOrganization>
      <RegisteredOwner>{cfg.sysprep_owner}</RegisteredOwner>
      <TimeZone>{cfg.sysprep_timezone}</TimeZone>
    </component>
    <component name="Microsoft-Windows-International-Core" processorArchitecture="amd64"
               publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/Unattend" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <UserLocale>{cfg.sysprep_locale}</UserLocale>
      <SystemLocale>{cfg.sysprep_locale}</SystemLocale>
      <UILanguage>{cfg.sysprep_locale}</UILanguage>
      <InputLocale>{cfg.sysprep_locale}</InputLocale>
    </component>
  </settings>
  <settings pass="oobe">
    <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64"
               publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/Unattend" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <OOBE>
        <HideEULAPage>true</HideEULAPage>
        <SkipMachineOOBE>true</SkipMachineOOBE>
        <SkipUserOOBE>true</SkipUserOOBE>
        <ProtectYourPC>3</ProtectYourPC>
      </OOBE>
      <RegisteredOrganization>{cfg.sysprep_organization}</RegisteredOrganization>
      <RegisteredOwner>{cfg.sysprep_owner}</RegisteredOwner>
      <TimeZone>{cfg.sysprep_timezone}</TimeZone>
    </component>
  </settings>
</unattend>
""".replace("<ProductKey></ProductKey>", "<!-- no product key -->")


def build_sysprep_bat(cfg: TemplateConfig) -> str:
    if not cfg.sysprep:
        return ""
    return (
        "@echo off\n"
        "REM CloudSeed Sysprep: generalize VM -> new SID on next boot.\n"
        'set "UNATTEND=%~dp0sysprep-unattend.xml"\n'
        "if not exist \"%UNATTEND%\" (\n"
        "  echo ERROR: sysprep-unattend.xml not found next to this script.\n"
        "  exit /b 1\n"
        ")\n"
        'echo Running Sysprep (generalize + oobe, shutdown)...\n'
        'C:\\Windows\\System32\\sysprep\\sysprep.exe /generalize /oobe /shutdown /unattend:"%UNATTEND%"\n'
    )


# --- vSphere Customization Spec (XML) ---------------------------------------

def build_vsphere_customization_spec(cfg: TemplateConfig) -> str:
    """Generate vSphere Customization Specification XML."""
    if not cfg.export_vsphere_spec or cfg.platform != "vsphere":
        return ""

    # Build hostname section
    hostname_section = ""
    if cfg.use_platform_hostname:
        hostname_section = """      <hostname>
        <type>fixed</type>
        <value></value>
      </hostname>"""
    elif cfg.hostname:
        hostname_section = f"""      <hostname>
        <type>fixed</type>
        <value>{cfg.hostname}</value>
      </hostname>"""
    else:
        hostname_section = f"""      <hostname>
        <type>prefix</type>
        <value>{cfg.hostname_prefix}</value>
      </hostname>"""

    # Build network section
    network_section = ""
    if cfg.let_platform_handle_network:
        network_section = """      <nicSettingMap>
        <adapter>
          <ip>
            <type>dhcp</type>
          </ip>
        </adapter>
      </nicSettingMap>"""
    elif cfg.net_mode == "static" and cfg.net_address:
        network_section = f"""      <nicSettingMap>
        <adapter>
          <ip>
            <type>static</type>
            <ipAddress>{cfg.net_address}</ipAddress>
            <subnetMask>{cfg.net_netmask}</subnetMask>
            <gateway>{cfg.net_gateway}</gateway>
          </ip>
          <dns>
            <ipAddresses>{",".join(cfg.net_dns)}</ipAddresses>
          </dns>
        </adapter>
      </nicSettingMap>"""
    else:
        network_section = """      <nicSettingMap>
        <adapter>
          <ip>
            <type>dhcp</type>
          </ip>
        </adapter>
      </nicSettingMap>"""

    # Build domain section (for Windows)
    domain_section = ""
    if cfg.os_type == "windows":
        domain_section = """      <domain>
        <type>workgroup</type>
        <name>WORKGROUP</name>
      </domain>"""
    else:
        domain_section = """      <domain>
        <type>dns</type>
        <name></name>
      </domain>"""

    # Build time zone
    timezone = cfg.sysprep_timezone if cfg.os_type == "windows" else cfg.timezone

    # Build product key
    product_key = cfg.sysprep_product_key if cfg.os_type == "windows" else ""
    product_key_section = f"""      <productKey>{product_key}</productKey>""" if product_key else """      <productKey></productKey>"""

    spec_name = cfg.vsphere_spec_name or "CloudSeed-Spec"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<CustomizationSpecItem xmlns="urn:vim25" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <spec>
    <name>{spec_name}</name>
    <description>Generated by CloudSeed v{__import__('cloudseed').__version__}</description>
    <type>Linux</type>
    <identity>
{hostname_section}
{domain_section}
      <dnsSuffixList></dnsSuffixList>
    </identity>
    <globalIPSettings>
      <dnsServerList>{",".join(cfg.net_dns)}</dnsServerList>
      <dnsSuffixList></dnsSuffixList>
    </globalIPSettings>
    <nicSettingMap>
{network_section}
    </nicSettingMap>
    <options>
      <customizationTimeout>0</customizationTimeout>
      <reboot>reboot</reboot>
    </options>
  </spec>
  <lastUpdateTime>{__import__('datetime').datetime.now().isoformat()}</lastUpdateTime>
</CustomizationSpecItem>"""


# --- vSphere Pre/Post Customization Scripts ---------------------------------

SAMPLE_PRE_SCRIPT_LINUX = """#!/bin/bash
# CloudSeed vSphere Pre-Customization Script (Linux)
# This script runs BEFORE cloud-init during vSphere guest customization
# Place in: /etc/cloud/cloud.cfg.d/99-cloudseed-pre.cfg or use vSphere customization spec

set -euo pipefail

LOG_FILE="/var/log/cloudseed-pre.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[$(date)] CloudSeed pre-customization started"

# Example: Register with Red Hat Satellite / Foreman
# subscription-manager register --activationkey=<key> --org=<org>

# Example: Install additional agents
# yum install -y <agent-package>

# Example: Configure custom repositories
# cat > /etc/yum.repos.d/custom.repo << 'EOF'
# [custom]
# name=Custom Repository
# baseurl=https://repo.example.com/
# enabled=1
# gpgcheck=0
# EOF

# Example: Set up SSH for remote access before cloud-init
# mkdir -p /root/.ssh
# echo "ssh-rsa AAAA..." > /root/.ssh/authorized_keys
# chmod 600 /root/.ssh/authorized_keys

echo "[$(date)] CloudSeed pre-customization completed"
"""

SAMPLE_PRE_SCRIPT_WINDOWS = r"""@echo off
REM CloudSeed vSphere Pre-Customization Script (Windows)
REM This script runs BEFORE Cloudbase-Init during vSphere guest customization

set LOG_FILE=C:\Windows\Temp\cloudseed-pre.log
echo [%DATE% %TIME%] CloudSeed pre-customization started >> "%LOG_FILE%"

REM Example: Install additional software
REM msiexec /i "https://example.com/agent.msi" /qn

REM Example: Configure Windows features
REM dism /online /enable-feature /featurename:OpenSSH.Server /all /norestart

REM Example: Set up WinRM for remote management
REM winrm quickconfig -q

echo [%DATE% %TIME%] CloudSeed pre-customization completed >> "%LOG_FILE%"
"""

SAMPLE_POST_SCRIPT_LINUX = """#!/bin/bash
# CloudSeed vSphere Post-Customization Script (Linux)
# This script runs AFTER cloud-init completes during vSphere guest customization
# Can be triggered via cloud-init runcmd or systemd service

set -euo pipefail

LOG_FILE="/var/log/cloudseed-post.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[$(date)] CloudSeed post-customization started"

# Example: Join Active Directory domain
# realm join --user=<admin> <domain.com>

# Example: Run compliance checks
# /usr/bin/oscap xccdf eval --profile xccdf_org.ssgproject.content_profile_stig /usr/share/xml/scap/ssg/content/ssg-ubuntu2204-ds.xml

# Example: Register with monitoring
# curl -X POST "https://monitoring.example.com/api/register" -d "hostname=$(hostname)"

# Example: Apply security hardening
# /usr/sbin/aide --init

echo "[$(date)] CloudSeed post-customization completed"
"""

SAMPLE_POST_SCRIPT_WINDOWS = r"""@echo off
REM CloudSeed vSphere Post-Customization Script (Windows)
REM This script runs AFTER Cloudbase-Init completes during vSphere guest customization

set LOG_FILE=C:\Windows\Temp\cloudseed-post.log
echo [%DATE% %TIME%] CloudSeed post-customization started >> "%LOG_FILE%"

REM Example: Join Active Directory domain
REM powershell -Command "Add-Computer -DomainName 'domain.com' -Credential (Get-Credential) -Restart -Force"

REM Example: Run compliance checks
REM powershell -ExecutionPolicy Bypass -File "C:\Compliance\check.ps1"

REM Example: Register with monitoring
REM curl -X POST "https://monitoring.example.com/api/register" -d "hostname=%COMPUTERNAME%"

echo [%DATE% %TIME%] CloudSeed post-customization completed >> "%LOG_FILE%"
"""


def build_vsphere_scripts(cfg: TemplateConfig) -> tuple:
    """Generate vSphere pre/post customization scripts."""
    if not cfg.vsphere_pre_script and not cfg.vsphere_post_script:
        return "", ""

    pre_script = cfg.vsphere_pre_script
    post_script = cfg.vsphere_post_script

    # If using sample scripts, prepend the samples
    if cfg.use_sample_scripts:
        if cfg.os_type == "linux":
            if pre_script:
                pre_script = SAMPLE_PRE_SCRIPT_LINUX + "\n# User customizations:\n" + pre_script
            else:
                pre_script = SAMPLE_PRE_SCRIPT_LINUX
            if post_script:
                post_script = SAMPLE_POST_SCRIPT_LINUX + "\n# User customizations:\n" + post_script
            else:
                post_script = SAMPLE_POST_SCRIPT_LINUX
        else:
            if pre_script:
                pre_script = SAMPLE_PRE_SCRIPT_WINDOWS + "\nREM User customizations:\n" + pre_script
            else:
                pre_script = SAMPLE_PRE_SCRIPT_WINDOWS
            if post_script:
                post_script = SAMPLE_POST_SCRIPT_WINDOWS + "\nREM User customizations:\n" + post_script
            else:
                post_script = SAMPLE_POST_SCRIPT_WINDOWS

    return pre_script, post_script


# --- README ----------------------------------------------------------------

def build_readme(cfg: TemplateConfig, warnings: List[str] = None) -> str:
    plat = "VMware vSphere" if cfg.platform == "vsphere" else "KVM (libvirt)"
    osname = "Linux (cloud-init)" if cfg.os_type == "linux" else "Windows (Cloudbase-Init + Sysprep)"
    lines = [
        "CloudSeed generated configuration",
        "=" * 64,
        f"Platform : {plat}",
        f"Guest OS : {osname}",
        f"Modules  : {', '.join(cfg.modules) or '(none)'}",
        "",
        "Files produced:",
    ]
    if cfg.os_type == "linux":
        lines += [
            "  user-data   - cloud-config customization",
            "  meta-data   - instance identity",
            "  cloudseed.json - this config (re-usable)",
        ]
    else:
        lines += [
            "  cloudbase-init.conf            - main service config",
            "  cloudbase-init-unattend.conf   - unattend-phase config",
            "  sysprep-unattend.xml           - Sysprep answer file (new SID)",
            "  run-sysprep.bat                - launch Sysprep generalize",
            "  cloudseed.json                 - this config (re-usable)",
        ]

    # Add warnings if any
    if warnings:
        lines += ["", "⚠️  Warnings:"]
        for w in warnings:
            lines.append(f"  - {w}")

    lines += ["", "Apply (no ISO) - see GUIDE.md for full steps:"]
    if cfg.platform == "vsphere":
        lines += [
            "  Linux : guestinfo/vApp OR drop into /etc/cloud/cloud.cfg.d/ on image.",
            "  Windows: place .conf in Cloudbase-Init conf dir; run run-sysprep.bat",
            "           BEFORE sealing the template.",
        ]
        # vSphere Customization Spec import guide
        if cfg.export_vsphere_spec:
            lines += [
                "",
                "vSphere Customization Spec Import:",
                "  1. In vCenter, go to Policies and Profiles > Customization Specifications",
                "  2. Click 'Import Specification' and select vsphere-customization-spec.xml",
                "  3. Apply the spec when deploying/cloning VMs",
                "  4. For scripts: pre-script runs before cloud-init, post-script runs after",
            ]
    else:
        lines += [
            "  Linux : virt-install --cloud-init user-data=./user-data,meta-data=./meta-data",
            "          or copy into /etc/cloud/cloud.cfg.d/ on the image.",
            "  Windows: place .conf in Cloudbase-Init conf dir; run run-sysprep.bat",
            "           BEFORE sealing the template.",
        ]
    return "\n".join(lines) + "\n"


def generate_all(cfg: TemplateConfig, out_dir: str, interactive: bool = True) -> List[str]:
    import json as _json

    # Reset overwrite-all state for new generation
    import cloudseed.model as model_mod

    from .cli import validate_config
    from .model import _get_unique_path
    model_mod._overwrite_all_action = None

    # Organize output by platform/OS: e.g., out_dir/vsphere-linux/, out_dir/kvm-windows/, etc.
    plat_name = "vsphere" if cfg.platform == "vsphere" else cfg.platform
    subdir = os.path.join(out_dir, f"{plat_name}-{cfg.os_type}")
    os.makedirs(subdir, exist_ok=True)

    # Check for existing cloudseed.json in the platform/OS subdir (collision detection)
    subdir_json = os.path.join(subdir, "cloudseed.json")
    if os.path.exists(subdir_json):
        print_warn(f"Existing cloudseed.json found in target directory: {subdir_json}")
        print_warn("This may indicate a previous generation for the same platform/OS.")
        if interactive:
            action = _ask_overwrite(subdir_json)
            if action == "skip":
                print_info("Skipping generation to avoid collision.")
                return []
            # If overwrite or suffix, continue (the _get_unique_path will handle it)

    written: List[str] = []

    # Validate and get warnings
    warnings = validate_config(cfg)

    def w(name: str, content: str) -> None:
        if content == "":
            return
        # Get unique path (handles overwrite/suffix/skip)
        unique_path = _get_unique_path(subdir, name)
        if unique_path is None:
            # User chose to skip
            return
        with open(unique_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(unique_path)

    w("user-data", build_user_data(cfg))
    w("meta-data", build_meta_data(cfg))
    if cfg.os_type == "windows":
        w("cloudbase-init.conf", build_cloudbase_conf(cfg, unattend=False))
        w("cloudbase-init-unattend.conf", build_cloudbase_conf(cfg, unattend=True))
        w("sysprep-unattend.xml", build_sysprep_unattend(cfg))
        w("run-sysprep.bat", build_sysprep_bat(cfg))

    # vSphere Customization Spec
    if cfg.export_vsphere_spec and cfg.platform == "vsphere":
        w("vsphere-customization-spec.xml", build_vsphere_customization_spec(cfg))

    # vSphere Pre/Post Customization Scripts
    if cfg.vsphere_pre_script or cfg.vsphere_post_script:
        pre_script, post_script = build_vsphere_scripts(cfg)
        if pre_script:
            w("vsphere-pre-script.sh" if cfg.os_type == "linux" else "vsphere-pre-script.bat", pre_script)
        if post_script:
            w("vsphere-post-script.sh" if cfg.os_type == "linux" else "vsphere-post-script.bat", post_script)

    # Write cloudseed.json to out_dir root (not subdir) for reusability
    # But check if it already exists in the subdir
    root_json = os.path.join(out_dir, "cloudseed.json")
    unique_root_json = _get_unique_path(out_dir, "cloudseed.json")
    if unique_root_json is not None:
        with open(unique_root_json, "w", encoding="utf-8") as fh:
            _json.dump(cfg.to_dict(), fh, indent=2)
        written.append(unique_root_json)
    w("README.txt", build_readme(cfg, warnings))
    return written
