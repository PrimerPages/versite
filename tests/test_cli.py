from __future__ import annotations

from versite.cli import build_parser, main


def test_help_parser_exists() -> None:
    parser = build_parser()
    assert parser.prog == "versite"


def test_help_command(capsys) -> None:
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    captured = capsys.readouterr()
    assert "deploy" in captured.out
