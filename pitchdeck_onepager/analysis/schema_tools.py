"""Turn a Pydantic model into a provider-compatible JSON schema.

Both Anthropic structured outputs and OpenAI strict JSON schema reject a subset
of JSON Schema (numeric/length constraints, ``additionalProperties`` other than
``false``) and require every object to list all of its properties as required.
Pydantic emits schemas that violate all three rules, so this module rewrites
them. Semantic constraints removed here are re-checked in
:mod:`analysis.validation`.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

#: Keywords the providers do not support and that must be stripped.
_UNSUPPORTED_KEYWORDS = {
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minProperties",
    "maxProperties",
    "format",
    "default",
    "examples",
    "$comment",
    "readOnly",
    "writeOnly",
}


def _flatten_nullable(node: dict[str, Any]) -> dict[str, Any]:
    """Rewrite Pydantic's ``anyOf: [T, null]`` into ``type: [T, "null"]``.

    Keeps the schema shallower, which both providers handle more reliably.
    """
    any_of = node.get("anyOf")
    if not isinstance(any_of, list) or len(any_of) != 2:
        return node

    non_null = [item for item in any_of if item.get("type") != "null"]
    nulls = [item for item in any_of if item.get("type") == "null"]
    if len(non_null) != 1 or len(nulls) != 1:
        return node

    inner = non_null[0]
    inner_type = inner.get("type")
    if not isinstance(inner_type, str):
        return node

    merged = {k: v for k, v in node.items() if k != "anyOf"}
    merged.update({k: v for k, v in inner.items() if k != "type"})
    merged["type"] = [inner_type, "null"]
    return merged


def sanitize_schema(node: Any) -> Any:
    """Recursively make a JSON schema safe for structured-output APIs."""
    if isinstance(node, list):
        return [sanitize_schema(item) for item in node]
    if not isinstance(node, dict):
        return node

    node = _flatten_nullable(dict(node))
    cleaned: dict[str, Any] = {}
    for key, value in node.items():
        if key in _UNSUPPORTED_KEYWORDS:
            continue
        cleaned[key] = sanitize_schema(value)

    if cleaned.get("type") == "object" or "properties" in cleaned:
        properties = cleaned.get("properties", {})
        cleaned["additionalProperties"] = False
        # Strict mode requires every property to be listed as required;
        # nullability is expressed through the type union instead.
        cleaned["required"] = list(properties.keys())

    return cleaned


def build_schema(model: type) -> dict[str, Any]:
    """JSON schema for a Pydantic model, sanitised for structured outputs."""
    raw = model.model_json_schema()
    schema = sanitize_schema(deepcopy(raw))
    schema.pop("title", None)
    return schema
