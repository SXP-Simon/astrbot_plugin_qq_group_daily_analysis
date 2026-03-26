from __future__ import annotations

from typing import TypeAlias

JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | dict[str, "JSONValue"] | list["JSONValue"]
JSONObject: TypeAlias = dict[str, JSONValue]


def build_response_format(name: str, schema: JSONObject) -> JSONObject:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": schema,
        },
    }


def build_topics_schema(max_items: int) -> JSONObject:
    return {
        "type": "array",
        "maxItems": max(1, int(max_items)),
        "items": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "contributors": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "detail": {"type": "string"},
            },
            "required": ["topic", "contributors", "detail"],
            "additionalProperties": False,
        },
    }


def build_user_titles_schema(max_items: int) -> JSONObject:
    return {
        "type": "array",
        "maxItems": max(1, int(max_items)),
        "items": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "user_id": {"type": "string"},
                "title": {"type": "string"},
                "mbti": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["name", "user_id", "title", "mbti", "reason"],
            "additionalProperties": False,
        },
    }


def build_golden_quotes_schema(max_items: int) -> JSONObject:
    return {
        "type": "array",
        "maxItems": max(1, int(max_items)),
        "items": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "sender": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["content", "sender", "reason"],
            "additionalProperties": False,
        },
    }


def build_chat_quality_schema(max_dimensions: int) -> JSONObject:
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "subtitle": {"type": "string"},
            "dimensions": {
                "type": "array",
                "maxItems": max(1, int(max_dimensions)),
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "percentage": {"type": "number"},
                        "comment": {"type": "string"},
                    },
                    "required": ["name", "percentage", "comment"],
                    "additionalProperties": False,
                },
            },
            "summary": {"type": "string"},
        },
        "required": ["title", "subtitle", "dimensions", "summary"],
        "additionalProperties": False,
    }
