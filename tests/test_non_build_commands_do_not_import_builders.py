from __future__ import annotations

import builtins
from pathlib import Path

from versite.cli import main


def test_non_build_commands_do_not_import_mkdocs(git_repo: Path, monkeypatch) -> None:
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("mkdocs"):
            raise AssertionError("mkdocs should not be imported")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    commands = [
        ["list"],
        ["delete", "latest"],
        ["alias", "1.0", "stable"],
        ["retitle", "1.0", "One"],
        ["props", "1.0"],
        ["props", "1.0", "meta.channel=\"beta\""],
        ["set-default", "1.0"],
    ]
    monkeypatch.setattr("versite.commands.serve_directory", lambda *args, **kwargs: None)
    for argv in commands:
        assert main([*argv, "-b", "gh-pages", "--ignore-remote-status"]) == 0
    assert main(["serve", "-b", "gh-pages", "--ignore-remote-status"]) == 0
