"""
话题分析模块
专门处理群聊话题分析
"""

from typing import List, Dict, Tuple
from datetime import datetime
import re
from astrbot.api import logger
from ...models.data_models import SummaryTopic, TokenUsage
from .base_analyzer import BaseAnalyzer
from ..utils.json_utils import extract_topics_with_regex


class TopicAnalyzer(BaseAnalyzer):
    """
    话题分析器
    专门处理群聊话题的提取和分析
    """
    
    def get_data_type(self) -> str:
        """获取数据类型标识"""
        return "话题"
    
    def get_max_count(self) -> int:
        """获取最大话题数量"""
        return self.config_manager.get_max_topics()
    
    def get_max_tokens(self) -> int:
        """获取最大token数"""
        return 10000
    
    def get_temperature(self) -> float:
        """获取温度参数"""
        return 0.6
    
    def build_prompt(self, messages: List[Dict]) -> str:
        """
        构建话题分析提示词
        
        Args:
            messages: 群聊消息列表
            
        Returns:
            提示词字符串
        """
        # 提取文本消息
        text_messages = []
        for msg in messages:
            sender = msg.get("sender", {})
            nickname = sender.get("nickname", "") or sender.get("card", "")
            msg_time = datetime.fromtimestamp(msg.get("time", 0)).strftime("%H:%M")
            
            for content in msg.get("message", []):
                if content.get("type") == "text":
                    text = content.get("data", {}).get("text", "").strip()
                    if text and len(text) > 2 and not text.startswith("/"):
                        # 清理消息内容
                        text = text.replace('“', '"').replace('”', '"')
                        text = text.replace('‘', "'").replace('’', "'")
                        text = text.replace('\n', ' ').replace('\r', ' ')
                        text = text.replace('\t', ' ')
                        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
                        text_messages.append({
                            "sender": nickname,
                            "time": msg_time,
                            "content": text.strip()
                        })
        
        if not text_messages:
            return ""
        
        # 构建消息文本
        messages_text = "\n".join([
            f"[{msg['time']}] {msg['sender']}: {msg['content']}"
            for msg in text_messages
        ])
        
        max_topics = self.get_max_count()
        prompt = f"""
你是一个帮我进行群聊信息总结的助手，生成总结内容时，你需要严格遵守下面的几个准则：
请分析接下来提供的群聊记录，提取出最多{max_topics}个主要话题。

对于每个话题，请提供：
1. 话题名称（突出主题内容，尽量简明扼要）
2. 主要参与者（最多5人）
3. 话题详细描述（包含关键信息和结论）

注意：
- 对于比较有价值的点，稍微用一两句话详细讲讲，比如不要生成 "Nolan 和 SOV 讨论了 galgame 中关于性符号的衍生情况" 这种宽泛的内容，而是生成更加具体的讨论内容，让其他人只看这个消息就能知道讨论中有价值的，有营养的信息。
- 对于其中的部分信息，你需要特意提到主题施加的主体是谁，是哪个群友做了什么事情，而不要直接生成和群友没有关系的语句。
- 对于每一条总结，尽量讲清楚前因后果，以及话题的结论，是什么，为什么，怎么做，如果用户没有讲到细节，则可以不用这么做。

群聊记录：
{messages_text}

重要：必须返回标准JSON格式，严格遵守以下规则：
1. 只使用英文双引号 " 不要使用中文引号 " "
2. 字符串内容中的引号必须转义为 \"
3. 多个对象之间用逗号分隔
4. 数组元素之间用逗号分隔
5. 不要在JSON外添加任何文字说明
6. 描述内容避免使用特殊符号，用普通文字表达

请严格按照以下JSON格式返回，确保可以被标准JSON解析器解析：
[
  {{
    "topic": "话题名称",
    "contributors": ["用户1", "用户2"],
    "detail": "话题描述内容"
  }},
  {{
    "topic": "另一个话题",
    "contributors": ["用户3", "用户4"],
    "detail": "另一个话题的描述"
  }}
]

注意：返回的内容必须是纯JSON，不要包含markdown代码块标记或其他格式
"""
        return prompt
    
    def extract_with_regex(self, result_text: str, max_topics: int) -> List[Dict]:
        """
        使用正则表达式提取话题信息
        
        Args:
            result_text: LLM响应文本
            max_topics: 最大话题数量
            
        Returns:
            话题数据列表
        """
        return extract_topics_with_regex(result_text, max_topics)
    
    def create_data_objects(self, topics_data: List[Dict]) -> List[SummaryTopic]:
        """
        创建话题对象列表
        
        Args:
            topics_data: 原始话题数据列表
            
        Returns:
            SummaryTopic对象列表
        """
        try:
            topics = []
            max_topics = self.get_max_count()
            
            for topic_data in topics_data[:max_topics]:
                # 确保数据格式正确
                topic_name = topic_data.get("topic", "").strip()
                contributors = topic_data.get("contributors", [])
                detail = topic_data.get("detail", "").strip()
                
                # 验证必要字段
                if not topic_name or not detail:
                    logger.warning(f"话题数据格式不完整，跳过: {topic_data}")
                    continue
                
                # 确保参与者列表有效
                if not contributors or not isinstance(contributors, list):
                    contributors = ["群友"]
                else:
                    # 清理参与者名称
                    contributors = [str(c).strip() for c in contributors if c and str(c).strip()] or ["群友"]
                
                topics.append(SummaryTopic(
                    topic=topic_name,
                    contributors=contributors[:5],  # 最多5个参与者
                    detail=detail
                ))
            
            return topics
            
        except Exception as e:
            logger.error(f"创建话题对象失败: {e}")
            return []
    
    async def analyze_topics(self, messages: List[Dict], umo: str = None) -> Tuple[List[SummaryTopic], TokenUsage]:
        """
        分析群聊话题
        
        Args:
            messages: 群聊消息列表
            umo: 模型唯一标识符
            
        Returns:
            (话题列表, Token使用统计)
        """
        try:
            # 提取文本消息
            text_messages = self.extract_text_messages(messages)
            
            if not text_messages:
                logger.info("没有有效的文本消息，返回空结果")
                return [], TokenUsage()
            
            logger.info(f"开始分析 {len(text_messages)} 条文本消息中的话题")
            return await self.analyze(text_messages, umo)
            
        except Exception as e:
            logger.error(f"话题分析失败: {e}")
            return [], TokenUsage()