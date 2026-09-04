"""Tests for CloudSeed validator, doctor, templatemaker, toolbox. Stdlib + pytest."""

import os
import sys
import tempfile
import json
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cloudseed import validator as V
from cloudseed import doctor as D
from cloudseed import templatemaker as T
from cloudseed import toolbox as TB


class TestValidator:
    """Tests for config validator."""

    def test_validate_no_persistent_runs_clean(self):
        """Clean user-data passes validation."""
        with tempfile.TemporaryDirectory() as d:
            user_data = Path(d) / "user-data"
            user_data.write_text("#cloud-config\nhostname: test\n")
            warnings = V.validate_no_persistent_runs(d)
            assert isinstance(warnings, list)

    def test_validate_no_persistent_runs_bootcmd_warning(self):
        """bootcmd triggers warning."""
        with tempfile.TemporaryDirectory() as d:
            user_data = Path(d) / "user-data"
            user_data.write_text("#cloud-config\nbootcmd: [echo hello]\n")
            warnings = V.validate_no_persistent_runs(d)
            assert any("bootcmd" in w for w in warnings)

    def test_validate_no_persistent_runs_runcmd_warning(self):
        """runcmd triggers warning."""
        with tempfile.TemporaryDirectory() as d:
            user_data = Path(d) / "user-data"
            user_data.write_text("#cloud-config\nruncmd: [systemctl enable nginx]\n")
            warnings = V.validate_no_persistent_runs(d)
            assert any("runcmd" in w for w in warnings)

    def test_validate_cloudseed_json_missing(self):
        """Missing cloudseed.json is not an error."""
        with tempfile.TemporaryDirectory() as d:
            warnings = V.validate_cloudseed_json(d)
            assert warnings == []

    def test_validate_cloudseed_json_invalid(self):
        """Invalid JSON triggers warning."""
        with tempfile.TemporaryDirectory() as d:
            json_path = Path(d) / "cloudseed.json"
            json_path.write_text("{ invalid }")
            warnings = V.validate_cloudseed_json(d)
            assert any("invalid JSON" in w for w in warnings)

    def test_validate_cloudseed_json_missing_fields(self):
        """Missing required fields triggers warning."""
        with tempfile.TemporaryDirectory() as d:
            json_path = Path(d) / "cloudseed.json"
            json_path.write_text("{}")
            warnings = V.validate_cloudseed_json(d)
            assert any("missing field" in w for w in warnings)

    def test_validate_windows_config_missing_sysprep(self):
        """Missing sysprep files triggers warning."""
        with tempfile.TemporaryDirectory() as d:
            warnings = V.validate_windows_config(d)
            assert any("sysprep-unattend.xml not found" in w for w in warnings)


class TestDoctor:
    """Tests for cloud-init doctor."""

    def test_run_cmd_success(self):
        """run_cmd returns tuple."""
        rc, out, err = D.run_cmd(["echo", "hello"])
        assert rc == 0
        assert "hello" in out
        assert err == ""

    def test_run_cmd_not_found(self):
        """run_cmd handles missing command."""
        rc, out, err = D.run_cmd(["this_command_does_not_exist_12345"])
        assert rc == -1
        assert "not found" in err.lower()

    def test_check_disk_space_linux(self):
        """check_disk_space returns dict with expected keys."""
        info = D.check_disk_space()
        assert "partitions" in info
        assert "warnings" in info
        assert "errors" in info

    def test_diagnose_all_returns_structure(self):
        """diagnose_all returns expected structure."""
        results = D.diagnose_all()
        assert "timestamp" in results
        assert "platform" in results
        assert "cloud_init" in results
        assert "cloud_config" in results
        assert "boot" in results
        assert "network" in results
        assert "disk" in results


class TestTemplateMaker:
    """Tests for template maker."""

    def test_detect_os(self):
        """detect_os returns linux or windows."""
        os_type = T.detect_os()
        assert os_type in ("linux", "windows", "unknown")

    def test_is_admin(self):
        """is_admin returns bool."""
        result = T.is_admin()
        assert isinstance(result, bool)

    def test_generate_cleanup_script_linux(self):
        """Generates Linux cleanup script."""
        with tempfile.TemporaryDirectory() as d:
            old_cwd = os.getcwd()
            os.chdir(d)
            try:
                result = T.generate_cleanup_script("linux")
                assert result is True
                script = Path(d) / "cloudseed-template-cleanup-linux.sh"
                assert script.exists()
                content = script.read_text()
                assert "cloud-init clean" in content
                assert "machine-id" in content
            finally:
                os.chdir(old_cwd)

    def test_generate_cleanup_script_windows(self):
        """Generates Windows cleanup script."""
        with tempfile.TemporaryDirectory() as d:
            old_cwd = os.getcwd()
            os.chdir(d)
            try:
                result = T.generate_cleanup_script("windows")
                assert result is True
                script = Path(d) / "cloudseed-template-cleanup-windows.bat"
                assert script.exists()
                content = script.read_text()
                assert "wevtutil" in content
                assert "Sysprep" in content
            finally:
                os.chdir(old_cwd)

    def test_show_best_practices_no_crash(self):
        """show_best_practices runs without error."""
        T.show_best_practices("linux", "vsphere")
        T.show_best_practices("windows", "kvm")


class TestToolbox:
    """Tests for toolbox."""

    def test_show_cloud_init_compat_no_crash(self, monkeypatch):
        """show_cloud_init_compat runs without error."""
        monkeypatch.setattr('builtins.input', lambda _: '')
        TB.show_cloud_init_compat()

    def test_show_sid_tool_info_no_crash(self, monkeypatch):
        """show_sid_tool_info runs without error."""
        monkeypatch.setattr('builtins.input', lambda _: '')
        TB.show_sid_tool_info()

    def test_show_sysprep_guidance_no_crash(self, monkeypatch):
        """show_sysprep_guidance runs without error."""
        monkeypatch.setattr('builtins.input', lambda _: '')
        TB.show_sysprep_guidance()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
