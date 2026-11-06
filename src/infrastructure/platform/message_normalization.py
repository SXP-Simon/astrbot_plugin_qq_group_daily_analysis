"""平台及历史数据入口的图片表情标记兼容。"""

from ...shared.type_guards import is_string_mapping


def is_image_sticker(data: object) -> bool:
    """将协议中的图片标记转换为明确的表情属性。

    Args:
        data: 平台图片字段或旧快照的原始图片数据。

    Returns:
        是否有明确表情标记；显式子类型优先于摘要，不按 URL 推断。
    """
    if is_string_mapping(data):
        explicit = data.get("is_sticker")
        if isinstance(explicit, bool):
            return explicit
        sub_type = data.get("subType", data.get("sub_type"))
        if sub_type is not None:
            return str(sub_type) == "1"
        if data.get("sticker_id"):
            return True
        summary = str(data.get("summary", ""))
    else:
        summary = data if isinstance(data, str) else ""
    return "表情" in summary
