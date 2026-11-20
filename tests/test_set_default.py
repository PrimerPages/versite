from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from versite.cli import main


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.mark.parametrize("prefix", ["", "docs", "products/widget/docs"])
@pytest.mark.parametrize("identifier", ["2.0", "upcoming"])
def test_configure_default_before_deploying_target(
    git_repo: Path, tmp_path: Path, prefix: str, identifier: str,
) -> None:
    options = ["--deploy-prefix", prefix]
    previous = _git(git_repo, "rev-parse", "gh-pages")
    manifest = _git(git_repo, "show", "gh-pages:versions.json")
    assert main(["set-default", identifier, *options]) == 1
    assert _git(git_repo, "rev-parse", "gh-pages") == previous

    assert main(["set-default", identifier, "--allow-undefined", *options]) == 0
    default_path = str(Path(prefix) / "index.html")
    redirect = _git(git_repo, "show", f"gh-pages:{default_path}")
    assert f'href="./{identifier}/"' in redirect
    assert _git(git_repo, "show", "gh-pages:versions.json") == manifest
    paths = _git(git_repo, "ls-tree", "--name-only", "-r", "gh-pages").splitlines()
    assert str(Path(prefix) / identifier / "index.html") not in paths
    if prefix:
        assert "index.html" not in paths
        assert str(Path(prefix) / "versions.json") not in paths

    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("Published version")
    aliases = [identifier] if identifier == "upcoming" else []
    assert main(["deploy", "2.0", *aliases, "--site-dir", str(site), *options]) == 0
    assert _git(git_repo, "show", f"gh-pages:{default_path}") == redirect
    version_path = str(Path(prefix) / "2.0/index.html")
    assert _git(git_repo, "show", f"gh-pages:{version_path}") == "Published version"
    if aliases:
        alias_path = str(Path(prefix) / identifier / "index.html")
        assert 'href="../2.0/"' in _git(git_repo, "show", f"gh-pages:{alias_path}")


def test_allow_undefined_can_initialize_a_deployment_branch(git_repo: Path) -> None:
    assert main([
        "set-default", "latest", "--allow-undefined", "--branch", "docs/new",
        "--deploy-prefix", "docs",
    ]) == 0
    assert _git(git_repo, "ls-tree", "--name-only", "-r", "docs/new") == "docs/index.html"
    assert 'href="./latest/"' in _git(git_repo, "show", "docs/new:docs/index.html")


@pytest.mark.parametrize("identifier", ["", ".", "../outside", "/outside"])
def test_allow_undefined_still_rejects_unsafe_identifiers(
    git_repo: Path, identifier: str,
) -> None:
    previous = _git(git_repo, "rev-parse", "gh-pages")
    assert main(["set-default", identifier, "--allow-undefined"]) == 1
    assert _git(git_repo, "rev-parse", "gh-pages") == previous
