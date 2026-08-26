"""Render a TemplateConfig into cloud-init / Cloudbase-Init files.

Minimal YAML emitter (no PyYAML dependency) sufficient for cloud-config.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .model import TemplateConfig


# --- minimal YAML emitter --------------------------------------------------

def _needs_quote(s: str) -> bool:
    if s == "":
        return True
    unsafe = set("#':{}[],&*?|<>=!%@`\"\\")
    if s[0] in unsafe or s[-1] in unsafe:
        return True
    if any(c in unsafe for c in s):
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
                    lines.append(f"{pad}{k}: {_scalar(v) if not isinstance(v, (dict, list)) else '[]' if isinstance(v, list) else '{}'}")
            else:
                lines.append(f"{pad}{k}: {_scalar(v)}")
    elif isinstance(obj, list):
        if not obj:
            return pad + "[]"
        for item in obj:
            if isinstance(item, (dict, list)):
                body = yaml_dump(item, indent + 1).split("\n")
                # join first line to the "- "
                first = body[0]
                rest = body[1:]
                lines.append(f"{pad}- {first.lstrip()}")
                for r in rest:
                    lines.append(r)
            else:
                lines.append(f"{pad}- {_scalar(item)}")
    else:
        lines.append(f"{pad}{_scalar(obj)}")
    return "\n".join(lines)


# --- cloud-config (user-data) ---------------------------------------------

def build_user_data(cfg: TemplateConfig) -> str:
    top: Dict[str, Any] = {}

    if cfg.has("hostname") and cfg.hostname:
        top["hostname"] = cfg.hostname

    if cfg.has("user") and cfg.username:
        user: Dict[str, Any] = {"name": cfg.username}
        if cfg.os_type == "linux":
            user["groups"] = "sudo"
            if cfg.sudo:
                user["sudo"] = "ALL=(ALL) NOPASSWD:ALL"
        if cfg.lock_password:
            user["lock_passwd"] = True
        else:
            user["passwd"] = cfg.password
            user["lock_passwd"] = False
        if cfg.has("ssh") and cfg.ssh_keys:
            user["ssh_authorized_keys"] = cfg.ssh_keys
        # drop Nones
        user = {k: v for k, v in user.items() if v is not None}
        top["users"] = [user]

    if cfg.has("ssh") and cfg.ssh_keys and not (cfg.has("user") and cfg.username):
        top["ssh_authorized_keys"] = cfg.ssh_keys

    if cfg.has("packages") and cfg.packages:
        top["package_update"] = True
        top["packages"] = cfg.packages

    if cfg.has("timezone") and cfg.timezone:
        top["timezone"] = cfg.timezone

    if cfg.has("growpart") and cfg.grow_device:
        top["growpart"] = {
            "mode": "auto",
            "devices": [f"{cfg.grow_device}{cfg.grow_partition}"],
        }

    if cfg.has("ntp") and cfg.ntp_servers:
        top["ntp"] = {"servers": cfg.ntp_servers}

    if cfg.has("network") and cfg.net_mode == "static":
        net: Dict[str, Any] = {
            "version": 2,
            "ethernets": {
                (cfg.net_interface or "eth0"): {
                    "dhcp4": False,
                    "addresses": [f"{cfg.net_address}/{_cidr(cfg.net_netmask)}"],
                    "gateway4": cfg.net_gateway,
                }
            },
        }
        if cfg.net_dns:
            net["ethernets"][cfg.net_interface or "eth0"]["nameservers"] = {
                "addresses": cfg.net_dns
            }
        top["network"] = net

    if cfg.has("firstboot") and cfg.firstboot:
        top["runcmd"] = cfg.firstboot

    return "#cloud-config\n" + _render_top(top)


def _render_top(top: Dict[str, Any]) -> str:
    # stabilize key order: known cloud-init ordering
    order = [
        "hostname", "users", "ssh_authorized_keys", "package_update",
        "packages", "timezone", "growpart", "ntp", "network", "runcmd",
    ]
    ordered = {k: top[k] for k in order if k in top}
    for k in top:
        if k not in ordered:
            ordered[k] = top[k]
    return yaml_dump(ordered, 0)


def _cidr(netmask: str) -> int:
    # convert dotted netmask to prefix length
    try:
        bits = "".join(f"{int(o):08b}" for o in netmask.split("."))
        return bits.count("1")
    except Exception:
        return 24


def build_meta_data(cfg: TemplateConfig) -> str:
    lines = ["instance-id: iid-cloudseed", "local-hostname: " +
             (cfg.hostname or "cloudseed-vm")]
    if cfg.has("network") and cfg.net_mode == "static":
        # meta-data can carry static network for NoCloud
        lines.append("network-interfaces: |")
        iface = cfg.net_interface or "eth0"
        lines.append(f"  auto {iface}")
        lines.append(f"  iface {iface} inet static")
        lines.append(f"    address {cfg.net_address}")
        lines.append(f"    netmask {cfg.net_netmask}")
        lines.append(f"    gateway {cfg.net_gateway}")
        for dns in cfg.net_dns:
            lines.append(f"    dns-nameservers {dns}")
    return "\n".join(lines) + "\n"


# --- Cloudbase-Init (Windows) ---------------------------------------------

def _ini(conf: Dict[str, str]) -> str:
    out = ["[DEFAULT]"]
    # preserve given key order
    for k, v in conf.items():
        out.append(f"{k}: {v}")
    return "\n".join(out) + "\n"


def build_cloudbase_conf(cfg: TemplateConfig, unattend: bool) -> str:
    conf: Dict[str, str] = {}
    if cfg.has("user") and cfg.username:
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
    if unattend:
        conf["metadata_services"] = (
            "cloudbaseinit.metadata.services.winrmconfigdrive.WinRmConfigDrive"
        )
    else:
        conf["metadata_services"] = (
            "cloudbaseinit.metadata.services.configdrive.ConfigDrive"
        )
    return _ini(conf)


# --- README ----------------------------------------------------------------

def build_readme(cfg: TemplateConfig) -> str:
    plat = "VMware vSphere" if cfg.platform == "vsphere" else "KVM (libvirt)"
    osname = "Linux (cloud-init)" if cfg.os_type == "linux" else "Windows (Cloudbase-Init)"
    lines = [
        "cloudseed generated template",
        "============================",
        f"Platform : {plat}",
        f"Guest OS : {osname}",
        f"Modules  : {', '.join(cfg.modules) or '(none)'}",
        "",
        "Files produced:",
    ]
    if cfg.os_type == "linux":
        lines += [
            "  user-data   - cloud-config customization",
            "  meta-data   - instance identity / network",
        ]
    else:
        lines += [
            "  user-data   - cloud-config (consumed by Cloudbase-Init cloudconfig plugin)",
            "  meta-data   - instance identity",
            "  cloudbase-init.conf            - main service config",
            "  cloudbase-init-unattend.conf   - unattend-phase config",
        ]

    lines += ["", "Apply on " + plat + ":"]
    if cfg.platform == "vsphere":
        lines += [
            "  1. Build a config-drive ISO from user-data + meta-data:",
            "       mkisofs -o seed.iso -V cidata -J -r user-data meta-data",
            "  2. Attach seed.iso as a CD-ROM to the VM before first boot.",
            "     (For Windows, also place the two .conf files into",
            "      C:\\Program Files\\Cloudbase Solutions\\Cloudbase-Init\\conf\\"
            "      before sealing the template.)",
        ]
    else:  # kvm
        lines += [
            "  Linux:",
            "    virt-install --cloud-init user-data=./user-data,meta-data=./meta-data ...",
            "  or build a NoCloud seed ISO:",
            "    mkisofs -o seed.iso -V cidata -J -r user-data meta-data",
            "    virsh attach-disk <domain> seed.iso --target sdc --type cdrom",
            "  Windows: place the two .conf files into",
            "    C:\\Program Files\\Cloudbase Solutions\\Cloudbase-Init\\conf\\"
            "    and provide user-data/meta-data via a config-drive ISO.",
        ]
    return "\n".join(lines) + "\n"


def generate_all(cfg: TemplateConfig, out_dir: str) -> List[str]:
    import os

    os.makedirs(out_dir, exist_ok=True)
    written: List[str] = []

    def w(name: str, content: str) -> None:
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(path)

    w("user-data", build_user_data(cfg))
    w("meta-data", build_meta_data(cfg))
    if cfg.os_type == "windows":
        w("cloudbase-init.conf", build_cloudbase_conf(cfg, unattend=False))
        w("cloudbase-init-unattend.conf", build_cloudbase_conf(cfg, unattend=True))
    w("README.txt", build_readme(cfg))
    return written
