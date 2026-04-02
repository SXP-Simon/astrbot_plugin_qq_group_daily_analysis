"""安全模板渲染工具（String Template 兼容）"""

import re
from string import Template

from ...utils.logger import logger

# 统一默认 placeholder
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
    """判断模板是否为 str.format 风格。

    只认为满足：
    1) 不包含 String Template `${var}` 或 `$var`
    2) 包含 str.format `{var}`（非 `{{...}}`）
    """
    if not template:
        return False

    # 1. 預先建立排除模式 (匹配 ${var} 或 $var)
    # 使用 set 去重並組合
    dollar_patterns = [re.escape(v) for v in PLACEHOLDERS.values()] + [
        rf"\${re.escape(k)}" for k in PLACEHOLDERS.keys()
    ]
    exclude_regex = "|".join(dollar_patterns)

    # 如果包含任何 $ 相關的佔位符，則不視為 str.format 模板
    if re.search(exclude_regex, template):
        return False

    # 2. 檢查是否包含標準的 {key}，確保匹配單個花括號包裹的 Key
    for key in PLACEHOLDERS.keys():
        # (?<!\{)  前面不能有 {
        # \{{key}\} 匹配 {key}
        # (?!\})   後面不能有 }
        # (?<!\$)  前面不能有 $
        pattern = rf"(?<![\{{\$])\{{{key}\}}(?!\}})"
        if re.search(pattern, template):
            return True
    return False


def upgrade_str_format_template(template: str) -> tuple[str, bool]:
    """如果模板是 str.format 风格，则自动升级为 string.Template。

    返回 (升级后的模板, 是否升级)
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

    # 将双括号回退为单括号（str.format 里表示字面量大括号）
    safe_template = safe_template.replace("{{", "{").replace("}}", "}")

    return safe_template, True


def render_template(template: str, strict: bool = False, **kwargs) -> str:
    """渲染模板（String Template）。

    Args:
        template: 模板字符串
        strict: 是否使用严格模式（变量缺失则抛出异常）
        **kwargs: 渲染变量

    由于插件启动时已完成 str.format 兼容升级，运行时直接按 string.Template 渲染。
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
