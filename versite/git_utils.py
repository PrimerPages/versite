from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class GitError(RuntimeError):
    pass


def git_root(cwd: str | Path | None = None) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip())


def run_git(
    repo: str | Path,
    *args: str,
    cwd: str | Path | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd or repo,
        check=True,
        capture_output=capture_output,
        text=True,
    )


def ref_exists(repo: str | Path, ref: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def ensure_branch_ready(
    repo: str | Path,
    branch: str,
    remote: str,
    ignore_remote_status: bool = False,
) -> None:
    local_ref = f"refs/heads/{branch}"
    remote_ref = f"refs/remotes/{remote}/{branch}"

    if not ignore_remote_status:
        subprocess.run(
            ["git", "fetch", remote, branch],
            cwd=repo,
            capture_output=True,
            text=True,
        )

    if not ref_exists(repo, local_ref) and ref_exists(repo, remote_ref):
        run_git(repo, "branch", branch, remote_ref)

    if ignore_remote_status or not ref_exists(repo, local_ref) or not ref_exists(repo, remote_ref):
        return

    local_sha = run_git(repo, "rev-parse", local_ref, capture_output=True).stdout.strip()
    remote_sha = run_git(repo, "rev-parse", remote_ref, capture_output=True).stdout.strip()
    if local_sha == remote_sha:
        return

    ahead = subprocess.run(
        ["git", "merge-base", "--is-ancestor", remote_sha, local_sha],
        cwd=repo,
    )
    behind = subprocess.run(
        ["git", "merge-base", "--is-ancestor", local_sha, remote_sha],
        cwd=repo,
    )
    if behind.returncode == 0:
        raise GitError(
            f"local branch '{branch}' is behind {remote}/{branch}; fetch or use --ignore-remote-status"
        )
    if ahead.returncode != 0:
        raise GitError(
            f"local branch '{branch}' diverged from {remote}/{branch}; resolve it or use --ignore-remote-status"
        )


def _clear_directory(path: Path) -> None:
    for child in path.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


@contextmanager
def branch_worktree(
    repo: str | Path,
    branch: str,
    remote: str = "origin",
    ignore_remote_status: bool = False,
) -> Iterator[Path]:
    repo_path = Path(repo)
    ensure_branch_ready(repo_path, branch, remote, ignore_remote_status)
    safe_branch = branch.replace("/", "-")
    tempdir = Path(tempfile.mkdtemp(prefix=f"versite-{safe_branch}-"))
    has_branch = ref_exists(repo_path, f"refs/heads/{branch}")
    try:
        if has_branch:
            run_git(repo_path, "worktree", "add", "--detach", str(tempdir), branch)
            run_git(repo_path, "checkout", branch, cwd=tempdir)
        else:
            run_git(repo_path, "worktree", "add", "--detach", str(tempdir), "HEAD")
            run_git(repo_path, "checkout", "--orphan", branch, cwd=tempdir)
            _clear_directory(tempdir)
        yield tempdir
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(tempdir)], cwd=repo_path)
        shutil.rmtree(tempdir, ignore_errors=True)


def commit_all(repo: str | Path, message: str, allow_empty: bool = False) -> bool:
    run_git(repo, "add", "-A", cwd=repo)
    status = run_git(repo, "status", "--porcelain", cwd=repo, capture_output=True).stdout.strip()
    if not status and not allow_empty:
        return False
    command = ["commit", "-m", message]
    if allow_empty:
        command.append("--allow-empty")
    run_git(repo, *command, cwd=repo)
    return True


def push_branch(repo: str | Path, remote: str, branch: str) -> None:
    run_git(repo, "push", remote, branch, cwd=repo)
