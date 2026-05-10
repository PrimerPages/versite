from __future__ import annotations

import os
import sys
from pathlib import Path

from versite.builders.command import load_builder


def test_builder_runs_command_and_sets_env(tmp_path: Path) -> None:
    script = tmp_path / "builder.py"
    script.write_text(
        "import os, pathlib, sys\n"
        "out = pathlib.Path(sys.argv[1])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'index.html').write_text(os.environ['VERSITE_VERSION'])\n",
        encoding="utf-8",
    )
    config = {
        "builders": {
            "custom": {
                "command": [sys.executable, str(script), "{output_dir}"],
            }
        }
    }
    builder = load_builder("custom", config)
    result = builder.build(version="2.0", output_dir=str(tmp_path / "out"), config={}, quiet=False)
    assert Path(result.site_dir).joinpath("index.html").read_text(encoding="utf-8") == "2.0"


def test_mkdocs_builder_sets_compat_env(tmp_path: Path, monkeypatch) -> None:
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["env"] = kwargs["env"]
        return None

    monkeypatch.setattr("subprocess.run", fake_run)
    config = {"builders": {"mkdocs": {"command": ["mkdocs", "build", "--site-dir", "{output_dir}"]}}}
    builder = load_builder("mkdocs", config)
    builder.build(version="3.0", output_dir=str(tmp_path / "out"), config={}, quiet=True)
    assert observed["env"]["VERSITE_VERSION"] == "3.0"
    assert observed["env"]["MIKE_DOCS_VERSION"] == "3.0"
