import re

from ....domain.models.data_models import TokenUsage
from ....utils.logger import logger
from ..utils.structured_output_schema import JSONObject
from .base_analyzer import BaseAnalyzer

DEFAULT_COMIC_STORYBOARD_PROMPT = (
    "你是一个资深的漫画分镜师与 AI 绘画提示词专家。\n"
    "请根据以下给出的【群聊每日核心话题列表】，站在你【当前的人格角色设定】（详见系统注入的身份）的视角与语气，将其改编并设计为一个精彩的多格连环漫画（Comic Strip）全景视觉画图提示词 (Prompt)。\n\n"
    "【核心视觉、台词与双层排版规则】：\n"
    "1. 【全话题必须覆盖（共 ${topic_count} 个分格）】：给出的待创作核心话题列表中共有 ${topic_count} 个话题，你必须为每一个话题分别设计一个分格 Panel（即 Panel 1 到 Panel ${topic_count}），绝对不许随意裁减、挑选或遗漏任何一个话题！\n"
    "2. 【人设口语化台词改编】：绝对严禁将报告分析总结原文直接放进对话框！必须以【你当前的人格语气/性格/口吻】（例如傲娇、萌系或专属说话风格），将每个话题的事件提炼改编为一句角色在漫画中的生动台词或吐槽，【每条台词控制在 15 个汉字以内】（例如：“呜呜！家里云又断网了啦！”、“萝卜子才没有降智！那都是Gemini的错！”）。\n"
    "3. 【精美双层文字排版（气泡 + 可爱旁白字幕条）】：\n"
    "   - 【角色的气泡】：在描述英文 Prompt 时，指定样式为“adorable kawaii anime speech bubble, soft rounded cloud-like shape, cute pointer tail pointing to the speaker”。\n"
    "   - 【分格底部的事件旁白条】：将每个话题概括为生动精炼的短标题（控制在 30 字以内，严禁带有“【事件】”字样），在 Prompt 中指定样式为“cute pastel-colored kawaii caption strip at the bottom of the panel with soft rounded corners”，严禁死板白框！\n"
    '4. 【中文文本显式渲染】：画面整体构图与场景描述使用英文，但气泡与底部旁白条内渲染的中文必须显式指定（指令格式：containing a speech bubble with exact Chinese text "人设吐槽台词" 以及 and a cute caption strip at bottom with exact Chinese text "精炼话题短标题"），绝对禁止将中文翻译成英文！\n'
    "5. 【话题内容直传与文字渲染约束】：在生成传给生图 LLM 的英文提示词 (scene) 时，对于每一个分格，除了描述具体的视觉画面外，你必须将该话题的【完整详情（翻译为英文）】作为 Background Context 附加在该分格的提示词中，帮助生图模型理解剧情。但同时，必须极其强烈地警告生图模型：“绝对禁止将长篇上下文写在画面上，仅允许渲染短标题字幕条和气泡台词！”（示例：Background Context: [Details]. STRICT RULE: DO NOT render the background context text! ONLY render the exact Chinese text in the bubble and caption strip!）。\n"
    "6. 【核心角色强制全覆盖】：在提示词中必须明确要求并描述，每一个分格 (Panel) 都必须无一例外地出现你当前的人格设定（即参考图中的核心角色，例如 1girl, [特定外貌特征] 等），保持整篇连环画的主角绝对连贯！\n\n"
    "【待创作的群聊核心话题列表】：\n${chat_content}\n\n"
    "【输出格式与正反例规范 (GOOD & BAD EXAMPLES)】：\n"
    '⚠️ 核心要求：AI 绘图引擎会直接读取 "scene" 字段作为唯一生图指令。你必须将全局角色总设以及 Panel 1 到 Panel ${topic_count} 的每一格完整描述全部写入 "scene" 字符串中！\n\n'
    "✅ 正确示范 (GOOD EXAMPLE - 必须严格遵循此格式输出纯 JSON)：\n"
    "{\n"
    '  "scene": "A ${topic_count}-panel comic strip featuring [protagonist description] observing a chaotic QQ group chat.\\n\\nPanel 1: [Visual action] containing a speech bubble with exact Chinese text \\"[人设吐槽台词 15字内]\\" and a cute pastel caption strip at bottom with exact Chinese text \\"[精炼短标题]\\". Background Context: [English Details]. STRICT RULE: DO NOT render the background context text!\\n\\nPanel 2: [Visual action] containing a speech bubble with exact Chinese text \\"[人设吐槽台词 15字内]\\" and a cute pastel caption strip at bottom with exact Chinese text \\"[精炼短标题]\\". Background Context: [English Details]. STRICT RULE: DO NOT render the background context text!\\n\\n... (必须依次写完 Panel 1 到 Panel ${topic_count})"\n'
    "}\n\n"
    "❌ 错误示范 (BAD EXAMPLE - 严禁以下行为)：\n"
    "1. 严禁把 scene 写成一句简短概括，却把具体话题藏在 panels 列表中（生图模型直接读取 scene，必须全内联写入 scene）！\n"
    "2. 严禁丢失气泡或字幕条里的 exact Chinese text 显式中文台词与短标题！\n"
    "3. 严禁在 JSON 之外输出任何多余的 Markdown 或闲聊文字！\n"
)


class ComicStoryboardAnalyzer(BaseAnalyzer[dict, list[dict]]):
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

    def build_prompt(self, data: list[dict], prompt_template: str | None = None) -> str:
        prompt_template = (
            prompt_template
            or self.config_manager.get_comic_storyboard_prompt()
            or DEFAULT_COMIC_STORYBOARD_PROMPT
        )

        valid_topics = [m for m in data if m.get("topic", "")]
        topic_count = len(valid_topics) if valid_topics else self.get_max_count()
        chat_content = "\n".join(
            [
                f"{i + 1}. 话题: {m.get('topic', '')}\n   详情: {m.get('detail', '')}"
                for i, m in enumerate(valid_topics)
            ]
        )

        try:
            from string import Template

            if "${" in prompt_template or "$" in prompt_template:
                return Template(prompt_template).safe_substitute(
                    chat_content=chat_content,
                    topic_count=topic_count,
                    max_count=topic_count,
                )
            else:
                return prompt_template.format(
                    chat_content=chat_content,
                    topic_count=topic_count,
                    max_count=topic_count,
                )
        except Exception as e:
            logger.warning(f"漫画分镜提示词格式化失败，使用默认格式: {e}")
            return f"请从以下群聊话题中提取并生成包含 scene 的 JSON：\n{chat_content}"

    def build_prompt_with_override(
        self, data: list[dict], prompt_override: str | None
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
        topics: list[dict],
        umo: str | None = None,
        session_id: str | None = None,
        persona_id: str | None = None,
        prompt_template: str | None = None,
    ) -> tuple[list[dict], TokenUsage]:
        """执行分析，返回 storyboards 和 token 消耗。

        Args:
            topics: 已提取的有效群聊话题。
            umo: 群聊统一消息来源标识。
            session_id: 调试会话标识。
            persona_id: 漫画分镜专用人格 ID。
            prompt_template: 角色专属的漫画分镜提示词模板。

        Returns:
            分镜列表和 Token 使用统计。
        """
        storyboards, usage = await self.analyze(
            topics, umo, session_id, persona_id, prompt_template
        )

        if isinstance(storyboards, list):
            return [item for item in storyboards if isinstance(item, dict)], usage
        return [], usage
