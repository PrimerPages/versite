from __future__ import annotations

import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from versite.cli import main


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _properties(repo: Path) -> dict:
    records = json.loads(_git(repo, "show", "gh-pages:versions.json"))
    return next(record["properties"] for record in records if record["version"] == "1.0")


@pytest.mark.parametrize("operation", ["set", "set-all"])
def test_set_json_values(git_repo: Path, operation: str) -> None:
    value = {"hidden": True, "tags": ["stable", "supported"], "count": 2, "url": None}
    raw = json.dumps(value)
    options = ["--set-all", raw] if operation == "set-all" else ["--set", f"metadata={raw}"]

    assert main(["props", "latest", *options]) == 0

    expected = value if operation == "set-all" else {"channel": "stable", "metadata": value}
    assert _properties(git_repo) == expected


@pytest.mark.parametrize("source", ["file", "environment"])
def test_shell_can_supply_json_from_files_or_ci_variables(git_repo: Path, source: str) -> None:
    source_root = str(Path(__file__).resolve().parents[1])
    value = {"hidden": False, "channel": "ci"}
    settings = git_repo / "property settings.json"
    settings.write_text(json.dumps(value))
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([source_root, os.environ.get("PYTHONPATH", "")]),
        "PROPERTIES_JSON": json.dumps(value),
    }
    command = '"$1" -m versite.cli props 1.0 --set-all '
    command += '"$(cat "$2")"' if source == "file" else '"$PROPERTIES_JSON"'
    result = subprocess.run(
        ["bash", "-c", command, "versite-shell-test", sys.executable, str(settings)],
        cwd=git_repo, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert _properties(git_repo) == value


def test_property_edits_apply_in_order_with_one_commit_and_push(git_repo: Path, monkeypatch) -> None:
    previous = _git(git_repo, "rev-parse", "gh-pages")
    pushes = []
    monkeypatch.setattr("versite.commands.push_branch", lambda *args: pushes.append(args))

    assert main([
        "props", "1.0", "--set-all", '{"old": true}',
        "--set", "temporary=1", "--delete", "old",
        "--delete-all", "--set", "hidden=false", "--set-string", "label=true", "--push",
    ]) == 0

    assert _properties(git_repo) == {"hidden": False, "label": "true"}
    assert _git(git_repo, "rev-list", "--count", f"{previous}..gh-pages") == "1"
    assert len(pushes) == 1


@pytest.mark.parametrize("value", [" true ", "@settings.json", "-", "null", "001"])
def test_set_string_preserves_literal_values(git_repo: Path, value: str) -> None:
    assert main(["props", "1.0", "--set-string", f"label={value}"]) == 0
    assert _properties(git_repo)["label"] == value


def test_metadata_property_edits_and_reads(git_repo: Path, capsys) -> None:
    assert main(["props", "1.0", "--set", 'metadata={"hidden":true}']) == 0
    assert main(["props", "1.0", "--set-string", "label=stable"]) == 0
    assert main(["props", "1.0", "--delete", "channel"]) == 0
    assert _properties(git_repo) == {"metadata": {"hidden": True}, "label": "stable"}
    capsys.readouterr()
    previous = _git(git_repo, "rev-parse", "gh-pages")
    assert main(["props", "latest", "metadata.hidden", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) is True
    assert _git(git_repo, "rev-parse", "gh-pages") == previous


def test_delete_flag_handles_property_names_ending_in_a_dash(git_repo: Path) -> None:
    assert main(["props", "1.0", "--set", "old-=true"]) == 0
    assert main(["props", "1.0", "old-", "--json"]) == 0
    assert _properties(git_repo)["old-"] is True
    assert main(["props", "1.0", "--delete", "old-"]) == 0
    assert _properties(git_repo) == {"channel": "stable"}


@pytest.mark.parametrize("options", [
    ["--set", "hidden=not-json"],
    ["--set", "=true"],
    ["--set", "missing-assignment"],
    ["--set-all", "{broken}"],
    ["--set-all", "[]"],
    ["--set-all", "null"],
    ["--set-all", "@missing.json"],
    ["--set-all", "@invalid.json"],
    ["--set", "hidden=true", "--delete", "missing"],
    ["--delete", ""],
    ["channel", "--set", "hidden=true"],
    ["hidden=true"],
    ["channel=stable"],
    ["metadata.hidden=true"],
    ["channel-"],
    ["metadata=not-json"],
    ['metadata={"hidden":true}'],
    ["metadata=@invalid.json"],
    ["metadata=-"],
])
def test_invalid_property_edits_leave_deployed_metadata_unchanged(
    git_repo: Path, options: list[str], capsys,
) -> None:
    (git_repo / "invalid.json").write_text("not json")
    previous = _git(git_repo, "rev-parse", "gh-pages")
    assert main(["props", "1.0", *options]) == 1
    assert "versite:" in capsys.readouterr().err
    assert _git(git_repo, "rev-parse", "gh-pages") == previous
    assert _properties(git_repo) == {"channel": "stable"}


@pytest.mark.parametrize("options", [
    ["--set-all", "@properties.json"],
    ["--set", "metadata=@properties.json"],
    ["--set-all", "-"],
    ["--set", "metadata=-"],
])
def test_property_values_do_not_read_files_or_stdin(
    git_repo: Path, monkeypatch, options: list[str],
) -> None:
    (git_repo / "properties.json").write_text('{"hidden": true}')
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"hidden": true}'))
    previous = _git(git_repo, "rev-parse", "gh-pages")
    assert main(["props", "1.0", *options]) == 1
    assert _git(git_repo, "rev-parse", "gh-pages") == previous
    assert _properties(git_repo) == {"channel": "stable"}
