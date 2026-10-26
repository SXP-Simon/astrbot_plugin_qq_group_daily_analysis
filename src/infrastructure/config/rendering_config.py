"""可扩展图片渲染方案的配置契约与边界校验。"""

from typing import Literal, TypedDict


class RenderingStrategyConfig(TypedDict):
    """配置面板中的单个渲染方案，数值越小越先执行。"""

    name: str
    priority: int
    environment: Literal["Mainland", "Overseas"]
    type: Literal["png", "jpeg"]
    quality: int
    device_scale: Literal["normal", "high", "ultra"]
    timeout: int


DEFAULT_RENDERING_STRATEGY: RenderingStrategyConfig = {
    "name": "默认方案",
    "priority": 10,
    "environment": "Overseas",
    "type": "png",
    "quality": 80,
    "device_scale": "high",
    "timeout": 20000,
}


def parse_rendering_strategies(value: object) -> list[RenderingStrategyConfig]:
    """校验方案列表并按优先级稳定排序，不修改输入，运行时只读取已声明字段。

    Args:
        value: 配置文件或保存请求中的方案列表。

    Returns:
        供运行时使用的规范化方案；相同优先级保持原列表顺序。

    Raises:
        ValueError: 列表、方案字段或参数范围无效。
    """
    if not isinstance(value, list):
        raise ValueError("渲染方案必须是列表")
    result: list[RenderingStrategyConfig] = []
    for index, item in enumerate(value, 1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 个渲染方案必须是配置对象")
        name = item.get("name", "渲染方案")
        environment = item.get("environment", "Overseas")
        image_type = item.get("type", "png")
        scale = item.get("device_scale", "high")
        if not isinstance(name, str):
            raise ValueError(f"第 {index} 个渲染方案的名称必须是文字")
        if environment not in ("Mainland", "Overseas"):
            raise ValueError(f"第 {index} 个渲染方案请选择内地或海外环境")
        if image_type not in ("png", "jpeg"):
            raise ValueError(f"第 {index} 个渲染方案请选择 PNG 或 JPEG 格式")
        if scale not in ("normal", "high", "ultra"):
            raise ValueError(f"第 {index} 个渲染方案的分辨率等级无效")
        integers = {}
        for key, label, default, lower, upper in (
            ("priority", "优先级", 10, 0, 10000),
            ("quality", "图片质量", 80, 1, 100),
            ("timeout", "渲染超时", 20000, 1000, 300000),
        ):
            number = item.get(key, default)
            if type(number) is not int or not lower <= number <= upper:
                raise ValueError(
                    f"第 {index} 个渲染方案的{label} 必须是 {lower} 到 {upper} 的整数"
                )
            integers[key] = number
        result.append(
            {
                "name": name,
                "priority": integers["priority"],
                "environment": environment,
                "type": image_type,
                "quality": integers["quality"],
                "device_scale": scale,
                "timeout": integers["timeout"],
            }
        )
    return sorted(result, key=lambda strategy: strategy["priority"])
