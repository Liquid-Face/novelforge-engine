"""Shared parsing and shape checks for structured LLM responses."""
from __future__ import annotations

import json
from typing import Any


def parse_json_response(text: str) -> Any:
    """Parse plain or fenced JSON returned by an LLM."""
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned[3:-3].strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()
    return json.loads(cleaned)


def parse_json_object(text: str, required: tuple[str, ...]) -> dict[str, Any] | None:
    try:
        value = parse_json_response(text)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or any(key not in value for key in required):
        return None
    return value


def parse_json_array(text: str) -> list[Any] | None:
    try:
        value = parse_json_response(text)
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, list) else None


def has_string_fields(value: dict[str, Any], fields: tuple[str, ...]) -> bool:
    return all(isinstance(value.get(field), str) for field in fields)
