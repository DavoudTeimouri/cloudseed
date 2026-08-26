"""Tests for CloudSeed generators. Stdlib only (pytest)."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cloudseed.model import TemplateConfig
from cloudseed import generate as G


def test_cidr():
    assert G._cidr("255.255.255.0") == 24
    assert G._cidr("255.255.0.0") == 16
    assert G._cidr("255.255.255.128") == 25


def test_module_catalog_covers_os():
    from cloudseed.modules import MODULES
    ids = {m[0] for m in MODULES}
    assert {"hostname", "users", "ssh", "network", "ntp", "sysprep"} <= ids
    sysprep = next(m for m in MODULES if m[0] == "sysprep")
    assert sysprep[2] == ["windows"]        # sysprep linux-only-false
    disk = next(m for m in MODULES if m[0] == "disk")
    assert disk[2] == ["linux"]


def test_linux_full_userdata():
    cfg = TemplateConfig(
        os_type="linux",
        modules=["hostname", "users", "ssh", "root", "network", "packages",
                 "locale", "disk", "ntp", "files", "bootcmd", "firstboot", "final"],
        hostname="web01", username="admin", password="x", ssh_keys=["ssh-rsa AAA"],
        net_mode="static", net_interface="eth0", net_address="192.168.1.50",
        net_netmask="255.255.255.0", net_gateway="192.168.1.1",
        net_dns=["8.8.8.8"], net_search=["example.com"],
        packages=["nginx"], timezone="Europe/Berlin", locale="en_US.UTF-8",
        keyboard_layout="us", ntp_servers=["pool.ntp.org"],
        write_files=[{"path": "/etc/motd", "content": "hi", "permissions": "0644"}],
        bootcmd=["echo boot"], firstboot=["systemctl enable nginx"],
        final_message="ready",
    )
    ud = G.build_user_data(cfg)
    assert ud.startswith("#cloud-config")
    assert "hostname: web01" in ud
    assert "name: admin" in ud
    assert "disable_root: true" in ud
    assert "network:" in ud and "192.168.1.50/24" in ud
    assert "packages:" in ud and "nginx" in ud
    assert "timezone: Europe/Berlin" in ud
    assert "growpart:" in ud
    assert "ntp:" in ud
    assert "write_files:" in ud and "/etc/motd" in ud
    assert "bootcmd:" in ud
    assert "runcmd:" in ud
    assert "final_message: ready" in ud


def test_windows_cloudbase_and_sysprep():
    cfg = TemplateConfig(
        os_type="windows",
        modules=["hostname", "users", "ssh", "network", "ntp", "sysprep", "firstboot"],
        hostname="win01", username="admin", password="p", ssh_keys=["ssh-rsa AAA"],
        ntp_servers=["pool.ntp.org"], sysprep=True,
        sysprep_organization="Acme", sysprep_owner="Admin",
        sysprep_computer_prefix="WIN", sysprep_timezone="W. Europe Standard Time",
        sysprep_locale="en-US",
    )
    main = G.build_cloudbase_conf(cfg, unattend=False)
    unatt = G.build_cloudbase_conf(cfg, unattend=True)
    xml = G.build_sysprep_unattend(cfg)
    bat = G.build_sysprep_bat(cfg)
    assert "username: admin" in main
    assert "CreateUserPlugin" in main
    assert "SetNtpClientPlugin" in main
    assert "WinRmConfigDrive" in unatt
    assert "ConfigDrive" in main
    assert "<ComputerName>WIN-*</ComputerName>" in xml
    assert "Microsoft-Windows-Shell-Setup" in xml
    assert "/generalize" in bat and "/oobe" in bat


def test_sysprep_skipped_when_disabled():
    cfg = TemplateConfig(os_type="windows", modules=["sysprep"], sysprep=False)
    assert G.build_sysprep_unattend(cfg) == ""
    assert G.build_sysprep_bat(cfg) == ""


def test_generate_all_linux_files():
    cfg = TemplateConfig(os_type="linux", modules=["hostname"], hostname="x")
    with tempfile.TemporaryDirectory() as d:
        written = G.generate_all(cfg, d)
        names = {os.path.basename(p) for p in written}
        assert {"user-data", "meta-data", "cloudseed.json", "README.txt"} <= names
        assert not any("sysprep" in n or "cloudbase" in n for n in names)


def test_generate_all_windows_files():
    cfg = TemplateConfig(os_type="windows", modules=["users", "sysprep"],
                         username="admin", password="p", sysprep=True)
    with tempfile.TemporaryDirectory() as d:
        written = G.generate_all(cfg, d)
        names = {os.path.basename(p) for p in written}
        assert "cloudbase-init.conf" in names
        assert "cloudbase-init-unattend.conf" in names
        assert "sysprep-unattend.xml" in names
        assert "run-sysprep.bat" in names


def test_roundtrip_json():
    cfg = TemplateConfig(os_type="linux", modules=["hostname", "users"],
                         hostname="h", username="u")
    d = cfg.to_dict()
    cfg2 = TemplateConfig.from_dict(d)
    assert cfg2.hostname == "h"
    assert cfg2.username == "u"
    assert cfg2.modules == ["hostname", "users"]
