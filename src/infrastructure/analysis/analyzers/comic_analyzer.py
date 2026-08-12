import re

from ....domain.models.data_models import TokenUsage
from ....utils.logger import logger
from ..utils.structured_output_schema import JSONObject
from .base_analyzer import BaseAnalyzer


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

    def build_prompt(self, data: list[dict]) -> str:
        prompt_template = self.config_manager.get_comic_storyboard_prompt()
        if not prompt_template:
            # 默认的 Prompt
            prompt_template = (
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
                '请输出包含 "scene" 字段的 JSON 对象。\n'
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

    def extract_with_regex(self, result_text: str, max_count: int) -> list[dict]:
        del max_count
        storyboards = []
        scene_match = re.search(r'"scene"\s*:\s*"((?:[^"\\]|\\.)*)"', result_text)
        if scene_match:
            storyboards.append({"scene": scene_match.group(1).replace('\\"', '"')})
        return storyboards

    def parse_structured_response(
        self, result_text: str
    ) -> tuple[bool, list[dict] | None, str | None]:
        from ..utils.json_utils import parse_json_object_response

        success, data, error = parse_json_object_response(
            result_text, self.get_data_type()
        )
        if success and isinstance(data, dict):
            if "storyboards" in data and isinstance(data["storyboards"], list):
                scenes = [
                    item["scene"].strip()
                    for item in data["storyboards"]
                    if isinstance(item, dict)
                    and isinstance(item.get("scene"), str)
                    and item["scene"].strip()
                ]
                if scenes:
                    return True, [{"scene": "\n\n".join(scenes)}], None
                return False, None, "'storyboards'中没有有效的非空'scene'字段"
            elif "scene" in data:
                scene = data["scene"]
                if isinstance(scene, str) and scene.strip():
                    return True, [{"scene": scene.strip()}], None
                return False, None, "'scene'字段必须是非空字符串"
            else:
                return False, None, "无法在JSON对象中找到'scene'或'storyboards'字段"
        return False, None, error

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
            "additionalProperties": False,
        }

    async def analyze_storyboards(
        self,
        topics: list[dict],
        umo: str | None = None,
        session_id: str | None = None,
        persona_id: str | None = None,
    ) -> tuple[list[dict], TokenUsage]:
        """执行分析，返回 storyboards 和 token 消耗。

        Args:
            topics: 已提取的有效群聊话题。
            umo: 群聊统一消息来源标识。
            session_id: 调试会话标识。
            persona_id: 漫画分镜专用人格 ID。

        Returns:
            分镜列表和 Token 使用统计。
        """
        storyboards, usage = await self.analyze(topics, umo, session_id, persona_id)

        if storyboards:
            if isinstance(storyboards, list):
                if len(storyboards) > 0 and isinstance(storyboards[0], dict):
                    if "storyboards" in storyboards[0]:
                        storyboards = storyboards[0]["storyboards"]
                    # else: storyboards[0] 已含 "scene"，直接使用

        if isinstance(storyboards, list):
            return [item for item in storyboards if isinstance(item, dict)], usage
        return [], usage
