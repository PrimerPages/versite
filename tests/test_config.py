from __future__ import annotations

from pathlib import Path

from versite.config import DEFAULT_CONFIG, apply_cli_overrides, load_config


def test_load_defaults_without_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config, path = load_config()
    assert path is None
    assert config["remote"] == DEFAULT_CONFIG["remote"]


def test_load_config_file(tmp_path: Path) -> None:
    config_file = tmp_path / "versite.yml"
    config_file.write_text("branch: docs\npush: true\n", encoding="utf-8")
    config, path = load_config(config_file)
    assert path == config_file
    assert config["branch"] == "docs"
    assert config["push"] is True


def test_cli_overrides_deploy_values() -> None:
    config = apply_cli_overrides(
        DEFAULT_CONFIG,
        branch="pages",
        deploy_prefix="docs",
        remote="upstream",
    )
    assert config["branch"] == "pages"
    assert config["deploy_prefix"] == "docs"
    assert config["remote"] == "upstream"
