from __future__ import annotations


def _to_text(value: object) -> str:
    return str(value).strip()


def _to_float(value: object) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _validate_topic_item(
    item: dict[str, object],
) -> tuple[dict[str, object] | None, str | None]:
    topic = _to_text(item.get("topic", ""))
    detail = _to_text(item.get("detail", ""))
    contributors_raw = item.get("contributors", [])
    contributors: list[str] = []
    if isinstance(contributors_raw, list):
        for contributor in contributors_raw:
            text = _to_text(contributor)
            if text:
                contributors.append(text)

    if not topic:
        return None, "topic is required"
    if not detail:
        return None, "detail is required"

    return {"topic": topic, "contributors": contributors, "detail": detail}, None


def _validate_user_title_item(
    item: dict[str, object],
) -> tuple[dict[str, object] | None, str | None]:
    normalized: dict[str, object] = {
        "name": _to_text(item.get("name", "")),
        "user_id": _to_text(item.get("user_id", "")),
        "title": _to_text(item.get("title", "")),
        "mbti": _to_text(item.get("mbti", "")),
        "reason": _to_text(item.get("reason", "")),
    }
    if not normalized["name"] or not normalized["user_id"] or not normalized["title"]:
        return None, "name/user_id/title are required"
    return normalized, None


def _validate_golden_quote_item(
    item: dict[str, object],
) -> tuple[dict[str, object] | None, str | None]:
    normalized: dict[str, object] = {
        "content": _to_text(item.get("content", "")),
        "sender": _to_text(item.get("sender", "")),
        "reason": _to_text(item.get("reason", "")),
    }
    if not normalized["content"] or not normalized["sender"]:
        return None, "content/sender are required"
    return normalized, None


def _validate_quality_dimension(
    item: dict[str, object],
) -> tuple[dict[str, object] | None, str | None]:
    name = _to_text(item.get("name", ""))
    comment = _to_text(item.get("comment", ""))
    percentage = _to_float(item.get("percentage", 0))
    if not name:
        return None, "dimension name is required"
    if not comment:
        return None, "dimension comment is required"
    if percentage is None:
        return None, "dimension percentage must be numeric"
    return {"name": name, "percentage": percentage, "comment": comment}, None


def validate_topic_items(
    data_list: list[dict[str, object]],
) -> tuple[bool, list[dict[str, object]] | None, str | None]:
    normalized: list[dict[str, object]] = []
    for idx, item in enumerate(data_list, start=1):
        valid_item, err = _validate_topic_item(item)
        if valid_item is None:
            return False, None, f"topic item #{idx}: {err}"
        normalized.append(valid_item)
    return True, normalized, None


def validate_user_title_items(
    data_list: list[dict[str, object]],
) -> tuple[bool, list[dict[str, object]] | None, str | None]:
    normalized: list[dict[str, object]] = []
    for idx, item in enumerate(data_list, start=1):
        valid_item, err = _validate_user_title_item(item)
        if valid_item is None:
            return False, None, f"user title item #{idx}: {err}"
        normalized.append(valid_item)
    return True, normalized, None


def validate_golden_quote_items(
    data_list: list[dict[str, object]],
) -> tuple[bool, list[dict[str, object]] | None, str | None]:
    normalized: list[dict[str, object]] = []
    for idx, item in enumerate(data_list, start=1):
        valid_item, err = _validate_golden_quote_item(item)
        if valid_item is None:
            return False, None, f"golden quote item #{idx}: {err}"
        normalized.append(valid_item)
    return True, normalized, None


def validate_quality_review_item(
    data: dict[str, object],
) -> tuple[bool, dict[str, object] | None, str | None]:
    title = _to_text(data.get("title", ""))
    subtitle = _to_text(data.get("subtitle", ""))
    summary = _to_text(data.get("summary", ""))
    dimensions_raw = data.get("dimensions", [])
    if not isinstance(dimensions_raw, list):
        return False, None, "dimensions must be a list"
    dimensions_items: list[object] = list(dimensions_raw)

    dimensions: list[dict[str, object]] = []
    for idx, dim in enumerate(dimensions_items, start=1):
        if not isinstance(dim, dict):
            return False, None, f"dimension #{idx} must be an object"
        valid_dimension, err = _validate_quality_dimension(dim)
        if valid_dimension is None:
            return False, None, f"dimension #{idx}: {err}"
        dimensions.append(valid_dimension)

    if not title:
        return False, None, "title is required"
    if not subtitle:
        return False, None, "subtitle is required"
    if not summary:
        return False, None, "summary is required"

    return (
        True,
        {
            "title": title,
            "subtitle": subtitle,
            "dimensions": dimensions,
            "summary": summary,
        },
        None,
    )
