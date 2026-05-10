from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Any


class BuilderError(RuntimeError):
    pass


@dataclass
class BuildResult:
    site_dir: str
    metadata: dict[str, Any]


@dataclass
class CommandBuilder:
    name: str
    command: list[str]

    def build(
        self,
        *,
        version: str,
        output_dir: str,
        config: dict[str, Any],
        quiet: bool = False,
    ) -> BuildResult:
        variables = {
            "version": version,
            "output_dir": output_dir,
            "source": config.get("source", "."),
            "config_file": config.get("config_file", "mkdocs.yml"),
        }
        rendered = [part.format(**variables) for part in self.command]
        env = os.environ.copy()
        env["VERSITE_VERSION"] = version
        if self.name == "mkdocs":
            env["MIKE_DOCS_VERSION"] = version
        kwargs: dict[str, Any] = {"check": True, "env": env}
        if quiet:
            kwargs["stdout"] = subprocess.DEVNULL
            kwargs["stderr"] = subprocess.DEVNULL
        try:
            subprocess.run(rendered, **kwargs)
        except FileNotFoundError as exc:
            raise BuilderError(
                f"builder command is unavailable: {rendered[0]}"
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise BuilderError(f"builder command failed with exit code {exc.returncode}") from exc
        return BuildResult(site_dir=output_dir, metadata={"command": rendered})


def load_builder(name: str, config: dict[str, Any]) -> CommandBuilder:
    try:
        builder_config = config["builders"][name]
    except KeyError as exc:
        raise BuilderError(f"unknown builder: {name}") from exc
    command = builder_config.get("command")
    if not command:
        raise BuilderError(f"builder '{name}' has no command configured")
    return CommandBuilder(name=name, command=list(command))
