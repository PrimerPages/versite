from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from versite.jsonpath import delete_path, get_path, set_path


@dataclass
class VersionRecord:
    version: str
    title: str
    aliases: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VersionRecord":
        return cls(
            version=data["version"],
            title=data.get("title", data["version"]),
            aliases=list(data.get("aliases", [])),
            properties=dict(data.get("properties", {})),
        )


class VersionStore:
    def __init__(self, records: list[VersionRecord] | None = None) -> None:
        self.records = records or []

    @classmethod
    def load(cls, path: Path) -> "VersionStore":
        if not path.exists():
            return cls([])
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls([VersionRecord.from_dict(item) for item in data])

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(record) for record in self.records]
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def as_list(self) -> list[dict[str, Any]]:
        return [asdict(record) for record in self.records]

    def find(self, identifier: str) -> VersionRecord | None:
        for record in self.records:
            if record.version == identifier or identifier in record.aliases:
                return record
        return None

    def get(self, identifier: str) -> VersionRecord:
        record = self.find(identifier)
        if record is None:
            raise KeyError(f"unknown version or alias: {identifier}")
        return record

    def remove_alias_globally(self, alias: str) -> None:
        for record in self.records:
            if alias in record.aliases:
                record.aliases = [item for item in record.aliases if item != alias]

    def upsert(self, version: str, title: str | None = None, aliases: list[str] | None = None) -> VersionRecord:
        record = next((item for item in self.records if item.version == version), None)
        if record is None:
            record = VersionRecord(version=version, title=title or version)
            self.records.append(record)
        elif title is not None:
            record.title = title
        if aliases:
            for alias in aliases:
                if alias == version:
                    continue
                if any(existing.version == alias for existing in self.records):
                    raise ValueError(f"alias conflicts with version name: {alias}")
                self.remove_alias_globally(alias)
                if alias not in record.aliases:
                    record.aliases.append(alias)
        return record

    def delete_identifier(self, identifier: str) -> tuple[str | None, list[str]]:
        for index, record in enumerate(self.records):
            if record.version == identifier:
                removed = self.records.pop(index)
                return removed.version, list(removed.aliases)
            if identifier in record.aliases:
                record.aliases = [alias for alias in record.aliases if alias != identifier]
                return None, [identifier]
        raise KeyError(f"unknown version or alias: {identifier}")

    def retitle(self, identifier: str, title: str) -> VersionRecord:
        record = self.get(identifier)
        record.title = title
        return record

    def get_properties(self, identifier: str) -> dict[str, Any]:
        return self.get(identifier).properties

    def get_property(self, identifier: str, path: str) -> Any:
        return get_path(self.get(identifier).properties, path)

    def set_property(self, identifier: str, path: str, value: Any) -> dict[str, Any]:
        record = self.get(identifier)
        set_path(record.properties, path, value)
        return record.properties

    def delete_property(self, identifier: str, path: str) -> dict[str, Any]:
        record = self.get(identifier)
        delete_path(record.properties, path)
        return record.properties
