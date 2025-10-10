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
        logger.debug(f"build_prompt 开始处理，输入消息数量: {len(messages) if messages else 0}")
        logger.debug(f"输入消息类型: {type(messages)}")
        
        # 验证输入数据格式
        if not isinstance(messages, list):
            logger.error(f"build_prompt 期望列表，但收到: {type(messages)}")
            return ""
        
        # 检查消息列表是否为空
        if not messages:
            logger.warning("build_prompt 收到空消息列表")
            return ""
        
        logger.debug(f"build_prompt 第一条消息内容: {messages[0] if messages else '无'}")
        
        # 提取文本消息
        text_messages = []
        for i, msg in enumerate(messages):
            logger.debug(f"build_prompt 处理第 {i+1} 条消息，类型: {type(msg)}")
            
            # 确保msg是字典类型，避免'str' object has no attribute 'get'错误
            if not isinstance(msg, dict):
                logger.warning(f"build_prompt 跳过非字典类型的消息: {type(msg)} - {msg}")
                continue
                
            try:
                sender = msg.get("sender", {})
                # 确保sender是字典类型，避免'str' object has no attribute 'get'错误
                if not isinstance(sender, dict):
                    logger.warning(f"build_prompt 跳过sender非字典类型的消息: {type(sender)} - {sender}")
                    continue
                    
                nickname = sender.get("nickname", "") or sender.get("card", "")
                msg_time = datetime.fromtimestamp(msg.get("time", 0)).strftime("%H:%M")
                
                message_list = msg.get("message", [])
                logger.debug(f"build_prompt 消息 {i+1} 的 message 字段类型: {type(message_list)}, 长度: {len(message_list) if hasattr(message_list, '__len__') else 'N/A'}")
                
                # 提取文本内容，可能分布在多个 content 中
                text_parts = []
                for j, content in enumerate(message_list):
                    logger.debug(f"build_prompt 处理消息 {i+1} 的内容 {j+1}, 类型: {type(content)}")
                    if not isinstance(content, dict):
                        logger.warning(f"build_prompt 跳过非字典类型的内容: {type(content)} - {content}")
                        continue
                    
                    content_type = content.get("type", "")
                    logger.debug(f"build_prompt 内容类型: {content_type}")
                    
                    if content_type == "text":
                        text = content.get("data", {}).get("text", "").strip()
                        logger.debug(f"build_prompt 提取到的文本: '{text}' (长度: {len(text)})")
                        if text:
                            text_parts.append(text)
                    elif content_type == "at":
                        # 处理 @ 消息，转换为文本
                        at_qq = content.get("data", {}).get("qq", "")
                        if at_qq:
                            at_text = f"@{at_qq}"
                            text_parts.append(at_text)
                            logger.debug(f"build_prompt 提取到@消息: {at_text}")
                    elif content_type == "reply":
                        # 处理回复消息，添加标记
                        reply_id = content.get("data", {}).get("id", "")
                        if reply_id:
                            reply_text = f"[回复:{reply_id}]"
                            text_parts.append(reply_text)
                            logger.debug(f"build_prompt 提取到回复消息: {reply_text}")
                
                # 合并所有文本部分
                combined_text = "".join(text_parts).strip()
                logger.debug(f"build_prompt 合并后的文本: '{combined_text}' (长度: {len(combined_text)})")
                
                if combined_text and len(combined_text) > 2 and not combined_text.startswith("/"):
                    # 清理消息内容
                    cleaned_text = combined_text.replace('“', '"').replace('”', '"')
                    cleaned_text = cleaned_text.replace('‘', "'").replace('’', "'")
                    cleaned_text = cleaned_text.replace('\n', ' ').replace('\r', ' ')
                    cleaned_text = cleaned_text.replace('\t', ' ')
                    cleaned_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned_text)
                    
                    logger.debug(f"build_prompt 清理后的文本: '{cleaned_text}'")
                    
                    text_messages.append({
                        "sender": nickname,
                        "time": msg_time,
                        "content": cleaned_text
                    })
                else:
                    logger.debug(f"build_prompt 跳过文本: '{combined_text}' (长度不足或以/开头)")
            except Exception as e:
                logger.error(f"build_prompt 处理第 {i+1} 条消息时出错: {e}", exc_info=True)
                continue
        
        logger.debug(f"build_prompt 提取到 {len(text_messages)} 条文本消息")
        
        if not text_messages:
            logger.warning("build_prompt 没有提取到有效的文本消息，返回空prompt")
            return ""
        
        logger.debug(f"build_prompt 第一条文本消息: {text_messages[0] if text_messages else '无'}")
        
        # 构建消息文本
        messages_text = "\n".join([
            f"[{msg['time']}] {msg['sender']}: {msg['content']}"
            for msg in text_messages
        ])
        
        max_topics = self.get_max_count()
        
        logger.debug(f"build_prompt 准备构建prompt，max_topics={max_topics}")
        logger.debug(f"build_prompt messages_text 长度: {len(messages_text)}")
        
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
        logger.debug(f"build_prompt 构建的prompt长度: {len(prompt)}")
        logger.debug(f"build_prompt prompt前100字符: {prompt[:100]}...")
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
        logger.debug(f"create_data_objects 开始处理，输入数据数量: {len(topics_data) if topics_data else 0}")
        logger.debug(f"输入数据类型: {type(topics_data)}")
        
        try:
            topics = []
            max_topics = self.get_max_count()
            
            logger.debug(f"处理前 {max_topics} 条话题数据")
            
            for i, topic_data in enumerate(topics_data[:max_topics]):
                logger.debug(f"处理第 {i+1} 条话题数据，类型: {type(topic_data)}")
                
                # 确保topic_data是字典类型，避免'str' object has no attribute 'get'错误
                if not isinstance(topic_data, dict):
                    logger.warning(f"跳过非字典类型的话题数据: {type(topic_data)} - {topic_data}")
                    continue
                    
                try:
                    # 确保数据格式正确
                    topic_name = topic_data.get("topic", "").strip()
                    contributors = topic_data.get("contributors", [])
                    detail = topic_data.get("detail", "").strip()
                    
                    logger.debug(f"话题数据 - 名称: {topic_name}, 参与者: {contributors}, 详情: {detail[:50]}...")
                    
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
                except Exception as e:
                    logger.error(f"处理第 {i+1} 条话题数据时出错: {e}", exc_info=True)
                    continue
            
            logger.debug(f"create_data_objects 完成，创建了 {len(topics)} 个话题对象")
            return topics
            
        except Exception as e:
            logger.error(f"创建话题对象失败: {e}", exc_info=True)
            return []
    
    def extract_text_messages(self, messages: List[Dict]) -> List[Dict]:
        """
        从群聊消息中提取文本消息
        
        Args:
            messages: 群聊消息列表
            
        Returns:
            提取的文本消息列表
        """
        logger.debug(f"extract_text_messages 开始处理，输入消息数量: {len(messages) if messages else 0}")
        logger.debug(f"extract_text_messages 输入消息类型: {type(messages)}")
        
        if not messages:
            logger.warning("extract_text_messages 收到空消息列表")
            return []
        
        text_messages = []
        
        for i, msg in enumerate(messages):
            logger.debug(f"处理第 {i+1} 条消息，类型: {type(msg)}")
            # 确保msg是字典类型，避免'str' object has no attribute 'get'错误
            if not isinstance(msg, dict):
                logger.warning(f"跳过非字典类型的消息: {type(msg)} - {msg}")
                continue
                
            try:
                sender = msg.get("sender", {})
                # 确保sender是字典类型，避免'str' object has no attribute 'get'错误
                if not isinstance(sender, dict):
                    logger.warning(f"extract_text_messages 跳过sender非字典类型的消息: {type(sender)} - {sender}")
                    continue
                    
                nickname = sender.get("nickname", "") or sender.get("card", "")
                msg_time = datetime.fromtimestamp(msg.get("time", 0)).strftime("%H:%M")
                
                for content in msg.get("message", []):
                    if content.get("type") == "text":
                        text = content.get("data", {}).get("text", "").strip()
                        if text and len(text) > 2 and not text.startswith("/"):
                            # 清理消息内容
                            text = text.replace('""', '"').replace('""', '"')
                            text = text.replace(''', "'").replace(''', "'")
                            text = text.replace('\n', ' ').replace('\r', ' ')
                            text = text.replace('\t', ' ')
                            text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
                            text_messages.append({
                                "sender": nickname,
                                "time": msg_time,
                                "content": text.strip()
                            })
            except Exception as e:
                logger.error(f"处理第 {i+1} 条消息时出错: {e}", exc_info=True)
                continue
        
        logger.debug(f"extract_text_messages 完成，提取到 {len(text_messages)} 条文本消息")
        if text_messages:
            logger.debug(f"extract_text_messages 第一条文本消息: {text_messages[0]}")
        return text_messages
    
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
            logger.debug(f"analyze_topics 开始处理，消息数量: {len(messages) if messages else 0}")
            logger.debug(f"消息类型: {type(messages)}")
            if messages:
                logger.debug(f"第一条消息类型: {type(messages[0]) if messages else '无'}")
                logger.debug(f"第一条消息内容: {messages[0] if messages else '无'}")
            
            # 检查是否有有效的文本消息
            text_messages = self.extract_text_messages(messages)
            logger.debug(f"提取到 {len(text_messages)} 条文本消息")
            
            if not text_messages:
                logger.info("没有有效的文本消息，返回空结果")
                return [], TokenUsage()
            
            logger.info(f"开始分析 {len(text_messages)} 条文本消息中的话题")
            logger.debug(f"文本消息类型: {type(text_messages)}")
            if text_messages:
                logger.debug(f"第一条文本消息类型: {type(text_messages[0])}")
                logger.debug(f"第一条文本消息内容: {text_messages[0]}")
            
            # 直接传入原始消息，让 build_prompt 方法处理
            return await self.analyze(messages, umo)
            
        except Exception as e:
            logger.error(f"话题分析失败: {e}", exc_info=True)
            return [], TokenUsage()