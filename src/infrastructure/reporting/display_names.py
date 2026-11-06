"""HTML 与原生图片报告共用的昵称展示规则。"""

import unicodedata


def normalize_display_name(name: str) -> str:
    """清理昵称中的控制字符与换行，不改动原始身份数据。

    Args:
        name: 平台昵称或分析结果中的发言人名称。

    Returns:
        合并空白后的展示名称；保留 Emoji 连接符、变体选择符和正常文字。
    """
    return " ".join(
        "".join(
            char
            for char in name
            if char.isspace() or unicodedata.category(char) != "Cc"
        ).split()
    )
