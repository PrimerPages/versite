from __future__ import annotations

from pathlib import Path

from versite.redirects import render_redirect, write_redirect


def test_render_redirect_contains_href() -> None:
    content = render_redirect("../1.0/")
    assert "../1.0/" in content


def test_write_redirect(tmp_path: Path) -> None:
    target = tmp_path / "latest" / "index.html"
    write_redirect(target, "../1.0/")
    assert "../1.0/" in target.read_text(encoding="utf-8")
