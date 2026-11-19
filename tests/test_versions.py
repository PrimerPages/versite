from __future__ import annotations

import json
from pathlib import Path

from versite.versions import VersionRecord, VersionStore


def test_upsert_and_alias_reassignment() -> None:
    store = VersionStore()
    store.upsert("1.0", aliases=["latest"])
    store.upsert("2.0", aliases=["latest", "stable"])
    first = store.get("1.0")
    second = store.get("2.0")
    assert first.aliases == []
    assert second.aliases == ["latest", "stable"]


def test_delete_version_and_alias() -> None:
    store = VersionStore()
    store.upsert("1.0", aliases=["latest"])
    version, aliases = store.delete_identifier("latest")
    assert version is None
    assert aliases == ["latest"]
    version, aliases = store.delete_identifier("1.0")
    assert version == "1.0"
    assert aliases == []


def test_properties_round_trip() -> None:
    store = VersionStore()
    store.upsert("1.0")
    store.set_property("1.0", "meta.channel", "stable")
    assert store.get_property("1.0", "meta.channel") == "stable"
    store.delete_property("1.0", "meta.channel")
    assert store.get_properties("1.0") == {"meta": {}}


def test_versions_are_newest_first_with_dev_pinned() -> None:
    versions = ["v2.0.0", "v1.0.0", "v2.2.0", "v2.2.1", "v2.9.0", "dev", "v2.10.0", "v10.0.0"]
    store = VersionStore([VersionRecord(version=item, title=item) for item in versions])
    assert [item["version"] for item in store.as_list()] == [
        "dev", "v10.0.0", "v2.10.0", "v2.9.0", "v2.2.1", "v2.2.0", "v2.0.0", "v1.0.0"
    ]


def test_loose_release_formats_and_prereleases() -> None:
    versions = ["1.0b1", "1.0rc1", "1.0", "1.0a1", "0.9", "2.1", "2.0"]
    store = VersionStore([VersionRecord(version=item, title=item) for item in versions])
    assert [item["version"] for item in store.as_list()] == [
        "2.1", "2.0", "1.0", "1.0rc1", "1.0b1", "1.0a1", "0.9"
    ]


def test_mixed_prefixes_follow_mike_comparison() -> None:
    versions = ["v2.9.0", "2.10.0", "v2.10.0", "2.9.0"]
    store = VersionStore([VersionRecord(version=item, title=item) for item in versions])
    assert [item["version"] for item in store.as_list()] == [
        "2.10.0", "2.9.0", "v2.10.0", "v2.9.0"
    ]


def test_development_versions_precede_numbered_releases() -> None:
    store = VersionStore()
    for version in ["feature/search", "v2.2.1", "nightly", "dev", "devel", "10"]:
        store.upsert(version)
    assert [item["version"] for item in store.as_list()] == [
        "nightly", "feature/search", "devel", "dev", "10", "v2.2.1"
    ]


def test_save_sorts_existing_manifest_without_losing_metadata(tmp_path: Path) -> None:
    path = tmp_path / "versions.json"
    original = [
        {"version": "v2.0.0", "title": "Old release", "aliases": [], "properties": {"channel": "stable"}},
        {"version": "dev", "title": "Development", "aliases": [], "properties": {}},
        {"version": "v2.2.1", "title": "Current release", "aliases": ["latest"], "properties": {"custom": [1, 2]}},
    ]
    path.write_text(json.dumps(original))
    store = VersionStore.load(path)
    store.save(path)
    saved = json.loads(path.read_text())
    assert saved == [original[1], original[2], original[0]]
    assert VersionStore.load(path).as_list() == saved
