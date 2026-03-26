"""Tests for CLI entry points and installer helpers."""

import os
from types import SimpleNamespace

import pytest

from vit import cli


def test_default_clone_dest_removes_literal_git_suffix():
    assert cli._default_clone_dest("https://github.com/org/repo.git") == "repo"
    assert cli._default_clone_dest("https://github.com/org/widget") == "widget"


def test_install_premiere_rejects_non_macos(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys, "platform", "linux")

    with pytest.raises(SystemExit) as excinfo:
        cli.cmd_install_premiere(SimpleNamespace())

    assert excinfo.value.code == 1
    assert "macOS only" in capsys.readouterr().out


def test_install_premiere_uses_plugin_dir_and_saves_package_path(tmp_path, monkeypatch, capsys):
    plugin_dir = tmp_path / "premiere_plugin"
    plugin_dir.mkdir()
    cep_dir = tmp_path / "cep"
    calls = []

    monkeypatch.setattr(cli.sys, "platform", "darwin")
    monkeypatch.setattr(cli, "PREMIERE_CEP_DIR", str(cep_dir))
    monkeypatch.setattr(cli, "_find_plugin_dir", lambda name: (str(tmp_path), str(plugin_dir)))
    monkeypatch.setattr(cli, "_save_package_path", lambda package_dir: calls.append(("save", package_dir)))
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda args, capture_output, text: calls.append(("defaults", tuple(args))),
    )

    cli.cmd_install_premiere(SimpleNamespace())

    dest = cep_dir / cli.PREMIERE_EXTENSION_ID
    assert dest.is_symlink()
    assert os.readlink(dest) == str(plugin_dir)
    assert ("save", str(tmp_path)) in calls
    assert sum(1 for call in calls if call[0] == "defaults") == 3
    assert "Installed Premiere extension" in capsys.readouterr().out
