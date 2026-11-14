"""宿主回退模型配置的读取规则，供运行时和只读配置展示共用。"""

from collections.abc import Mapping

from ....shared.type_guards import is_object_list, is_string_mapping


def get_configured_host_fallback_ids(config: Mapping[str, object]) -> list[str]:
    """按宿主生效版本读取配置顺序，不重新启用遗留字段。

    Args:
        config: 宿主默认配置或对应会话的生效配置。

    Returns:
        去重后的配置模型 ID，包含尚未加载或已删除的模型。

    Raises:
        ValueError: 当前配置结构或回退列表格式无效。
    """
    if "agent" in config:
        path = ("agent", "config", "model", "fallback_provider_ids")
    elif "agent_runner" in config:
        path = ("agent_runner", "config", "model", "fallback_provider_ids")
    else:
        path = ("provider_settings", "fallback_chat_models")
    value: object = dict(config)
    for key in path:
        if value is None:
            return []
        if not is_string_mapping(value):
            raise ValueError("宿主模型配置结构无效")
        value = value.get(key)
    if value is None:
        return []
    if not is_object_list(value):
        raise ValueError("宿主回退模型列表格式无效")
    return list(
        dict.fromkeys(
            item.strip() for item in value if isinstance(item, str) and item.strip()
        )
    )
