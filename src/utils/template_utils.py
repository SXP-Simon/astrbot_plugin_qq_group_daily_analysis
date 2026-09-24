"""安全模板渲染工具（String Template 兼容）"""

import re
from string import Template

from .logger import logger

# 统一默认占位符映射
PLACEHOLDERS = {
    # 分析类核心变量
    "messages_text": "${messages_text}",
    "reviews_text": "${reviews_text}",
    "max_topics": "${max_topics}",
    "users_text": "${users_text}",
    "max_golden_quotes": "${max_golden_quotes}",
    # 文件名渲染类变量
    "group_id": "${group_id}",
    "date": "${date}",
    "ulid": "${ulid}",
}


def is_str_format_template(template: str) -> bool:
    """判断模板字符串是否为 str.format 风格。

    Args:
        template: 待检查的模板字符串。

    Returns:
        True 表示使用 str.format 语法，False 表示不是。
    """
    if not template:
        return False

    # 1. 预先建立排除模式 (匹配 ${var} 或 $var)
    dollar_patterns = [re.escape(v) for v in PLACEHOLDERS.values()] + [
        rf"\${re.escape(k)}" for k in PLACEHOLDERS.keys()
    ]
    exclude_regex = "|".join(dollar_patterns)

    # 如果包含任何 $ 相关的占位符，则不视为主流 str.format 模板
    if re.search(exclude_regex, template):
        return False

    # 2. 检查是否包含标准的花括号占位符 {key}
    for key in PLACEHOLDERS.keys():
        pattern = rf"(?<![\{{\$])\{{{key}\}}(?!\}})"
        if re.search(pattern, template):
            return True
    return False


def upgrade_str_format_template(template: str) -> tuple[str, bool]:
    """如果模板是 str.format 风格，则自动升级为 string.Template 语法。

    Args:
        template: 待转换的模板字符串。

    Returns:
        元组 (升级后的模板字符串, 是否发生了升级)。
    """
    if template is None:
        return "", False

    if not is_str_format_template(template):
        return template, False

    # 先转义原文中的 $，避免被 Template 误解释为占位符
    safe_template = template.replace("$", "$$")

    # 将 {var} 转为 ${var}
    safe_template = re.sub(
        r"(?<![\{\$])\{([_a-zA-Z][_a-zA-Z0-9]*)\}(?!\})",
        lambda m: f"${{{m.group(1)}}}",
        safe_template,
    )

    # 将双大括号回退为单括号（str.format 里表示字面量大括号）
    safe_template = safe_template.replace("{{", "{").replace("}}", "}")

    return safe_template, True


def render_template(template: str, strict: bool = False, **kwargs) -> str:
    """安全渲染 string.Template 模板。

    Args:
        template: 模板字符串。
        strict: 是否使用严格模式（缺少变量时直接抛出异常）。
        **kwargs: 传入的模板替换变量。

    Returns:
        渲染后的文本字符串。

    Raises:
        KeyError: 当 strict 为 True 且缺失必要占位符变量时抛出。
    """
    if template is None:
        return ""

    try:
        t = Template(template)
        return t.substitute(**kwargs) if strict else t.safe_substitute(**kwargs)
    except Exception as e:
        if strict:
            raise
        logger.warning(
            f"[template_utils] 模板渲染失败，返回原始文本，错误: {e}",
            exc_info=True,
        )
        return template
