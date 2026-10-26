"""在宿主配置定义中补入已保存的自定义资源选项。"""

from .rendering_config import parse_rendering_strategies


def sync_rendering_schema_options(schema: object, rendering: dict) -> None:
    """让原生选择框能够显示并再次选择已持久化的自定义地址。

    Args:
        schema: AstrBot 持有的插件配置定义；离线桩可能不提供。
        rendering: 当前图片渲染配置，不会被修改。

    Returns:
        无返回值，只更新内存中的选项，不改写 Schema 文件。
    """
    if not isinstance(schema, dict):
        return
    group = schema.get("t2i_rendering", {})
    if not isinstance(group, dict):
        return
    fields = group.get("items", {})
    if not isinstance(fields, dict):
        return
    strategies = fields.get("t2i_rendering_strategies", {})
    if not isinstance(strategies, dict):
        return
    templates = strategies.get("templates", {})
    raw = rendering.get("t2i_rendering_strategies", [])
    if not isinstance(templates, dict) or not isinstance(raw, list):
        return
    for item in raw:
        try:
            plan = parse_rendering_strategies([item])[0]
        except ValueError:
            continue
        for template in templates.values():
            if not isinstance(template, dict) or not isinstance(
                template.get("items"), dict
            ):
                continue
            for key in ("cdn_base_url", "google_fonts", "gstatic"):
                field = template["items"].get(key)
                if not isinstance(field, dict):
                    continue
                options = field.get("options")
                if not isinstance(options, list) or plan[key] in options:
                    continue
                labels = field.get("labels")
                # 先补齐显示名，再添加地址，确保 labels 与 options 一一对应。
                if not isinstance(labels, list):
                    labels = [str(value) for value in options]
                else:
                    labels = list(labels[: len(options)])
                    labels.extend(str(value) for value in options[len(labels) :])
                field["options"] = [*options, plan[key]]
                field["labels"] = [*labels, f"自定义 · {plan[key]}"]
