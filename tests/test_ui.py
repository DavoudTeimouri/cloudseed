"""Regression tests for CloudSeed banner and module selector."""

from cloudseed.model import _choose_module_multi, print_banner


def test_banner_names_application_without_host_platform(capsys):
    print_banner("Main Menu", modules_count=3)

    output = capsys.readouterr().out
    assert "CloudSeed" in output
    assert "_____ _" in output
    assert "Platform:" not in output
    assert "OS:" not in output


def test_module_selector_space_toggles_highlighted_module(monkeypatch, capsys):
    replies = iter([" ", "c"])

    def fake_key(prompt=""):
        return next(replies)

    monkeypatch.setattr("cloudseed.model._read_key", fake_key)

    selected = _choose_module_multi(
        "Module Selection",
        [("hostname", "Set Hostname"), ("users", "Create Admin User")],
        [],
        "physical",
        "linux",
    )

    output = capsys.readouterr().out
    assert selected == ["hostname"]
    assert "Target: Physical / Linux" in output
    assert "Platform:" not in output
    assert "OS:" not in output
