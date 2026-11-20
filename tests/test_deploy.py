from __future__ import annotations

import json
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

import pytest

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


@pytest.mark.parametrize("prefix", ["", "docs", "products/widget/docs"])
@pytest.mark.parametrize("existing_homepage", [False, True])
def test_default_redirects_stay_inside_the_site_root(
    git_repo: Path, tmp_path: Path, prefix: str, existing_homepage: bool
) -> None:
    with real_branch_worktree(git_repo, "gh-pages", ignore_remote_status=True) as worktree:
        if existing_homepage:
            (worktree / "index.html").write_text("Main homepage")
        other_site = worktree / "other"
        other_site.mkdir()
        (other_site / "index.html").write_text("Other site's default")
        subprocess.run(["git", "add", "-A"], cwd=worktree, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Seed independent homepages"],
            cwd=worktree, check=True, capture_output=True,
        )

    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text("Version content")
    options = ["--deploy-prefix", prefix]
    assert main(["deploy", "2.0", "latest", "--site-dir", str(site_dir), *options]) == 0

    default_path = str(Path(prefix) / "index.html")
    initial_default = _show_file(git_repo, "gh-pages", default_path)
    if not prefix and existing_homepage:
        assert initial_default == "Main homepage"
    else:
        assert 'href="./latest/"' in initial_default

    # Deploying another version preserves the site's existing default.
    assert main(["deploy", "3.0", "--site-dir", str(site_dir), *options]) == 0
    assert _show_file(git_repo, "gh-pages", default_path) == initial_default

    # Explicit default changes are relative to this site's own directory.
    assert main(["set-default", "3.0", *options]) == 0
    assert 'href="./3.0/"' in _show_file(git_repo, "gh-pages", default_path)
    assert main(["set-default", "latest", *options]) == 0
    assert 'href="./latest/"' in _show_file(git_repo, "gh-pages", default_path)
    assert _show_file(git_repo, "gh-pages", "other/index.html") == "Other site's default"

    if prefix:
        if existing_homepage:
            assert _show_file(git_repo, "gh-pages", "index.html") == "Main homepage"
        else:
            root_index = subprocess.run(
                ["git", "cat-file", "-e", "gh-pages:index.html"],
                cwd=git_repo, capture_output=True,
            )
            assert root_index.returncode != 0


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


def test_deploy_writes_newest_first_manifest_and_preserves_old_versions(git_repo: Path, tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text("Release content")
    for version in ["2.0.0", "dev", "2.2.1"]:
        assert main(["deploy", version, "--site-dir", str(site_dir), "-b", "gh-pages"]) == 0
    versions = json.loads(_show_file(git_repo, "gh-pages", "versions.json"))
    assert [item["version"] for item in versions] == ["dev", "2.2.1", "2.0.0", "1.0"]
    assert versions[-1]["aliases"] == ["latest"]
    assert versions[-1]["properties"] == {"channel": "stable"}
    assert _show_file(git_repo, "gh-pages", "1.0/index.html") == "<h1>1.0</h1>"


@pytest.mark.parametrize(
    ("alias_type", "configured_type"),
    [("redirect", "copy"), ("copy", "symlink"), ("symlink", "redirect")],
)
def test_deploy_alias_type_overrides_configuration(
    git_repo: Path, tmp_path: Path, alias_type: str, configured_type: str
) -> None:
    config = git_repo / "versite.yml"
    config.write_text(f"alias_type: {configured_type}\n")
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text("Version content")

    assert main([
        "deploy", "2.0", "stable", "--site-dir", str(site_dir),
        "--alias-type", alias_type,
    ]) == 0

    with real_branch_worktree(git_repo, "gh-pages", ignore_remote_status=True) as worktree:
        alias_dir = worktree / "stable"
        assert alias_dir.is_symlink() == (alias_type == "symlink")
        if alias_type == "redirect":
            assert 'href="../2.0/"' in (alias_dir / "index.html").read_text()
        else:
            assert (alias_dir / "index.html").read_text() == "Version content"
    assert config.read_text() == f"alias_type: {configured_type}\n"


@pytest.mark.parametrize("alias_type", ["redirect", "copy", "symlink"])
@pytest.mark.parametrize("new_aliases", [[], ["preview"]])
def test_redeploy_refreshes_all_attached_aliases(
    git_repo: Path, tmp_path: Path, alias_type: str, new_aliases: list[str]
) -> None:
    config = git_repo / "versite.yml"
    config.write_text(f"alias_type: {alias_type}\n")
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text("Original home")
    (site_dir / "removed.html").write_text("Obsolete page")
    assert main(["deploy", "2.0", "stable", "pinned", "--site-dir", str(site_dir)]) == 0
    previous_default = _show_file(git_repo, "gh-pages", "index.html")
    previous_other_alias = _show_file(git_repo, "gh-pages", "latest/index.html")

    (site_dir / "index.html").write_text("Updated home")
    (site_dir / "removed.html").unlink()
    (site_dir / "added.html").write_text("New page")
    assert main(["deploy", "2.0", *new_aliases, "--site-dir", str(site_dir)]) == 0

    aliases = {"stable", "pinned", *new_aliases}
    with real_branch_worktree(git_repo, "gh-pages", ignore_remote_status=True) as worktree:
        for alias in aliases:
            alias_dir = worktree / alias
            assert not (alias_dir / "removed.html").exists()
            if alias_type == "redirect":
                assert "../2.0/" in (alias_dir / "index.html").read_text()
                assert "../2.0/added.html" in (alias_dir / "added.html").read_text()
            else:
                assert (alias_dir / "index.html").read_text() == "Updated home"
                assert (alias_dir / "added.html").read_text() == "New page"
            assert alias_dir.is_symlink() == (alias_type == "symlink")
        manifest = json.loads((worktree / "versions.json").read_text())
        deployed = next(item for item in manifest if item["version"] == "2.0")
        assert set(deployed["aliases"]) == aliases
        previous = next(item for item in manifest if item["version"] == "1.0")
        assert previous["aliases"] == ["latest"]
        assert previous["properties"] == {"channel": "stable"}
        assert (worktree / "1.0/index.html").read_text() == "<h1>1.0</h1>"
        assert (worktree / "latest/index.html").read_text() == previous_other_alias
        assert (worktree / "index.html").read_text() == previous_default
