"""Tests for cloudseed generators. Stdlib only (pytest)."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cloudseed.model import TemplateConfig, MODULES
from cloudseed import generate as G


def test_cidr():
    assert G._cidr("255.255.255.0") == 24
    assert G._cidr("255.255.0.0") == 16
    assert G._cidr("255.255.255.128") == 25


def test_module_list_has_linux_and_windows():
    ids = {m["id"] for m in MODULES}
    assert {"hostname", "user", "ssh", "network"} <= ids
    # packages/growpart linux-only, ntp/ssh both
    pk = next(m for m in MODULES if m["id"] == "packages")
    assert pk["os"] == ["linux"]


def test_linux_dhcp_basic_userdata():
    cfg = TemplateConfig(
        platform="kvm", os_type="linux",
        modules=["hostname", "user", "ssh"],
        hostname="web01",
        username="admin",
        password="x",
        ssh_keys=["ssh-rsa AAA"],
    )
    ud = G.build_user_data(cfg)
    assert ud.startswith("#cloud-config")
    assert "hostname: web01" in ud
    assert "name: admin" in ud
    assert "ssh_authorized_keys" in ud
    assert "ssh-rsa AAA" in ud


def test_linux_static_network_emits_netplan():
    cfg = TemplateConfig(
        platform="vsphere", os_type="linux",
        modules=["network"],
        net_mode="static",
        net_interface="eth0",
        net_address="192.168.1.50",
        net_netmask="255.255.255.0",
        net_gateway="192.168.1.1",
        net_dns=["8.8.8.8"],
    )
    ud = G.build_user_data(cfg)
    assert "version: 2" in ud
    assert "192.168.1.50/24" in ud
    assert "gateway4: 192.168.1.1" in ud
    assert "8.8.8.8" in ud


def test_windows_cloudbase_conf():
    cfg = TemplateConfig(
        platform="vsphere", os_type="windows",
        modules=["hostname", "user", "ntp"],
        hostname="win01",
        username="admin",
        password="p",
        ntp_servers=["pool.ntp.org"],
    )
    main = G.build_cloudbase_conf(cfg, unattend=False)
    unatt = G.build_cloudbase_conf(cfg, unattend=True)
    assert "username: admin" in main
    assert "CreateUserPlugin" in main
    assert "SetNtpClientPlugin" in main
    assert "WinRmConfigDrive" in unatt
    assert "ConfigDrive" in main


def test_generate_all_linux_writes_files():
    cfg = TemplateConfig(
        platform="kvm", os_type="linux", modules=["hostname"], hostname="x"
    )
    with tempfile.TemporaryDirectory() as d:
        written = G.generate_all(cfg, d)
        names = {os.path.basename(p) for p in written}
        assert {"user-data", "meta-data", "README.txt"} <= names
        assert not any("cloudbase" in n for n in names)


def test_generate_all_windows_writes_conf():
    cfg = TemplateConfig(
        platform="vsphere", os_type="windows", modules=["user"],
        username="admin", password="p"
    )
    with tempfile.TemporaryDirectory() as d:
        written = G.generate_all(cfg, d)
        names = {os.path.basename(p) for p in written}
        assert "cloudbase-init.conf" in names
        assert "cloudbase-init-unattend.conf" in names


def test_meta_data_static_network():
    cfg = TemplateConfig(
        platform="vsphere", os_type="linux", modules=["network"],
        net_mode="static", net_interface="ens3",
        net_address="10.0.0.5", net_netmask="255.255.255.0",
        net_gateway="10.0.0.1", net_dns=["10.0.0.2"],
    )
    md = G.build_meta_data(cfg)
    assert "network-interfaces:" in md
    assert "address 10.0.0.5" in md


def test_roundtrip_json():
    cfg = TemplateConfig(os_type="linux", modules=["hostname"], hostname="h")
    d = cfg.to_dict()
    cfg2 = TemplateConfig.from_dict(d)
    assert cfg2.hostname == "h"
    assert cfg2.modules == ["hostname"]
