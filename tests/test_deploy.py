from __future__ import annotations

import json
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

from versite.cli import main
from versite.git_utils import branch_worktree as real_branch_worktree


def _show_file(repo: Path, branch: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{branch}:{path}"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_deploy_site_dir_copies_contents_and_updates_versions(git_repo: Path, tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text("2.0", encoding="utf-8")
    (site_dir / "guide").mkdir()
    (site_dir / "guide" / "index.html").write_text("guide", encoding="utf-8")
    (site_dir / "guide" / "reference").mkdir()
    (site_dir / "guide" / "reference" / "index.html").write_text("reference", encoding="utf-8")
    (site_dir / "about.html").write_text("about", encoding="utf-8")

    assert main(["deploy", "2.0", "latest", "--site-dir", str(site_dir), "-b", "gh-pages"]) == 0
    versions = json.loads(_show_file(git_repo, "gh-pages", "versions.json"))
    assert any(item["version"] == "2.0" for item in versions)
    assert _show_file(git_repo, "gh-pages", "2.0/index.html") == "2.0"
    assert _show_file(git_repo, "gh-pages", "2.0/guide/index.html") == "guide"
    assert "../../2.0/guide/" in _show_file(git_repo, "gh-pages", "latest/guide/index.html")
    assert "../../../2.0/guide/reference/" in _show_file(
        git_repo, "gh-pages", "latest/guide/reference/index.html"
    )
    assert "../2.0/about.html" in _show_file(git_repo, "gh-pages", "latest/about.html")


def test_deploy_requires_site_dir(git_repo: Path, capsys) -> None:
    assert main(["deploy", "2.0", "-b", "gh-pages"]) == 1
    captured = capsys.readouterr()
    assert "deploy requires --site-dir" in captured.err


def test_deploy_does_not_require_builder_config(git_repo: Path, tmp_path: Path) -> None:
    config = git_repo / "versite.yml"
    config.write_text("branch: gh-pages\nalias_type: redirect\n", encoding="utf-8")
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text("3.0", encoding="utf-8")

    assert main(["deploy", "3.0", "--site-dir", str(site_dir), "--config-file", str(config)]) == 0
    assert _show_file(git_repo, "gh-pages", "3.0/index.html") == "3.0"


def test_deploy_stages_site_dir_before_branch_setup(git_repo: Path, tmp_path: Path, monkeypatch) -> None:
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text("4.0", encoding="utf-8")

    @contextmanager
    def disruptive_branch_worktree(*args, **kwargs):
        shutil.rmtree(site_dir)
        with real_branch_worktree(*args, **kwargs) as worktree:
            yield worktree

    monkeypatch.setattr("versite.commands.branch_worktree", disruptive_branch_worktree)

    assert main(["deploy", "4.0", "--site-dir", str(site_dir), "-b", "gh-pages"]) == 0
    assert _show_file(git_repo, "gh-pages", "4.0/index.html") == "4.0"


def test_deploy_supports_branch_names_with_slashes(git_repo: Path, tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text("5.0", encoding="utf-8")

    branch = "ci-test/deploy-site"
    assert main(["deploy", "5.0", "--site-dir", str(site_dir), "-b", branch]) == 0
    assert _show_file(git_repo, branch, "5.0/index.html") == "5.0"
