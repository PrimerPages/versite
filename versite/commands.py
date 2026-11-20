from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from versite.config import normalize_prefix
from versite.git_utils import GitError, branch_worktree, commit_all, git_root, push_branch
from versite.redirects import write_redirect
from versite.serve import serve_directory
from versite.versions import VersionStore


class VersiteError(RuntimeError):
    pass


def _site_root(worktree: Path, deploy_prefix: str) -> Path:
    prefix = normalize_prefix(deploy_prefix)
    return worktree / prefix if prefix else worktree


def _versions_file(worktree: Path, deploy_prefix: str) -> Path:
    return _site_root(worktree, deploy_prefix) / "versions.json"


def _identifier_path(worktree: Path, deploy_prefix: str, identifier: str) -> Path:
    if identifier.startswith("/") or ".." in Path(identifier).parts:
        raise VersiteError(f"unsafe identifier path: {identifier}")
    return _site_root(worktree, deploy_prefix) / identifier


def _print(data: Any, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=True))
    elif isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(data)


def _load_store(worktree: Path, deploy_prefix: str) -> VersionStore:
    return VersionStore.load(_versions_file(worktree, deploy_prefix))


def _save_store(worktree: Path, deploy_prefix: str, store: VersionStore) -> None:
    site_root = _site_root(worktree, deploy_prefix)
    site_root.mkdir(parents=True, exist_ok=True)
    store.save(_versions_file(worktree, deploy_prefix))


def _alias_redirect_href(alias: str, version: str) -> str:
    alias_parts = Path(alias).parts
    upward = "../" * max(len(alias_parts), 1)
    return f"{upward}{version}/"


def _relative_redirect_href(source: Path, target: Path, *, clean_url: bool = False) -> str:
    href = os.path.relpath(target, source.parent).replace(os.sep, "/")
    if clean_url:
        href = href.rstrip("/") + "/"
    return href


def _write_alias_redirects(
    alias_path: Path,
    version_path: Path,
    alias: str,
    version: str,
    redirect_template: str | None,
) -> None:
    write_redirect(alias_path / "index.html", _alias_redirect_href(alias, version), redirect_template)
    for version_file in version_path.rglob("*.html"):
        relative_path = version_file.relative_to(version_path)
        if relative_path == Path("index.html"):
            continue
        alias_file = alias_path / relative_path
        target = version_file
        clean_url = version_file.name == "index.html"
        if clean_url:
            target = version_file.parent
        write_redirect(
            alias_file,
            _relative_redirect_href(alias_file, target, clean_url=clean_url),
            redirect_template,
        )


