from __future__ import annotations

from versite.versions import VersionStore


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
