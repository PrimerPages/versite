from __future__ import annotations

import json
import sys
import subprocess
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Versite Tests")
    _git(repo, "config", "user.email", "versite@example.com")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "seed")
    _git(repo, "checkout", "--orphan", "gh-pages")
    for child in repo.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            import shutil

            shutil.rmtree(child)
        else:
            child.unlink()
    versions = [
        {"version": "1.0", "title": "1.0", "aliases": ["latest"], "properties": {"channel": "stable"}}
    ]
    (repo / "versions.json").write_text(json.dumps(versions, indent=2) + "\n", encoding="utf-8")
    site = repo / "1.0"
    site.mkdir()
    (site / "index.html").write_text("<h1>1.0</h1>", encoding="utf-8")
    latest = repo / "latest"
    latest.mkdir()
    (latest / "index.html").write_text("latest", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "gh-pages seed")
    _git(repo, "checkout", "main")
    monkeypatch.chdir(repo)
    return repo
