from __future__ import annotations

import json
import re
from typing import Any


TOKEN_RE = re.compile(r"([^.[]+)|\[(\d+)\]")


def parse_path(path: str) -> list[str | int]:
    if not path:
        return []
    tokens: list[str | int] = []
    for match in TOKEN_RE.finditer(path):
        key, index = match.groups()
        if key is not None:
            tokens.append(key)
        else:
            tokens.append(int(index))
    if not tokens:
        raise ValueError(f"invalid property path: {path}")
    return tokens


def get_path(data: Any, path: str) -> Any:
    current = data
    for token in parse_path(path):
        current = current[token]
    return current


def set_path(data: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    tokens = parse_path(path)
    current: Any = data
    for index, token in enumerate(tokens[:-1]):
        next_token = tokens[index + 1]
        if isinstance(token, int):
            while len(current) <= token:
                current.append({} if isinstance(next_token, str) else [])
            current = current[token]
            continue
        if token not in current or not isinstance(current[token], (dict, list)):
            current[token] = {} if isinstance(next_token, str) else []
        current = current[token]
    last = tokens[-1]
    if isinstance(last, int):
        while len(current) <= last:
            current.append(None)
        current[last] = value
    else:
        current[last] = value
    return data


def delete_path(data: dict[str, Any], path: str) -> None:
    tokens = parse_path(path)
    current: Any = data
    for token in tokens[:-1]:
        current = current[token]
    last = tokens[-1]
    if isinstance(last, int):
        del current[last]
    else:
        del current[last]


def parse_assignment(expression: str) -> tuple[str, str]:
    if "=" not in expression:
        raise ValueError("property assignment must be in PATH=VALUE form")
    path, value = expression.split("=", 1)
    return path.strip(), value.strip()


def parse_value(raw: str) -> Any:
    if raw == "":
        return ""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
