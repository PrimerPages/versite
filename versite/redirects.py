from __future__ import annotations

from importlib import resources
from pathlib import Path

from jinja2 import Template


def load_redirect_template(path: str | None = None) -> str:
    if path is None:
        return resources.files("versite.templates").joinpath("redirect.html").read_text(
            encoding="utf-8"
        )
    return Path(path).read_text(encoding="utf-8")


def render_redirect(href: str, template_path: str | None = None) -> str:
    template = Template(load_redirect_template(template_path))
    return template.render(href=href)


def write_redirect(path: Path, href: str, template_path: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_redirect(href, template_path), encoding="utf-8")
