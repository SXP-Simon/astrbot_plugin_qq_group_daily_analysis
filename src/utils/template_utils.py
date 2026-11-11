"""安全模板渲染工具（String Template 兼容）"""

from __future__ import annotations

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
        rf"\${re.escape(k)}" for k in PLACEHOLDERS
    ]
    exclude_regex = "|".join(dollar_patterns)

    # 如果包含任何 $ 相关的占位符，则不视为主流 str.format 模板
    if re.search(exclude_regex, template):
        return False

    # 2. 检查是否包含标准的花括号占位符 {key}
    for key in PLACEHOLDERS:
        pattern = rf"(?<![\{{\$])\{{{key}\}}(?!\}})"
        if re.search(pattern, template):
            return True
    return False


# 匹配 ${var} 占位符，或一段连续的 { / }
_BRACE_TOKEN_RE = re.compile(r"\$\{[_a-zA-Z][_a-zA-Z0-9]*\}|\{+|\}+")


def unescape_doubled_braces(template: str) -> tuple[str, bool]:
    """还原 string.Template 模板中残留的 str.format 转义大括号。

    旧版默认提示词把占位符换成 ${var} 后，示例 JSON 里的 {{ 和 }} 没有同步还原。
    string.Template 不识别这种转义，双大括号会原样发给模型并被模型照抄。

    仅当占位符之外每一段连续大括号的长度都是偶数时才还原：转义过的模板满足
    这一点，而正常书写的 JSON 至少有一个单独的 {，不会被误改（例如嵌套对象
    结尾的 }} 会保持原样）。

    Args:
        template: 待检查的模板字符串。

    Returns:
        元组 (还原后的模板字符串, 是否发生了还原)。
    """
    runs = [
        m.group()
        for m in _BRACE_TOKEN_RE.finditer(template)
        if not m.group().startswith("$")
    ]
    if not runs or any(len(run) % 2 for run in runs):
        return template, False

    restored = _BRACE_TOKEN_RE.sub(
        lambda m: (
            m.group() if m.group().startswith("$") else m.group()[: len(m.group()) // 2]
        ),
        template,
    )
    return restored, True


def upgrade_str_format_template(template: str | None) -> tuple[str, bool]:
    """将旧版模板升级为 string.Template 语法。

    str.format 风格的模板会转换占位符并还原转义大括号；已经使用 ${var} 但仍
    残留 {{ / }} 的模板只还原大括号。

    Args:
        template: 待转换的模板字符串。

    Returns:
        元组 (升级后的模板字符串, 是否发生了升级)。
    """
    if template is None:
        return "", False

    if not is_str_format_template(template):
        return unescape_doubled_braces(template)

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


def render_template(
    template: str | None, strict: bool = False, **kwargs: object
) -> str:
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
