"""Render a TemplateConfig into cloud-init / Cloudbase-Init / Sysprep files.

Config-only output: no ISO is produced. Minimal YAML emitter (no PyYAML).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from .model import TemplateConfig


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
                if isinstance(v, dict) and v:
                    lines.append(f"{pad}{k}:")
                    lines.append(yaml_dump(v, indent + 1))
                elif isinstance(v, list) and v:
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

    if cfg.has("hostname") and cfg.hostname:
        top["hostname"] = cfg.hostname

    if cfg.has("users") and cfg.username:
        user: Dict[str, Any] = {"name": cfg.username, "groups": "sudo" if cfg.sudo else None}
        if cfg.sudo:
            user["sudo"] = "ALL=(ALL) NOPASSWD:ALL"
        user["lock_passwd"] = cfg.lock_password
        if not cfg.lock_password:
            user["passwd"] = cfg.password
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

    if cfg.has("ntp") and cfg.ntp_servers:
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

    if cfg.has("network") and cfg.net_mode == "static":
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
    lines = ["instance-id: iid-cloudseed",
             "local-hostname: " + (cfg.hostname or "cloudseed-vm")]
    return "\n".join(lines) + "\n"


# --- Cloudbase-Init (Windows) ---------------------------------------------

def _ini(conf: Dict[str, str]) -> str:
    return "\n".join(f"{k}: {v}" for k, v in conf.items()) + "\n"


def build_cloudbase_conf(cfg: TemplateConfig, unattend: bool) -> str:
    conf: Dict[str, str] = {}
    if cfg.has("users") and cfg.username:
        conf["username"] = cfg.username
        conf["password"] = cfg.password
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


# --- README ----------------------------------------------------------------

def build_readme(cfg: TemplateConfig) -> str:
    plat = "VMware vSphere" if cfg.platform == "vsphere" else "KVM (libvirt)"
    osname = "Linux (cloud-init)" if cfg.os_type == "linux" else "Windows (Cloudbase-Init + Sysprep)"
    lines = [
        "CloudSeed generated configuration (NO ISO -- config files only)",
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
    lines += ["", "Apply (no ISO) - see GUIDE.md for full steps:"]
    if cfg.platform == "vsphere":
        lines += [
            "  Linux : guestinfo/vApp OR drop into /etc/cloud/cloud.cfg.d/ on image.",
            "  Windows: place .conf in Cloudbase-Init conf dir; run run-sysprep.bat",
            "           BEFORE sealing the template.",
        ]
    else:
        lines += [
            "  Linux : virt-install --cloud-init user-data=./user-data,meta-data=./meta-data",
            "          or copy into /etc/cloud/cloud.cfg.d/ on the image.",
            "  Windows: place .conf in Cloudbase-Init conf dir; run run-sysprep.bat",
            "           BEFORE sealing the template.",
        ]
    return "\n".join(lines) + "\n"


def generate_all(cfg: TemplateConfig, out_dir: str) -> List[str]:
    import json as _json
    os.makedirs(out_dir, exist_ok=True)
    written: List[str] = []

    def w(name: str, content: str) -> None:
        if content == "":
            return
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(path)

    w("user-data", build_user_data(cfg))
    w("meta-data", build_meta_data(cfg))
    if cfg.os_type == "windows":
        w("cloudbase-init.conf", build_cloudbase_conf(cfg, unattend=False))
        w("cloudbase-init-unattend.conf", build_cloudbase_conf(cfg, unattend=True))
        w("sysprep-unattend.xml", build_sysprep_unattend(cfg))
        w("run-sysprep.bat", build_sysprep_bat(cfg))
    with open(os.path.join(out_dir, "cloudseed.json"), "w", encoding="utf-8") as fh:
        _json.dump(cfg.to_dict(), fh, indent=2)
    written.append(os.path.join(out_dir, "cloudseed.json"))
    w("README.txt", build_readme(cfg))
    return written
