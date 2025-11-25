"""
JSON处理工具模块
提供JSON解析、修复和正则提取功能
"""

import json
import re

from astrbot.api import logger


def fix_json(text: str) -> str:
    """
    修复JSON格式问题，包括中文符号替换

    Args:
        text: 需要修复的JSON文本

    Returns:
        修复后的JSON文本
    """
    try:
        # 1. 移除markdown代码块标记
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*$", "", text)

        # 2. 基础清理
        text = text.replace("\n", " ").replace("\r", " ")
        text = re.sub(r"\s+", " ", text)

        # 3. 替换中文符号为英文符号（修复）
        # 中文引号 -> 英文引号
        text = text.replace("“", '"').replace("”", '"')
        text = text.replace("‘", "'").replace("’", "'")
        # 中文逗号 -> 英文逗号
        text = text.replace("，", ",")
        # 中文冒号 -> 英文冒号
        text = text.replace("：", ":")
        # 中文括号 -> 英文括号
        text = text.replace("（", "(").replace("）", ")")
        text = text.replace("【", "[").replace("】", "]")

        # 4. 处理字符串内容中的特殊字符
        # 转义字符串内的双引号
        def escape_quotes_in_strings(match):
            content = match.group(1)
            # 转义内部的双引号
            content = content.replace('"', '\\"')
            return f'"{content}"'

        # 先处理字段值中的引号
        text = re.sub(r'"([^"]*(?:"[^"]*)*)"', escape_quotes_in_strings, text)

        # 5. 修复截断的JSON
        if not text.endswith("]"):
            last_complete = text.rfind("}")
            if last_complete > 0:
                text = text[: last_complete + 1] + "]"

        # 6. 修复常见的JSON格式问题
        # 1. 修复缺失的逗号
        text = re.sub(r"}\s*{", "}, {", text)

        # 2. 确保字段名有引号（仅在对象开始或逗号后，避免破坏字符串值）
        def quote_field_names(match):
            prefix = match.group(1)
            key = match.group(2)
            return f'{prefix}"{key}":'

        # 只在 { 或 , 后面匹配字段名，避免在字符串值中误匹配
        text = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:", quote_field_names, text)

        # 3. 移除多余的逗号
        text = re.sub(r",\s*}", "}", text)
        text = re.sub(r",\s*]", "]", text)

        return text.strip()

    except Exception as e:
        logger.error(f"JSON修复失败: {e}")
        return text


def parse_json_response(
    result_text: str, data_type: str
) -> tuple[bool, list[dict] | None, str | None]:
    """
    统一的JSON解析方法

    Args:
        result_text: LLM返回的原始文本
        data_type: 数据类型 ('topics' | 'user_titles' | 'golden_quotes')

    Returns:
        (成功标志, 解析后的数据列表, 错误消息)
    """
    try:
        # 1. 提取JSON部分
        json_match = re.search(r"\[.*?\]", result_text, re.DOTALL)
        if not json_match:
            error_msg = f"{data_type}响应中未找到JSON格式"
            logger.warning(error_msg)
            return False, None, error_msg

        json_text = json_match.group()
        logger.debug(f"{data_type}分析JSON原文: {json_text[:500]}...")

        # 2. 修复JSON
        json_text = fix_json(json_text)
        logger.debug(f"{data_type}修复后的JSON: {json_text[:300]}...")

        # 3. 解析JSON
        data = json.loads(json_text)
        logger.info(f"{data_type}分析成功，解析到 {len(data)} 条数据")
        return True, data, None

    except json.JSONDecodeError as e:
        error_msg = f"{data_type}JSON解析失败: {e}"
        logger.warning(error_msg)
        logger.debug(f"修复后的JSON: {json_text if 'json_text' in locals() else 'N/A'}")
        return False, None, error_msg
    except Exception as e:
        error_msg = f"{data_type}解析异常: {e}"
        logger.error(error_msg)
        return False, None, error_msg


