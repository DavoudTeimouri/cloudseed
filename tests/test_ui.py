"""Regression tests for CloudSeed banner and module selector."""

import builtins

from cloudseed.model import _choose_module_multi, print_banner


def test_banner_names_application_without_host_platform(capsys):
    print_banner("Main Menu", modules_count=3)

    output = capsys.readouterr().out
    assert "CloudSeed" in output
    assert "_____ _" in output
    assert "Platform:" not in output
    assert "OS:" not in output


def test_module_selector_numbered_toggle_enter_confirms(monkeypatch, capsys):
    """Numbered input toggles; Enter confirms."""
    replies = iter(["1", ""])  # toggle first module, then Enter (empty -> confirm)

    def fake_input(prompt=""):
        return next(replies)

    monkeypatch.setattr(builtins, "input", fake_input)

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


def test_module_selector_multi_digit_number(monkeypatch, capsys):
    """Modules 10+ selectable via multi-digit numbers."""
    modules = [(f"mod{i}", f"Module {i}") for i in range(1, 12)]
    replies = iter(["10", ""])  # select module 10, then Enter

    def fake_input(prompt=""):
        return next(replies)

    monkeypatch.setattr(builtins, "input", fake_input)

    selected = _choose_module_multi(
        "Module Selection",
        modules,
        [],
        "physical",
        "linux",
    )

    assert selected == ["mod10"]


def test_module_selector_conflict_toggle(monkeypatch, capsys):
    """Platform module auto-disables cloud-init equivalent."""
    modules = [("platform_hostname", "Platform Hostname"), ("hostname", "Set Hostname")]
    replies = iter(["1", ""])  # toggle platform_hostname, then Enter

    def fake_input(prompt=""):
        return next(replies)

    monkeypatch.setattr(builtins, "input", fake_input)

    selected = _choose_module_multi(
        "Module Selection",
        modules,
        [],
        "vsphere",
        "linux",
    )

    output = capsys.readouterr().out
    assert selected == ["platform_hostname"]
    assert "conflict!" in output


def test_module_selector_eof_handling(monkeypatch, capsys):
    """EOF on stdin returns empty selection gracefully."""
    def fake_input(prompt=""):
        raise EOFError

    monkeypatch.setattr(builtins, "input", fake_input)

    selected = _choose_module_multi(
        "Module Selection",
        [("hostname", "Set Hostname")],
        [],
        "physical",
        "linux",
    )

    # Should return BACK on EOF
    assert selected == "BACK"
