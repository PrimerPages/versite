from __future__ import annotations

import subprocess
from pathlib import Path

from versite.cli import main


def test_non_build_commands_do_not_run_builder_commands(git_repo: Path, monkeypatch) -> None:
    original_run = subprocess.run

    def guarded_run(command, *args, **kwargs):
        if isinstance(command, list) and command and command[0] in {"mkdocs", "bundle", "jekyll", "npm"}:
            raise AssertionError("builder command should not run")
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", guarded_run)
    monkeypatch.setattr("versite.commands.serve_directory", lambda *args, **kwargs: None)
    assert main(["list", "-b", "gh-pages", "--ignore-remote-status"]) == 0
    assert main(["delete", "latest", "-b", "gh-pages", "--ignore-remote-status"]) == 0
    assert main(["retitle", "1.0", "One", "-b", "gh-pages", "--ignore-remote-status"]) == 0
    assert main(["props", "1.0", "channel", "-b", "gh-pages", "--ignore-remote-status"]) == 0
    assert main(["set-default", "1.0", "-b", "gh-pages", "--ignore-remote-status"]) == 0
    assert main(["serve", "-b", "gh-pages", "--ignore-remote-status"]) == 0