def _copy_contents(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    shutil.copytree(source, destination, symlinks=True)


def _stage_source_site(source: Path) -> Path:
    staging_root = Path(tempfile.mkdtemp(prefix="versite-source-"))
    staged_site = staging_root / "site"
    shutil.copytree(source, staged_site, symlinks=True)
    return staged_site


def _ensure_root_redirect(
    worktree: Path,
    deploy_prefix: str,
    identifier: str,
    redirect_template: str | None,
) -> None:
    root_index = _site_root(worktree, deploy_prefix) / "index.html"
    if root_index.exists() or root_index.is_symlink():
        return
    write_redirect(
        root_index,
        f"./{identifier}/",
        redirect_template,
    )


def _write_alias(
    worktree: Path,
    deploy_prefix: str,
    alias: str,
    version: str,
    alias_type: str,
    redirect_template: str | None,
) -> None:
    alias_path = _identifier_path(worktree, deploy_prefix, alias)
    version_path = _identifier_path(worktree, deploy_prefix, version)
    if alias_path.exists() or alias_path.is_symlink():
        if alias_path.is_dir() and not alias_path.is_symlink():
            shutil.rmtree(alias_path)
        else:
            alias_path.unlink()
    if alias_type == "redirect":
        _write_alias_redirects(alias_path, version_path, alias, version, redirect_template)
        return
    if alias_type == "copy":
        _copy_contents(version_path, alias_path)
        return
    if alias_type == "symlink":
        alias_path.parent.mkdir(parents=True, exist_ok=True)
        target = os.path.relpath(version_path, alias_path.parent)
        os.symlink(target, alias_path)
        return
    raise VersiteError(f"unsupported alias type: {alias_type}")


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def list_versions(config: dict[str, Any], identifier: str | None = None, as_json: bool = False) -> int:
    repo = git_root()
    with branch_worktree(
        repo,
        config["branch"],
        remote=config["remote"],
        ignore_remote_status=config.get("ignore_remote_status", False),
    ) as worktree:
        store = _load_store(worktree, config["deploy_prefix"])
        if identifier is None:
            _print(store.as_list(), as_json)
            return 0
        record = store.get(identifier)
        _print(
            {
                "version": record.version,
                "title": record.title,
                "aliases": record.aliases,
                "properties": record.properties,
            },
            as_json,
        )
    return 0


def delete_versions(
    config: dict[str, Any],
    identifiers: list[str],
    *,
    delete_all: bool = False,
    message: str | None = None,
    push: bool = False,
    allow_empty: bool = False,
) -> int:
    if not identifiers and not delete_all:
        raise VersiteError("delete requires identifiers or --all")
    repo = git_root()
    with branch_worktree(
        repo,
        config["branch"],
        remote=config["remote"],
        ignore_remote_status=config.get("ignore_remote_status", False),
    ) as worktree:
        store = _load_store(worktree, config["deploy_prefix"])
        if delete_all:
            targets = [record.version for record in list(store.records)]
        else:
            targets = identifiers
        removed_any = False
        for identifier in targets:
            version, aliases = store.delete_identifier(identifier)
            removed_any = True
            if version is not None:
                _remove_path(_identifier_path(worktree, config["deploy_prefix"], version))
            for alias in aliases:
                _remove_path(_identifier_path(worktree, config["deploy_prefix"], alias))
        _save_store(worktree, config["deploy_prefix"], store)
        committed = commit_all(
            worktree,
            message or ("Delete all deployed versions" if delete_all else f"Delete {' '.join(targets)}"),
            allow_empty=allow_empty,
        )
        if push and committed:
            push_branch(worktree, config["remote"], config["branch"])
        return 0 if removed_any else 1


def alias_version(
    config: dict[str, Any],
    identifier: str,
    aliases: list[str],
    *,
    alias_type: str,
    message: str | None = None,
    push: bool = False,
    allow_empty: bool = False,
) -> int:
    if not aliases:
        raise VersiteError("alias requires at least one alias")
    repo = git_root()
    with branch_worktree(
        repo,
        config["branch"],
        remote=config["remote"],
        ignore_remote_status=config.get("ignore_remote_status", False),
    ) as worktree:
        store = _load_store(worktree, config["deploy_prefix"])
        record = store.get(identifier)
        store.upsert(record.version, aliases=aliases)
        for alias in aliases:
            _write_alias(
                worktree,
                config["deploy_prefix"],
                alias,
                record.version,
                alias_type,
                config.get("redirect_template"),
            )
        _save_store(worktree, config["deploy_prefix"], store)
        committed = commit_all(
            worktree,
            message or f"Update aliases for {record.version}",
            allow_empty=allow_empty,
        )
        if push and committed:
            push_branch(worktree, config["remote"], config["branch"])
    return 0


def retitle_version(
    config: dict[str, Any],
    identifier: str,
    title: str,
    *,
    message: str | None = None,
    push: bool = False,
    allow_empty: bool = False,
) -> int:
    repo = git_root()
    with branch_worktree(
        repo,
        config["branch"],
        remote=config["remote"],
        ignore_remote_status=config.get("ignore_remote_status", False),
    ) as worktree:
        store = _load_store(worktree, config["deploy_prefix"])
        store.retitle(identifier, title)
        _save_store(worktree, config["deploy_prefix"], store)
        committed = commit_all(worktree, message or f"Retitle {identifier}", allow_empty=allow_empty)
        if push and committed:
            push_branch(worktree, config["remote"], config["branch"])
    return 0


def _parse_property_edits(edits: list[tuple[str, str | None]]) -> list[tuple[str, str, Any]]:
    parsed: list[tuple[str, str, Any]] = []
    for operation, expression in edits:
        if operation in {"set", "set-string"}:
            path, separator, raw = expression.partition("=")
            path = path.strip()
            if not separator or not path:
                raise VersiteError("property assignment must be in PATH=VALUE form")
            if operation == "set-string":
                value = raw
            else:
                value = json.loads(raw)
            parsed.append(("set", path, value))
        elif operation == "delete":
            if not expression:
                raise VersiteError("property path must not be empty")
            parsed.append(("delete", expression, None))
        elif operation == "set-all":
            value = json.loads(expression)
            if not isinstance(value, dict):
                raise VersiteError("--set-all requires a JSON object")
            parsed.append(("set-all", "", value))
        elif operation == "delete-all":
            parsed.append(("set-all", "", {}))
    return parsed


def _apply_property_edits(
    store: VersionStore, identifier: str, operations: list[tuple[str, str, Any]],
) -> None:
    record = store.get(identifier)
    for operation, path, value in operations:
        if operation == "set":
            store.set_property(identifier, path, value)
        elif operation == "delete":
            store.delete_property(identifier, path)
        else:
            record.properties = value


def props_version(
    config: dict[str, Any],
    identifier: str,
    prop: str | None = None,
    *,
    edits: list[tuple[str, str | None]] | None = None,
    message: str | None = None,
    push: bool = False,
    allow_empty: bool = False,
    as_json: bool = False,
) -> int:
    if edits and prop is not None:
        raise VersiteError("use property-editing flags or a positional property, not both")
    if prop is not None and "=" in prop:
        raise VersiteError("use --set PATH=JSON or --set-string PATH=STRING to edit properties")
    operations = _parse_property_edits(edits or [])
    repo = git_root()
    with branch_worktree(
        repo,
        config["branch"],
        remote=config["remote"],
        ignore_remote_status=config.get("ignore_remote_status", False),
    ) as worktree:
        store = _load_store(worktree, config["deploy_prefix"])
        if not operations:
            value = store.get_properties(identifier) if prop is None else store.get_property(identifier, prop)
            _print(value, as_json)
            return 0
        record = store.get(identifier)
        _apply_property_edits(store, identifier, operations)
        _save_store(worktree, config["deploy_prefix"], store)
        committed = commit_all(
            worktree, message or f"Update properties for {identifier}", allow_empty=allow_empty,
        )
        if push and committed:
            push_branch(worktree, config["remote"], config["branch"])
        _print(record.properties, as_json)
    return 0


def set_default(
    config: dict[str, Any],
    identifier: str,
    *,
    message: str | None = None,
    push: bool = False,
    allow_empty: bool = False,
    allow_undefined: bool = False,
) -> int:
    repo = git_root()
    with branch_worktree(
        repo,
        config["branch"],
        remote=config["remote"],
        ignore_remote_status=config.get("ignore_remote_status", False),
    ) as worktree:
        if not identifier or identifier == ".":
            raise VersiteError("default identifier must not be empty or '.'")
        _identifier_path(worktree, config["deploy_prefix"], identifier)
        if not allow_undefined:
            store = _load_store(worktree, config["deploy_prefix"])
            store.get(identifier)
        write_redirect(
            _site_root(worktree, config["deploy_prefix"]) / "index.html",
            f"./{identifier}/",
            config.get("redirect_template"),
        )
        committed = commit_all(worktree, message or f"Set default site to {identifier}", allow_empty=allow_empty)
        if push and committed:
            push_branch(worktree, config["remote"], config["branch"])
    return 0


def serve_site(config: dict[str, Any], host: str = "127.0.0.1", port: int = 8000) -> int:
    repo = git_root()
    with branch_worktree(
        repo,
        config["branch"],
        remote=config["remote"],
        ignore_remote_status=True,
    ) as worktree:
        serve_directory(worktree, host=host, port=port)
    return 0


def deploy_version(
    config: dict[str, Any],
    version: str,
    aliases: list[str],
    *,
    message: str | None = None,
    push: bool = False,
    allow_empty: bool = False,
    site_dir: str | None = None,
    title: str | None = None,
    edits: list[tuple[str, str | None]] | None = None,
) -> int:
    operations = _parse_property_edits(edits or [])
    repo = git_root()
    if site_dir is None:
        raise VersiteError(
            "deploy requires --site-dir; versite deploys prebuilt static directories only"
        )
    source_site_dir = Path(site_dir).resolve()
    if not source_site_dir.exists():
        raise VersiteError(f"site directory does not exist: {site_dir}")
    if not source_site_dir.is_dir():
        raise VersiteError(f"site directory is not a directory: {site_dir}")
    staged_site_dir = _stage_source_site(source_site_dir)

    try:
        with branch_worktree(
            repo,
            config["branch"],
            remote=config["remote"],
            ignore_remote_status=config.get("ignore_remote_status", False),
        ) as worktree:
            site_root = _site_root(worktree, config["deploy_prefix"])
            site_root.mkdir(parents=True, exist_ok=True)
            version_path = _identifier_path(worktree, config["deploy_prefix"], version)
            store = _load_store(worktree, config["deploy_prefix"])
            existing = store.find(version)
            if title is None:
                title = existing.title if existing is not None else version
            record = store.upsert(version, title=title, aliases=aliases)
            _apply_property_edits(store, version, operations)
            _copy_contents(staged_site_dir, version_path)
            for alias in record.aliases:
                _write_alias(
                    worktree,
                    config["deploy_prefix"],
                    alias,
                    version,
                    config["alias_type"],
                    config.get("redirect_template"),
                )
            default_identifier = aliases[0] if aliases else version
            _ensure_root_redirect(
                worktree,
                config["deploy_prefix"],
                default_identifier,
                config.get("redirect_template"),
            )
            _save_store(worktree, config["deploy_prefix"], store)
            committed = commit_all(
                worktree,
                message or f"Deploy {version}",
                allow_empty=allow_empty,
            )
            if push and committed:
                push_branch(worktree, config["remote"], config["branch"])
    finally:
        shutil.rmtree(staged_site_dir.parent, ignore_errors=True)
    return 0
