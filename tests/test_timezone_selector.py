"""Regression tests for hierarchical timezone selection."""

import builtins

from cloudseed.model import _ask_from_list, _ask_timezone


def test_linux_timezone_hierarchy_uses_full_zone_ids(monkeypatch):
    prompts = []
    option_sets = []

    def fake_selector(prompt, default, options, allow_custom=False):
        prompts.append((prompt, default, allow_custom))
        option_sets.append(list(options))
        if len(option_sets) == 1:
            return "Asia"
        return "Asia/Tehran"

    monkeypatch.setattr("cloudseed.model._ask_from_list", fake_selector)

    selected = _ask_timezone("Timezone", default="UTC", os_type="linux")

    assert selected == "Asia/Tehran"
    assert prompts == [
        ("Timezone (region)", "UTC", False),
        ("Timezone (Asia)", "", False),
    ]
    assert "Asia" in option_sets[0]
    assert "Asia/Tehran" in option_sets[1]
    assert "Asia/Dubai" in option_sets[1]
    assert all("/" in value or value == "UTC" for value in option_sets[1])


def test_timezone_hierarchy_preserves_valid_default(monkeypatch):
    prompts = []

    def fake_selector(prompt, default, options, allow_custom=False):
        prompts.append((prompt, default, allow_custom))
        if len(prompts) == 1:
            return "Asia"
        return "Asia/Dubai"

    monkeypatch.setattr("cloudseed.model._ask_from_list", fake_selector)

    selected = _ask_timezone("Timezone", default="Asia/Dubai", os_type="linux")

    assert selected == "Asia/Dubai"
    assert prompts == [
        ("Timezone (region)", "Asia", False),
        ("Timezone (Asia)", "Asia/Dubai", False),
    ]


def test_non_tty_selector_accepts_numbered_selection(monkeypatch):
    replies = iter(["2"])

    def fake_input(prompt=""):
        return next(replies)

    monkeypatch.setattr(builtins, "input", fake_input)

    assert _ask_from_list("Region", "UTC", ["America", "Asia"], allow_custom=False) == "Asia"
