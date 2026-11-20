from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from versite.cli import main


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _record(repo: Path, version: str, prefix: str = "") -> dict:
    manifest = str(Path(prefix) / "versions.json")
    records = json.loads(_git(repo, "show", f"gh-pages:{manifest}"))
    return next(record for record in records if record["version"] == version)


@pytest.fixture
def built_site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("Updated content")
    return site


@pytest.mark.parametrize("version", ["1.0", "2.0"])
@pytest.mark.parametrize("title", ["Supported release", ""])
def test_deploy_content_title_and_properties_in_one_commit_and_push(
    git_repo: Path, built_site: Path, monkeypatch, version: str, title: str,
) -> None:
    previous = _git(git_repo, "rev-parse", "gh-pages")
    pushed = []

    def push(*args):
        pushed.append(_git(git_repo, "rev-parse", "gh-pages"))
        assert _record(git_repo, version)["title"] == title
        assert _git(git_repo, "show", f"gh-pages:{version}/index.html") == "Updated content"

    monkeypatch.setattr("versite.commands.push_branch", push)
    assert main([
        "deploy", version, "latest", "--site-dir", str(built_site), "--title", title,
        "--prop-set-all", '{"old":true}', "--prop-set", "temporary=1",
        "--prop-delete", "old", "--prop-delete-all", "--prop-set", "hidden=false",
        "--prop-set-string", "channel=stable", "--push",
    ]) == 0

    record = _record(git_repo, version)
    assert record["title"] == title
    assert record["aliases"] == ["latest"]
    assert record["properties"] == {"hidden": False, "channel": "stable"}
    assert _git(git_repo, "rev-list", "--count", f"{previous}..gh-pages") == "1"
    assert pushed == [_git(git_repo, "rev-parse", "gh-pages")]
    if version == "2.0":
        assert _record(git_repo, "1.0")["properties"] == {"channel": "stable"}


@pytest.mark.parametrize(("options", "expected"), [
    (["--prop-set", "hidden=true"], {"channel": "stable", "hidden": True}),
    (["--prop-set-string", "label=true"], {"channel": "stable", "label": "true"}),
    (["--prop-delete", "channel"], {}),
    (["--prop-set-all", '{"supported":false}'], {"supported": False}),
    (["--prop-delete-all"], {}),
])
def test_deploy_property_operations(
    git_repo: Path, built_site: Path, options: list[str], expected: dict,
) -> None:
    assert main(["deploy", "1.0", "--site-dir", str(built_site), *options]) == 0
    assert _record(git_repo, "1.0")["properties"] == expected


def test_redeploy_preserves_title_and_properties_without_metadata_flags(
    git_repo: Path, built_site: Path,
) -> None:
    assert main(["retitle", "1.0", "Supported release"]) == 0
    assert main(["props", "1.0", "--set", "hidden=false"]) == 0
    previous = _record(git_repo, "1.0")

    assert main(["deploy", "1.0", "--site-dir", str(built_site)]) == 0

    assert _record(git_repo, "1.0") == previous
    assert _git(git_repo, "show", "gh-pages:1.0/index.html") == "Updated content"


def test_deploy_metadata_under_a_prefix(git_repo: Path, built_site: Path) -> None:
    original = _record(git_repo, "1.0")
    assert main([
        "deploy", "2.0", "--site-dir", str(built_site), "--deploy-prefix", "docs",
        "-t", "Documentation 2.0", "--prop-set", 'metadata={"supported":true}',
    ]) == 0
    record = _record(git_repo, "2.0", "docs")
    assert record["title"] == "Documentation 2.0"
    assert record["properties"] == {"metadata": {"supported": True}}
    assert _record(git_repo, "1.0") == original


@pytest.mark.parametrize("options", [
    ["--prop-set", "hidden=invalid-json"],
    ["--prop-set-all", "[]"],
    ["--prop-delete", "missing"],
    ["--prop-set", "hidden=true", "--prop-delete", "missing"],
])
def test_failed_deployment_metadata_changes_nothing_and_does_not_push(
    git_repo: Path, built_site: Path, monkeypatch, options: list[str],
) -> None:
    previous = _git(git_repo, "rev-parse", "gh-pages")
    pushed = []
    monkeypatch.setattr("versite.commands.push_branch", lambda *args: pushed.append(args))
    assert main([
        "deploy", "1.0", "--site-dir", str(built_site), "--title", "Invalid update",
        *options, "--push",
    ]) == 1
    assert _git(git_repo, "rev-parse", "gh-pages") == previous
    assert _git(git_repo, "show", "gh-pages:1.0/index.html") == "<h1>1.0</h1>"
    assert (built_site / "index.html").read_text() == "Updated content"
    assert pushed == []
