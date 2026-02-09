"""
用户称号分析模块
专门处理用户称号和MBTI类型分析
"""

from ....domain.models.data_models import TokenUsage, UserTitle
from ....utils.logger import logger
from ..utils.json_utils import extract_user_titles_with_regex
from .base_analyzer import BaseAnalyzer


class UserTitleAnalyzer(BaseAnalyzer):
    """
    用户称号分析器
    专门处理用户称号分配和MBTI类型分析
    """

    def get_provider_id_key(self) -> str:
        """获取 Provider ID 配置键名"""
        return "user_title_provider_id"

    def get_data_type(self) -> str:
        """获取数据类型标识"""
        return "用户称号"

    def get_max_count(self) -> int:
        """获取最大用户称号数量"""
        return self.config_manager.get_max_user_titles()

    def get_max_tokens(self) -> int:
        """获取最大token数"""
        return self.config_manager.get_user_title_max_tokens()

    def get_temperature(self) -> float:
        """获取温度参数"""
        return 0.5

    def build_prompt(self, user_data: dict) -> str:
        """
        构建用户称号分析提示词

        Args:
            user_data: 用户数据字典，包含用户统计信息

        Returns:
            提示词字符串
        """
        user_summaries = user_data.get("user_summaries", [])

        if not user_summaries:
            return ""

        # 构建用户数据文本
        users_text = "\n".join(
            [
                f"- {user['name']} (ID:{user['user_id']}): "
                f"发言{user['message_count']}条, 平均{user['avg_chars']}字, "
                f"表情比例{user['emoji_ratio']}, 夜间发言比例{user['night_ratio']}, "
                f"回复比例{user['reply_ratio']}"
                for user in user_summaries
            ]
        )

        # 从配置读取 prompt 模板（默认使用 "default" 风格）
        prompt_template = self.config_manager.get_user_title_analysis_prompt()

        if prompt_template:
            # 使用配置中的 prompt 并替换变量
            try:
                prompt = prompt_template.format(users_text=users_text)
                logger.info("使用配置中的用户称号分析提示词")
                return prompt
            except KeyError as e:
                logger.warning(f"用户称号分析提示词变量格式错误: {e}")
            except Exception as e:
                logger.warning(f"应用用户称号分析提示词失败: {e}")

        logger.warning("未找到有效的用户称号分析提示词配置，请检查配置文件")
        return ""

    def extract_with_regex(self, result_text: str, max_count: int) -> list[dict]:
        """
        使用正则表达式提取用户称号信息

        Args:
            result_text: LLM响应文本
            max_count: 最大提取数量

        Returns:
            用户称号数据列表
        """
        return extract_user_titles_with_regex(result_text, max_count)

    def create_data_objects(self, titles_data: list[dict]) -> list[UserTitle]:
        """
        创建用户称号对象列表

        Args:
            titles_data: 原始用户称号数据列表

        Returns:
            UserTitle对象列表
        """
        try:
            titles = []
            max_titles = self.get_max_count()

            for title_data in titles_data[:max_titles]:
                # 确保数据格式正确
                name = title_data.get("name", "").strip()
                user_id = title_data.get("user_id")
                title = title_data.get("title", "").strip()
                mbti = title_data.get("mbti", "").strip()
                reason = title_data.get("reason", "").strip()

                # 验证必要字段
                if not name or not title or not mbti or not reason:
                    logger.warning(f"用户称号数据格式不完整，跳过: {title_data}")
                    continue

                # 确保 user_id 是字符串
                if user_id is not None:
                    user_id = str(user_id)
                else:
                    logger.warning(f"未找到用户ID (user_id)，跳过: {title_data}")
                    continue

                titles.append(
                    UserTitle(
                        name=name,
                        user_id=user_id,
                        title=title,
                        mbti=mbti,
                        reason=reason,
                    )
                )

            return titles

        except Exception as e:
            logger.error(f"创建用户称号对象失败: {e}")
            return []

    def prepare_user_data(
        self, messages: list[dict], user_analysis: dict, top_users: list[dict] = None
    ) -> dict:
        """
        准备用户数据

        Args:
            messages: 群聊消息列表
            user_analysis: 用户分析统计
            top_users: 活跃用户列表(从get_top_users获取)

        Returns:
            准备好的用户数据字典
        """
        try:
            # 获取机器人 ID 列表用于过滤
            bot_self_ids = self.config_manager.get_bot_self_ids()

            user_summaries = []

            # 如果提供了top_users列表,只分析这些活跃用户
            if top_users:
                logger.info(
                    f"使用get_top_users筛选出的 {len(top_users)} 个活跃用户进行称号分析"
                )
                target_user_ids = {str(user["user_id"]) for user in top_users}
            else:
                # 兼容旧逻辑:如果没有提供top_users,则使用所有消息数>=5的用户
                logger.info("未提供活跃用户列表,使用消息数>=5的用户")
                target_user_ids = {
                    user_id
                    for user_id, stats in user_analysis.items()
                    if stats["message_count"] >= 5
                }

            for user_id, stats in user_analysis.items():
                user_id_str = str(user_id)
                # 过滤机器人自己的消息
                if bot_self_ids and user_id_str in [str(uid) for uid in bot_self_ids]:
                    logger.debug(f"过滤掉机器人ID: {user_id}")
                    continue

                # 只处理活跃用户
                if user_id_str not in target_user_ids:
                    continue

                # 分析用户特征
                night_messages = sum(stats["hours"][h] for h in range(6))
                avg_chars = (
                    stats["char_count"] / stats["message_count"]
                    if stats["message_count"] > 0
                    else 0
                )

                user_summaries.append(
                    {
                        "name": stats["nickname"],
                        "user_id": user_id_str,  # 使用 user_id
                        "message_count": stats["message_count"],
                        "avg_chars": round(avg_chars, 1),
                        "emoji_ratio": round(
                            stats["emoji_count"] / stats["message_count"], 2
                        )
                        if stats["message_count"] > 0
                        else 0,
                        "night_ratio": round(night_messages / stats["message_count"], 2)
                        if stats["message_count"] > 0
                        else 0,
                        "reply_ratio": round(
                            stats["reply_count"] / stats["message_count"], 2
                        )
                        if stats["message_count"] > 0
                        else 0,
                    }
                )

            if not user_summaries:
                return {"user_summaries": []}

            # 按消息数量排序
            user_summaries.sort(key=lambda x: x["message_count"], reverse=True)

            return {"user_summaries": user_summaries}

        except Exception as e:
            logger.error(f"准备用户数据失败: {e}")
            return {"user_summaries": []}

    async def analyze_user_titles(
        self,
        messages: list[dict],
        user_analysis: dict,
        umo: str = None,
        top_users: list[dict] = None,
        session_id: str = None,
    ) -> tuple[list[UserTitle], TokenUsage]:
        """
        分析用户称号

        Args:
            messages: 群聊消息列表
            user_analysis: 用户分析统计
            umo: 模型唯一标识符
            top_users: 活跃用户列表(从get_top_users获取,可选)
            session_id: 会话ID (用于调试模式)

        Returns:
            (用户称号列表, Token使用统计)
        """
        try:
            # 准备用户数据,传入活跃用户列表
            user_data = self.prepare_user_data(messages, user_analysis, top_users)

            if not user_data["user_summaries"]:
                logger.info("没有符合条件的用户，返回空结果")
                return [], TokenUsage()

            logger.info(f"开始分析 {len(user_data['user_summaries'])} 个活跃用户的称号")
            return await self.analyze(user_data, umo, session_id)

        except Exception as e:
            logger.error(f"用户称号分析失败: {e}")
            return [], TokenUsage()
