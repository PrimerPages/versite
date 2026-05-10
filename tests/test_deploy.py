from __future__ import annotations

import builtins
import json
import subprocess
import sys
from pathlib import Path

from versite.cli import main


def _show_file(repo: Path, branch: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{branch}:{path}"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_deploy_custom_builder(git_repo: Path, tmp_path: Path) -> None:
    script = tmp_path / "custom_builder.py"
    script.write_text(
        "import os, pathlib, sys\n"
        "out = pathlib.Path(sys.argv[1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'index.html').write_text(os.environ['VERSITE_VERSION'])\n",
        encoding="utf-8",
    )
    config = git_repo / "versite.yml"
    config.write_text(
        "builder: custom\n"
        "branch: gh-pages\n"
        "builders:\n"
        "  custom:\n"
        f"    command: ['{sys.executable}', '{script}', '{{output_dir}}']\n",
        encoding="utf-8",
    )
    assert main(["deploy", "2.0", "latest", "--builder", "custom", "--config-file", str(config)]) == 0
    versions = json.loads(_show_file(git_repo, "gh-pages", "versions.json"))
    assert any(item["version"] == "2.0" for item in versions)
    assert _show_file(git_repo, "gh-pages", "2.0/index.html") == "2.0"


def test_deploy_mkdocs_command_template(git_repo: Path, tmp_path: Path) -> None:
    script = tmp_path / "fake_mkdocs.py"
    marker = tmp_path / "env.txt"
    script.write_text(
        "import os, pathlib, sys\n"
        "out = pathlib.Path(sys.argv[-1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'index.html').write_text('mkdocs')\n"
        f"pathlib.Path(r'{marker}').write_text(os.environ['MIKE_DOCS_VERSION'])\n",
        encoding="utf-8",
    )
    config = git_repo / "versite.yml"
    config.write_text(
        "branch: gh-pages\n"
        "builders:\n"
        "  mkdocs:\n"
        f"    command: ['{sys.executable}', '{script}', '--site-dir', '{{output_dir}}']\n",
        encoding="utf-8",
    )
    assert main(["deploy", "3.0", "--builder", "mkdocs", "--config-file", str(config)]) == 0
    assert marker.read_text(encoding="utf-8") == "3.0"
    assert _show_file(git_repo, "gh-pages", "3.0/index.html") == "mkdocs"


def test_deploy_jekyll_command_template(git_repo: Path, tmp_path: Path) -> None:
    script = tmp_path / "fake_jekyll.py"
    marker = tmp_path / "jekyll_env.txt"
    script.write_text(
        "import os, pathlib, sys\n"
        "out = pathlib.Path(sys.argv[-1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'index.html').write_text('jekyll')\n"
        f"pathlib.Path(r'{marker}').write_text(os.environ['VERSITE_VERSION'])\n",
        encoding="utf-8",
    )
    config = git_repo / "versite.yml"
    config.write_text(
        "builder: jekyll\n"
        "branch: gh-pages\n"
        "builders:\n"
        "  jekyll:\n"
        f"    command: ['{sys.executable}', '{script}', '--destination', '{{output_dir}}']\n",
        encoding="utf-8",
    )
    assert main(["deploy", "4.0", "--builder", "jekyll", "--config-file", str(config)]) == 0
    assert marker.read_text(encoding="utf-8") == "4.0"
    assert _show_file(git_repo, "gh-pages", "4.0/index.html") == "jekyll"


def test_deploy_site_dir_without_loading_builder(
    git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text("prebuilt", encoding="utf-8")
    assets = site_dir / "assets"
    assets.mkdir()
    (assets / "app.css").write_text("body{}", encoding="utf-8")

    sys.modules.pop("versite.builders.command", None)
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "versite.builders.command":
            raise AssertionError("builder module should not be imported for --site-dir deploys")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    assert main(["deploy", "5.0", "latest", "--site-dir", str(site_dir), "-b", "gh-pages"]) == 0
    assert _show_file(git_repo, "gh-pages", "5.0/index.html") == "prebuilt"
    assert _show_file(git_repo, "gh-pages", "5.0/assets/app.css") == "body{}"