def extract_topics_with_regex(result_text: str, max_topics: int) -> list[dict]:
    """
    使用正则表达式提取话题信息

    Args:
        result_text: 需要提取的文本
        max_topics: 最大话题数量

    Returns:
        话题数据列表
    """
    try:
        # 更强的正则表达式提取话题信息，处理转义字符
        # 匹配每个完整的话题对象
        topic_pattern = r'\{\s*"topic":\s*"([^"]+)"\s*,\s*"contributors":\s*\[([^\]]+)\]\s*,\s*"detail":\s*"([^"]*(?:\\.[^"]*)*)"\s*\}'
        matches = re.findall(topic_pattern, result_text, re.DOTALL)

        if not matches:
            # 尝试更宽松的匹配
            topic_pattern = r'"topic":\s*"([^"]+)"[^}]*"contributors":\s*\[([^\]]+)\][^}]*"detail":\s*"([^"]*(?:\\.[^"]*)*)"'
            matches = re.findall(topic_pattern, result_text, re.DOTALL)

        topics = []
        for match in matches[:max_topics]:
            topic_name = match[0].strip()
            contributors_str = match[1].strip()
            detail = match[2].strip()

            # 清理detail中的转义字符
            detail = detail.replace('\\"', '"').replace("\\n", " ").replace("\\t", " ")

            # 解析参与者列表
            contributors = [
                contrib.strip()
                for contrib in re.findall(r'"([^"]+)"', contributors_str)
            ] or ["群友"]

            topics.append(
                {
                    "topic": topic_name,
                    "contributors": contributors[:5],  # 最多5个参与者
                    "detail": detail,
                }
            )

        logger.info(f"话题正则表达式提取成功，提取到 {len(topics)} 条有效话题内容")
        return topics

    except Exception as e:
        logger.error(f"话题正则表达式提取失败: {e}")
        return []


def extract_user_titles_with_regex(result_text: str, max_count: int) -> list[dict]:
    """
    使用正则表达式提取用户称号信息

    Args:
        result_text: 需要提取的文本
        max_count: 最大提取数量

    Returns:
        用户称号数据列表
    """
    try:
        titles = []

        # 正则模式：匹配完整的用户称号对象
        pattern = r'\{\s*"name":\s*"([^"]+)"\s*,\s*"qq":\s*(\d+)\s*,\s*"title":\s*"([^"]+)"\s*,\s*"mbti":\s*"([^"]+)"\s*,\s*"reason":\s*"([^"]*(?:\\.[^"]*)*)"\s*\}'
        matches = re.findall(pattern, result_text, re.DOTALL)

        if not matches:
            # 尝试更宽松的匹配（字段顺序可变）
            pattern = r'"name":\s*"([^"]+)"[^}]*"qq":\s*(\d+)[^}]*"title":\s*"([^"]+)"[^}]*"mbti":\s*"([^"]+)"[^}]*"reason":\s*"([^"]*(?:\\.[^"]*)*)"'
            matches = re.findall(pattern, result_text, re.DOTALL)

        for match in matches[:max_count]:
            name = match[0].strip()
            qq = int(match[1])
            title = match[2].strip()
            mbti = match[3].strip()
            reason = match[4].strip()

            # 清理转义字符
            reason = reason.replace('\\"', '"').replace("\\n", " ").replace("\\t", " ")

            titles.append(
                {"name": name, "qq": qq, "title": title, "mbti": mbti, "reason": reason}
            )

        logger.info(f"用户称号正则表达式提取成功，提取到 {len(titles)} 条有效用户称号")
        return titles

    except Exception as e:
        logger.error(f"用户称号正则表达式提取失败: {e}")
        return []


def extract_golden_quotes_with_regex(result_text: str, max_count: int) -> list[dict]:
    """
    使用正则表达式提取金句信息

    Args:
        result_text: 需要提取的文本
        max_count: 最大提取数量

    Returns:
        金句数据列表
    """
    try:
        quotes = []

        # 正则模式：匹配完整的金句对象
        pattern = r'\{\s*"content":\s*"([^"]*(?:\\.[^"]*)*)"\s*,\s*"sender":\s*"([^"]+)"\s*,\s*"reason":\s*"([^"]*(?:\\.[^"]*)*)"\s*\}'
        matches = re.findall(pattern, result_text, re.DOTALL)

        if not matches:
            # 尝试更宽松的匹配（字段顺序可变）
            pattern = r'"content":\s*"([^"]*(?:\\.[^"]*)*)"[^}]*"sender":\s*"([^"]+)"[^}]*"reason":\s*"([^"]*(?:\\.[^"]*)*)"'
            matches = re.findall(pattern, result_text, re.DOTALL)

        for match in matches[:max_count]:
            content = match[0].strip()
            sender = match[1].strip()
            reason = match[2].strip()

            # 清理转义字符
            content = (
                content.replace('\\"', '"').replace("\\n", " ").replace("\\t", " ")
            )
            reason = reason.replace('\\"', '"').replace("\\n", " ").replace("\\t", " ")

            quotes.append({"content": content, "sender": sender, "reason": reason})

        logger.info(f"金句正则表达式提取成功，提取到 {len(quotes)} 条有效金句")
        return quotes

    except Exception as e:
        logger.error(f"金句正则表达式提取失败: {e}")
        return []
