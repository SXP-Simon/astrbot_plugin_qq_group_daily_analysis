from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ....shared.comic_prompts import DEFAULT_COMIC_STORYBOARD_PROMPT
from ....utils.logger import logger
from .base_analyzer import BaseAnalyzer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ....domain.value_objects import SummaryTopic, TokenUsage
    from ..utils.structured_output_schema import JSONObject


class ComicStoryboardAnalyzer(
    BaseAnalyzer[dict, "Sequence[SummaryTopic] | Sequence[dict[str, object]]"]
):
    """
    分镜及绘画提示词分析器
    直接从聊天记录中提取金句并生成绘画提示词（含文字渲染要求）
    """

    def get_provider_id_key(self) -> str:
        """获取画图提示词专用 Provider ID 配置键名"""
        return "drawing_prompt_provider_id"

    def get_data_type(self) -> str:
        return "comic_storyboards"

    def get_max_count(self) -> int:
        return self.config_manager.get_max_topics()

    def build_prompt(
        self,
        data: Sequence[SummaryTopic] | Sequence[dict[str, object]],
        prompt_template: str | None = None,
    ) -> str:
        template_str = (
            prompt_template
            or self.config_manager.get_comic_storyboard_prompt()
            or DEFAULT_COMIC_STORYBOARD_PROMPT
        )

        valid_topics: list[tuple[str, str]] = []
        for item in data:
            if isinstance(item, dict):
                t = str(item.get("topic", "")).strip()
                d = str(item.get("detail", "")).strip()
            else:
                t = str(getattr(item, "topic", "")).strip()
                d = str(getattr(item, "detail", "")).strip()
            if t:
                valid_topics.append((t, d))

        topic_count = len(valid_topics) if valid_topics else self.get_max_count()
        chat_content = "\n".join(
            [
                f"{i + 1}. 话题: {t}\n   详情: {d}"
                for i, (t, d) in enumerate(valid_topics)
            ]
        )

        try:
            from string import Template

            if "${" in template_str or "$" in template_str:
                return Template(template_str).safe_substitute(
                    chat_content=chat_content,
                    topic_count=topic_count,
                    max_count=topic_count,
                )
            return template_str.format(
                chat_content=chat_content,
                topic_count=topic_count,
                max_count=topic_count,
            )
        except Exception as e:
            logger.warning(f"漫画分镜提示词格式化失败，使用默认格式: {e}")
            return f"请从以下群聊话题中提取并生成包含 scene 的 JSON：\n{chat_content}"

    def build_prompt_with_override(
        self,
        data: Sequence[SummaryTopic] | Sequence[dict[str, object]],
        prompt_override: str | None,
    ) -> str:
        """使用角色专属模板构建漫画分镜提示词。"""
        return self.build_prompt(data, prompt_override)

    @classmethod
    def _extract_text_chunks(cls, obj: object, depth: int = 0) -> list[str]:
        """递归提取任意多层级 JSON 结构中的所有文本叶子节点，零硬编码字段名。"""
        if depth > 8 or obj is None:
            return []

        if isinstance(obj, str):
            text = obj.strip()
            return [text] if text else []

        chunks: list[str] = []
        if isinstance(obj, list):
            for item in obj:
                chunks.extend(cls._extract_text_chunks(item, depth + 1))
        elif isinstance(obj, dict):
            for val in obj.values():
                chunks.extend(cls._extract_text_chunks(val, depth + 1))

        return chunks

    @classmethod
    def _consolidate_scene_text(cls, data: object) -> str | None:
        """将任意多层级 JSON 结构模糊解析并整理为统一的单段 scene 提示词。"""
        if not data:
            return None

        raw_chunks = cls._extract_text_chunks(data)
        if not raw_chunks:
            return None

        # 智能去重与包含消除（避免子串重复出现）
        unique_chunks: list[str] = []
        for chunk in raw_chunks:
            if len(chunk) < 3:
                continue
            if any(
                chunk == existing or (len(chunk) < len(existing) and chunk in existing)
                for existing in unique_chunks
            ):
                continue
            superseded = [
                existing
                for existing in unique_chunks
                if existing != chunk and existing in chunk
            ]
            if superseded:
                for s in superseded:
                    unique_chunks.remove(s)
            unique_chunks.append(chunk)

        return "\n\n".join(unique_chunks) if unique_chunks else None

    def extract_with_regex(self, result_text: str, max_count: int) -> list[dict]:
        del max_count
        scene_match = re.search(r'"scene"\s*:\s*"((?:[^"\\]|\\.)*)"', result_text)
        if scene_match:
            return [{"scene": scene_match.group(1).replace('\\"', '"')}]
        return []

    def parse_structured_response(
        self, result_text: str
    ) -> tuple[bool, list[dict] | None, str | None]:
        from ..utils.json_utils import (
            parse_json_object_response,
            parse_json_response,
        )

        # 1. 尝试解析为 JSON 对象
        success, data, error = parse_json_object_response(
            result_text, self.get_data_type()
        )
        if success and isinstance(data, dict):
            # 主线：优先提取官方约定的 scene 字段
            scene_val = data.get("scene")
            scene_str = scene_val.strip() if isinstance(scene_val, str) else ""

            # 兼容性检查：提取字典中除 scene 以外其他字段的内容（防止模型把具体分格拆在其他字段中）
            other_data = {k: v for k, v in data.items() if k != "scene"}
            other_text = (
                self._consolidate_scene_text(other_data) if other_data else None
            )

            # 情况 A：仅有 scene，直接使用
            if scene_str and not other_text:
                return True, [{"scene": scene_str}], None

            # 情况 B：同时存在 scene 与其他字段内容
            if scene_str and other_text:
                # 若其他字段内容已被包含在 scene 中（如已全内联），直接使用 scene
                if other_text in scene_str or (
                    "panel 1" in scene_str.lower() and "panel 2" in scene_str.lower()
                ):
                    return True, [{"scene": scene_str}], None
                # 若未包含，将 scene 总设与其他字段细节健壮合并
                return True, [{"scene": f"{scene_str}\n\n{other_text}"}], None

            # 情况 C：缺失 scene 字段，使用其他字段提取整合的内容兜底
            if other_text:
                return True, [{"scene": other_text}], None

            return False, None, "无法在 JSON 对象中找到有效的 'scene' 字段或分镜描述"

        # 2. 容错兼容：若模型直接输出为顶层 JSON 数组
        list_success, list_data, _ = parse_json_response(
            result_text, self.get_data_type()
        )
        if list_success and list_data:
            consolidated = self._consolidate_scene_text(list_data)
            if consolidated:
                return True, [{"scene": consolidated}], None

        return False, None, error or "无法从 JSON 响应中提取有效的漫画分镜描述"

    def create_data_objects(self, data_list: list[dict]) -> list[dict]:
        # 我们直接返回 dict，因为不需要特别的类型验证
        return data_list

    def get_response_schema(self) -> JSONObject:
        return {
            "type": "object",
            "properties": {
                "scene": {
                    "type": "string",
                    "description": "One complete panoramic comic image-generation prompt covering every topic and panel",
                }
            },
            "required": ["scene"],
            "additionalProperties": True,
        }

    async def analyze_storyboards(
        self,
        topics: Sequence[SummaryTopic] | Sequence[dict[str, object]],
        umo: str | None = None,
        persona_id: str | None = None,
        prompt_template: str | None = None,
    ) -> tuple[list[dict], TokenUsage]:
        """执行分析，返回 storyboards 和 token 消耗。

        Args:
            topics: 已提取的有效群聊话题。
            umo: 群聊统一消息来源标识。
            persona_id: 漫画分镜专用人格 ID。
            prompt_template: 角色专属的漫画分镜提示词模板。

        Returns:
            分镜列表和 Token 使用统计。
        """
        storyboards, usage = await self.analyze(
            topics,
            umo=umo,
            persona_id=persona_id,
            prompt_override=prompt_template,
        )

        return storyboards, usage
