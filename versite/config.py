from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "builder": "mkdocs",
    "remote": "origin",
    "branch": "gh-pages",
    "deploy_prefix": "",
    "alias_type": "redirect",
    "redirect_template": None,
    "push": False,
    "builders": {
        "mkdocs": {
            "command": [
                "mkdocs",
                "build",
                "--clean",
                "--config-file",
                "{config_file}",
                "--site-dir",
                "{output_dir}",
            ],
            "config_file": "mkdocs.yml",
        },
        "jekyll": {
            "command": [
                "bundle",
                "exec",
                "jekyll",
                "build",
                "--source",
                "{source}",
                "--destination",
                "{output_dir}",
            ],
            "source": ".",
        },
    },
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_yaml_config(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("versite config must be a mapping")
    return data


def load_config(path: str | Path | None = None) -> tuple[dict[str, Any], Path | None]:
    config_path = Path(path) if path else Path("versite.yml")
    if config_path.exists():
        return deep_merge(DEFAULT_CONFIG, load_yaml_config(config_path)), config_path
    return deepcopy(DEFAULT_CONFIG), None


def normalize_prefix(prefix: str) -> str:
    prefix = prefix.strip().strip("/")
    if not prefix:
        return ""
    parts = [part for part in prefix.split("/") if part and part != "."]
    if any(part == ".." for part in parts):
        raise ValueError("deploy prefix must not contain '..'")
    return "/".join(parts)


def apply_cli_overrides(
    config: dict[str, Any],
    *,
    builder: str | None = None,
    remote: str | None = None,
    branch: str | None = None,
    message: str | None = None,
    push: bool | None = None,
    deploy_prefix: str | None = None,
    alias_type: str | None = None,
    redirect_template: str | None = None,
    ignore_remote_status: bool | None = None,
    source: str | None = None,
    output_dir: str | None = None,
    build_command: list[str] | None = None,
) -> dict[str, Any]:
    merged = deepcopy(config)
    if builder is not None:
        merged["builder"] = builder
    if remote is not None:
        merged["remote"] = remote
    if branch is not None:
        merged["branch"] = branch
    if message is not None:
        merged["message"] = message
    if push is not None:
        merged["push"] = push
    if deploy_prefix is not None:
        merged["deploy_prefix"] = normalize_prefix(deploy_prefix)
    else:
        merged["deploy_prefix"] = normalize_prefix(merged.get("deploy_prefix", ""))
    if alias_type is not None:
        merged["alias_type"] = alias_type
    if redirect_template is not None:
        merged["redirect_template"] = redirect_template
    if ignore_remote_status is not None:
        merged["ignore_remote_status"] = ignore_remote_status
    if source is not None:
        builder_name = merged["builder"]
        merged.setdefault("builders", {}).setdefault(builder_name, {})
        merged["builders"][builder_name]["source"] = source
    if output_dir is not None:
        merged["output_dir"] = output_dir
    if build_command is not None:
        builder_name = merged["builder"]
        merged.setdefault("builders", {}).setdefault(builder_name, {})
        merged["builders"][builder_name]["command"] = build_command
    return merged
