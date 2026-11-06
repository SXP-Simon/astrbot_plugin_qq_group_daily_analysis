"""外部接口边界的基础类型守卫，不代替具体业务字段校验。"""

import inspect
from collections.abc import Awaitable, Collection, Mapping
from typing import TypeGuard, cast


def is_string_mapping(value: object) -> TypeGuard[dict[str, object]]:
    """检查字典是否使用字符串键，不对字段值作未经验证的类型承诺。

    Args:
        value: 尚未验证的外部数据。

    Returns:
        输入为字符串键字典时返回 True。
    """
    if not is_object_mapping(value):
        return False
    return all(isinstance(key, str) for key in value)


def is_object_list(value: object) -> TypeGuard[list[object]]:
    """检查列表结构，元素保持未知，交给具体字段解析逻辑继续校验。

    Args:
        value: 尚未验证的外部数据。

    Returns:
        输入为列表时返回 True。
    """
    return isinstance(value, list)


def is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """检查字典结构，键和值均保持未知，兼容整数小时键等历史数据。

    Args:
        value: 尚未验证的外部数据。

    Returns:
        输入为字典时返回 True。
    """
    return isinstance(value, dict)


def is_object_collection(value: object) -> TypeGuard[Collection[object]]:
    """检查外部接口常见的列表、元组或集合，不将字符串当作条目集合。

    Args:
        value: 尚未验证的外部数据。

    Returns:
        输入为列表、元组或集合时返回 True，元素仍需校验。
    """
    return isinstance(value, (list, tuple, set))


def is_object_awaitable(value: object) -> TypeGuard[Awaitable[object]]:
    """兼容宿主同步与异步接口，异步结果仍保持未知类型。

    Args:
        value: 宿主方法返回的对象。

    Returns:
        输入可等待时返回 True。
    """
    return inspect.isawaitable(value)


def is_string_key_mapping(value: object) -> TypeGuard[Mapping[str, object]]:
    """校验宿主返回的只读映射，保留非 dict 的 Mapping 实现。

    Args:
        value: 外部映射候选。

    Returns:
        是否为仅包含字符串键的映射。
    """
    if not isinstance(value, Mapping):
        return False
    # Mapping 的泛型在运行时不可检查，先以 object 键遍历，再验证键的类型。
    mapping = cast("Mapping[object, object]", value)
    return all(isinstance(key, str) for key in mapping)
