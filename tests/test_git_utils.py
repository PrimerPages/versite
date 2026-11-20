from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from versite.git_utils import GitError, branch_worktree, ensure_branch_ready


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _commit(repo: Path, name: str, content: str) -> None:
    (repo / name).write_text(content)
    _git(repo, "add", name)
    _git(repo, "commit", "-m", f"Update {name}")


@pytest.fixture
def remote_writer(git_repo: Path, tmp_path: Path) -> Path:
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", "--initial-branch=main", str(remote))
    _git(git_repo, "remote", "add", "origin", str(remote))
    _git(git_repo, "push", "origin", "main", "gh-pages")
    writer = tmp_path / "writer"
    _git(tmp_path, "clone", "--branch", "gh-pages", str(remote), str(writer))
    _git(writer, "config", "user.name", "Remote Writer")
    _git(writer, "config", "user.email", "writer@example.com")
    return writer


@pytest.mark.parametrize("state", ["matching", "ahead", "behind", "diverged"])
def test_synchronize_deployment_branch_without_losing_local_work(
    git_repo: Path, remote_writer: Path, state: str,
) -> None:
    if state in {"ahead", "diverged"}:
        with branch_worktree(git_repo, "gh-pages", ignore_remote_status=True) as worktree:
            _commit(worktree, "local.html", "Local deployment")
    if state in {"behind", "diverged"}:
        _commit(remote_writer, "remote.html", "Remote deployment")
        _git(remote_writer, "push", "origin", "gh-pages")

    original_branch = _git(git_repo, "rev-parse", "gh-pages")
    original_head = _git(git_repo, "rev-parse", "HEAD")
    (git_repo / "README.md").write_text("Uncommitted source edits")
    (git_repo / "untracked.txt").write_text("Untracked source file")

    if state == "diverged":
        with pytest.raises(GitError, match="diverged"):
            ensure_branch_ready(git_repo, "gh-pages", "origin")
    else:
        ensure_branch_ready(git_repo, "gh-pages", "origin")

    expected = _git(remote_writer, "rev-parse", "HEAD") if state == "behind" else original_branch
    assert _git(git_repo, "rev-parse", "gh-pages") == expected
    assert _git(git_repo, "rev-parse", "HEAD") == original_head
    assert _git(git_repo, "branch", "--show-current") == "main"
    assert (git_repo / "README.md").read_text() == "Uncommitted source edits"
    assert (git_repo / "untracked.txt").read_text() == "Untracked source file"
    if state == "behind":
        with branch_worktree(git_repo, "gh-pages") as worktree:
            assert (worktree / "remote.html").read_text() == "Remote deployment"
            _commit(worktree, "next.html", "Next deployment")
            _git(worktree, "push", "origin", "gh-pages")


def test_synchronize_branch_with_narrow_remote_fetch_configuration(
    git_repo: Path, remote_writer: Path,
) -> None:
    _git(git_repo, "config", "remote.origin.fetch", "+refs/heads/main:refs/remotes/origin/main")
    _commit(remote_writer, "remote.html", "New deployment")
    _git(remote_writer, "push", "origin", "gh-pages")

    ensure_branch_ready(git_repo, "gh-pages", "origin")

    assert _git(git_repo, "rev-parse", "gh-pages") == _git(remote_writer, "rev-parse", "HEAD")


def test_synchronize_creates_missing_branch_in_a_single_branch_clone(
    git_repo: Path, remote_writer: Path, tmp_path: Path,
) -> None:
    clone = tmp_path / "single-branch"
    remote = _git(git_repo, "remote", "get-url", "origin")
    _git(tmp_path, "clone", "--single-branch", "--branch", "main", remote, str(clone))

    ensure_branch_ready(clone, "gh-pages", "origin")

    assert _git(clone, "rev-parse", "gh-pages") == _git(remote_writer, "rev-parse", "HEAD")
    assert _git(clone, "branch", "--show-current") == "main"


def test_ignore_remote_status_leaves_branch_and_remote_tracking_ref_unchanged(
    git_repo: Path, remote_writer: Path,
) -> None:
    original = _git(git_repo, "rev-parse", "gh-pages")
    _commit(remote_writer, "remote.html", "Remote deployment")
    _git(remote_writer, "push", "origin", "gh-pages")

    ensure_branch_ready(git_repo, "gh-pages", "origin", ignore_remote_status=True)

    assert _git(git_repo, "rev-parse", "gh-pages") == original
    assert _git(git_repo, "rev-parse", "origin/gh-pages") == original


def test_synchronization_refuses_to_move_a_checked_out_branch(
    git_repo: Path, remote_writer: Path,
) -> None:
    _commit(remote_writer, "remote.html", "Remote deployment")
    _git(remote_writer, "push", "origin", "gh-pages")
    _git(git_repo, "checkout", "gh-pages")
    original = _git(git_repo, "rev-parse", "HEAD")
    page = git_repo / "1.0/index.html"
    page.write_text("Uncommitted documentation")

    with pytest.raises(subprocess.CalledProcessError):
        ensure_branch_ready(git_repo, "gh-pages", "origin")

    assert _git(git_repo, "rev-parse", "HEAD") == original
    assert _git(git_repo, "rev-parse", "gh-pages") == original
    assert page.read_text() == "Uncommitted documentation"
