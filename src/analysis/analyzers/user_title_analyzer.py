"""
用户称号分析模块
专门处理用户称号和MBTI类型分析
"""

from typing import List, Dict, Tuple
from astrbot.api import logger
from ...models.data_models import UserTitle, TokenUsage
from .base_analyzer import BaseAnalyzer
from ..utils.json_utils import extract_user_titles_with_regex


class UserTitleAnalyzer(BaseAnalyzer):
    """
    用户称号分析器
    专门处理用户称号分配和MBTI类型分析
    """
    
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
    
    def build_prompt(self, user_data: Dict) -> str:
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
        users_text = "\n".join([
            f"- {user['name']} (QQ:{user['qq']}): "
            f"发言{user['message_count']}条, 平均{user['avg_chars']}字, "
            f"表情比例{user['emoji_ratio']}, 夜间发言比例{user['night_ratio']}, "
            f"回复比例{user['reply_ratio']}"
            for user in user_summaries
        ])
        
        # 从配置读取 prompt 模板（默认使用 "default" 风格）
        prompt_template = self.config_manager.get_user_title_analysis_prompt()
        
        if prompt_template:
            # 使用配置中的 prompt 并替换变量
            try:
                prompt = prompt_template.format(
                    users_text=users_text
                )
                logger.info("使用配置中的用户称号分析提示词")
                return prompt
            except KeyError as e:
                logger.warning(f"用户称号分析提示词变量格式错误: {e}")
            except Exception as e:
                logger.warning(f"应用用户称号分析提示词失败: {e}")
        
        logger.warning("未找到有效的用户称号分析提示词配置，请检查配置文件")
        return ""
    
    def extract_with_regex(self, result_text: str, max_count: int) -> List[Dict]:
        """
        使用正则表达式提取用户称号信息
        
        Args:
            result_text: LLM响应文本
            max_count: 最大提取数量
            
        Returns:
            用户称号数据列表
        """
        return extract_user_titles_with_regex(result_text, max_count)
    
    def create_data_objects(self, titles_data: List[Dict]) -> List[UserTitle]:
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
                qq = title_data.get("qq")
                title = title_data.get("title", "").strip()
                mbti = title_data.get("mbti", "").strip()
                reason = title_data.get("reason", "").strip()
                
                # 验证必要字段
                if not name or not title or not mbti or not reason:
                    logger.warning(f"用户称号数据格式不完整，跳过: {title_data}")
                    continue
                
                # 验证QQ号格式
                try:
                    qq = int(qq)
                except (ValueError, TypeError):
                    logger.warning(f"QQ号格式无效，跳过: {qq}")
                    continue
                
                titles.append(UserTitle(
                    name=name,
                    qq=qq,
                    title=title,
                    mbti=mbti,
                    reason=reason
                ))
            
            return titles
            
        except Exception as e:
            logger.error(f"创建用户称号对象失败: {e}")
            return []
    
    def prepare_user_data(self, messages: List[Dict], user_analysis: Dict) -> Dict:
        """
        准备用户数据
        
        Args:
            messages: 群聊消息列表
            user_analysis: 用户分析统计
            
        Returns:
            准备好的用户数据字典
        """
        try:
            user_summaries = []
            
            for user_id, stats in user_analysis.items():
                if stats["message_count"] < 5:  # 过滤活跃度太低的用户
                    continue
                
                # 分析用户特征
                night_messages = sum(stats["hours"][h] for h in range(6))
                day_messages = stats["message_count"] - night_messages
                avg_chars = stats["char_count"] / stats["message_count"] if stats["message_count"] > 0 else 0
                
                user_summaries.append({
                    "name": stats["nickname"],
                    "qq": int(user_id),
                    "message_count": stats["message_count"],
                    "avg_chars": round(avg_chars, 1),
                    "emoji_ratio": round(stats["emoji_count"] / stats["message_count"], 2),
                    "night_ratio": round(night_messages / stats["message_count"], 2),
                    "reply_ratio": round(stats["reply_count"] / stats["message_count"], 2)
                })
            
            if not user_summaries:
                return {"user_summaries": []}
            
            # 按消息数量排序，取前N名
            max_user_titles = self.get_max_count()
            user_summaries.sort(key=lambda x: x["message_count"], reverse=True)
            user_summaries = user_summaries[:max_user_titles]
            
            return {"user_summaries": user_summaries}
            
        except Exception as e:
            logger.error(f"准备用户数据失败: {e}")
            return {"user_summaries": []}
    
    async def analyze_user_titles(self, messages: List[Dict], user_analysis: Dict, umo: str = None) -> Tuple[List[UserTitle], TokenUsage]:
        """
        分析用户称号
        
        Args:
            messages: 群聊消息列表
            user_analysis: 用户分析统计
            umo: 模型唯一标识符
            
        Returns:
            (用户称号列表, Token使用统计)
        """
        try:
            # 准备用户数据
            user_data = self.prepare_user_data(messages, user_analysis)
            
            if not user_data["user_summaries"]:
                logger.info("没有符合条件的用户，返回空结果")
                return [], TokenUsage()
            
            logger.info(f"开始分析 {len(user_data['user_summaries'])} 个用户的称号")
            return await self.analyze(user_data, umo)
            
        except Exception as e:
            logger.error(f"用户称号分析失败: {e}")
            return [], TokenUsage()