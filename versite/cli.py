from __future__ import annotations

import argparse
import sys

from versite.commands import (
    VersiteError,
    alias_version,
    delete_versions,
    deploy_version,
    list_versions,
    props_version,
    retitle_version,
    serve_site,
    set_default,
)
from versite.config import apply_cli_overrides, load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="versite")
    subparsers = parser.add_subparsers(dest="command", required=True)

    deploy = subparsers.add_parser("deploy")
    deploy.add_argument("version")
    deploy.add_argument("aliases", nargs="*")
    _add_common_options(deploy, include_builder=True)
    deploy.add_argument("--source")
    deploy.add_argument("--output-dir")
    deploy.add_argument("--build-command", nargs=argparse.REMAINDER)
    deploy.add_argument("-q", "--quiet", action="store_true")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("identifier", nargs="?")
    _add_common_options(list_parser)
    list_parser.add_argument("--json", action="store_true")

    delete = subparsers.add_parser("delete")
    delete.add_argument("identifiers", nargs="*")
    delete.add_argument("--all", action="store_true")
    _add_common_options(delete)

    alias = subparsers.add_parser("alias")
    alias.add_argument("identifier")
    alias.add_argument("aliases", nargs="*")
    _add_common_options(alias)
    alias.add_argument("--alias-type", choices=["redirect", "copy", "symlink"])

    retitle = subparsers.add_parser("retitle")
    retitle.add_argument("identifier")
    retitle.add_argument("title")
    _add_common_options(retitle)

    props = subparsers.add_parser("props")
    props.add_argument("identifier")
    props.add_argument("prop", nargs="?")
    _add_common_options(props)
    props.add_argument("--json", action="store_true")

    default = subparsers.add_parser("set-default")
    default.add_argument("identifier")
    _add_common_options(default)

    serve = subparsers.add_parser("serve")
    _add_common_options(serve)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    return parser


def _add_common_options(parser: argparse.ArgumentParser, include_builder: bool = False) -> None:
    parser.add_argument("--config-file")
    if include_builder:
        parser.add_argument("--builder")
    parser.add_argument("-r", "--remote")
    parser.add_argument("-b", "--branch")
    parser.add_argument("-m", "--message")
    parser.add_argument("-p", "--push", action="store_true", default=None)
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--deploy-prefix")
    parser.add_argument("-T", "--template", dest="redirect_template")
    parser.add_argument("--ignore-remote-status", action="store_true")


def _load_runtime_config(args: argparse.Namespace) -> dict:
    config, _ = load_config(args.config_file)
    return apply_cli_overrides(
        config,
        builder=getattr(args, "builder", None),
        remote=args.remote,
        branch=args.branch,
        message=args.message,
        push=args.push,
        deploy_prefix=args.deploy_prefix,
        alias_type=getattr(args, "alias_type", None),
        redirect_template=args.redirect_template,
        ignore_remote_status=args.ignore_remote_status,
        source=getattr(args, "source", None),
        output_dir=getattr(args, "output_dir", None),
        build_command=getattr(args, "build_command", None),
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = _load_runtime_config(args)
        push = config.get("push", False)
        if args.command == "deploy":
            return deploy_version(
                config,
                args.version,
                args.aliases,
                message=args.message,
                push=push,
                allow_empty=args.allow_empty,
                quiet=args.quiet,
            )
        if args.command == "list":
            return list_versions(config, args.identifier, as_json=args.json)
        if args.command == "delete":
            return delete_versions(
                config,
                args.identifiers,
                delete_all=args.all,
                message=args.message,
                push=push,
                allow_empty=args.allow_empty,
            )
        if args.command == "alias":
            return alias_version(
                config,
                args.identifier,
                args.aliases,
                alias_type=args.alias_type or config["alias_type"],
                message=args.message,
                push=push,
                allow_empty=args.allow_empty,
            )
        if args.command == "retitle":
            return retitle_version(
                config,
                args.identifier,
                args.title,
                message=args.message,
                push=push,
                allow_empty=args.allow_empty,
            )
        if args.command == "props":
            return props_version(
                config,
                args.identifier,
                args.prop,
                message=args.message,
                push=push,
                allow_empty=args.allow_empty,
                as_json=args.json,
            )
        if args.command == "set-default":
            return set_default(
                config,
                args.identifier,
                message=args.message,
                push=push,
                allow_empty=args.allow_empty,
            )
        if args.command == "serve":
            return serve_site(config, host=args.host, port=args.port)
        parser.error(f"unsupported command: {args.command}")
    except (VersiteError, ValueError, KeyError) as exc:
        print(f"versite: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"versite: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
