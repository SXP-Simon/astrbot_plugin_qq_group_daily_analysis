"""将宿主与模型供应商的用量结构归一化为领域数值。"""

from ....domain.value_objects import TokenUsage
from ....shared.type_guards import is_string_mapping


def parse_token_usage(response: object) -> TokenUsage:
    """从 AstrBot LLMResponse 或原始响应对象解析生成 TokenUsage 值对象 (ACL 防腐)。

    兼容 AstrBot TokenUsage 属性 (input, output, total)、OpenAI Usage 对象
    (prompt_tokens, completion_tokens, total_tokens) 以及字典结构。

    Args:
        response: LLM 响应对象或其 raw_completion 字典。

    Returns:
        TokenUsage: 强类型 Token 消耗统计值对象。
    """
    if response is None:
        return TokenUsage()

    usage = getattr(response, "usage", None)
    if not usage:
        raw_comp = getattr(response, "raw_completion", None)
        if raw_comp and is_string_mapping(raw_comp):
            usage = raw_comp.get("usage")

    if not usage and is_string_mapping(response):
        usage = response.get("usage") or response

    if not usage:
        return TokenUsage()

    def _get_val(*keys_or_attrs: str) -> int:
        for k in keys_or_attrs:
            if is_string_mapping(usage) and k in usage:
                try:
                    return int(str(usage[k] or 0))
                except (TypeError, ValueError):
                    pass
            elif hasattr(usage, k):
                try:
                    return int(str(getattr(usage, k, 0) or 0))
                except (TypeError, ValueError):
                    pass
        return 0

    prompt_tokens = _get_val("input", "prompt_tokens")
    completion_tokens = _get_val("output", "completion_tokens")
    total_tokens = _get_val("total", "total_tokens")
    if total_tokens == 0 and (prompt_tokens > 0 or completion_tokens > 0):
        total_tokens = prompt_tokens + completion_tokens

    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
