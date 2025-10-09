"""
金句分析模块
专门处理群聊金句提取和分析
"""

from typing import List, Dict, Tuple
from datetime import datetime
from astrbot.api import logger
from ...models.data_models import GoldenQuote, TokenUsage
from .base_analyzer import BaseAnalyzer
from ..utils.json_utils import extract_golden_quotes_with_regex



class GoldenQuoteAnalyzer(BaseAnalyzer):
    """
    金句分析器
    专门处理群聊金句的提取和分析
    """
    
    def get_data_type(self) -> str:
        """获取数据类型标识"""
        return "金句"
    
    def get_max_count(self) -> int:
        """获取最大金句数量"""
        return self.config_manager.get_max_golden_quotes()
    
    def get_max_tokens(self) -> int:
        """获取最大token数"""
        return 1500
    
    def get_temperature(self) -> float:
        """获取温度参数"""
        return 0.7
    
    def build_prompt(self, messages: List[Dict]) -> str:
        """
        构建金句分析提示词
        
        Args:
            messages: 群聊的文本消息列表
            
        Returns:
            提示词字符串
        """
        if not messages:
            return ""
        
        # 构建消息文本
        messages_text = "\n".join([
            f"[{msg['time']}] {msg['sender']}: {msg['content']}"
            for msg in messages
        ])
        
        prompt = f"""
请从以下群聊记录中挑选出{max_golden_quotes}句最具冲击力、最令人惊叹的"金句"。这些金句需满足：
- 核心标准：**逆天的神人发言**，即具备颠覆常识的脑洞、逻辑跳脱的表达或强烈反差感的原创内容
- 典型特征：包含某些争议话题元素、夸张类比、反常规结论、一本正经的"胡说八道"或突破语境的清奇思路，并且具备一定的冲击力，让人印象深刻。

对于每个金句，请提供：
1. 原文内容（完整保留发言细节）
2. 发言人昵称
3. 选择理由（具体说明其"逆天"之处，如逻辑颠覆点/脑洞角度/反差感/争议话题元素）

此外，我将对你进行严格约束：
- 优先筛选 **逆天指数最高** 的内容：发情、性压抑话题 > 争议话题 > 元素级 > 颠覆认知级 > 逻辑跳脱级 > 趣味调侃级，剔除单纯玩梗或网络热词堆砌的普通发言
- 重点标记包含极端类比、反常识论证或无厘头结论的内容，并且包含一定的争议话题元素。

群聊记录：
{messages_text}

请以JSON格式返回，格式如下：
[
  {{
    "content": "金句原文",
    "sender": "发言人昵称",
    "reason": "选择这句话的理由（需明确说明逆天特质）"
  }}
]
"""
        return prompt
    
    def extract_with_regex(self, result_text: str, max_count: int) -> List[Dict]:
        """
        使用正则表达式提取金句信息
        
        Args:
            result_text: LLM响应文本
            max_count: 最大提取数量
            
        Returns:
            金句数据列表
        """
        return extract_golden_quotes_with_regex(result_text, max_count)
    
    def create_data_objects(self, quotes_data: List[Dict]) -> List[GoldenQuote]:
        """
        创建金句对象列表
        
        Args:
            quotes_data: 原始金句数据列表
            
        Returns:
            GoldenQuote对象列表
        """
        try:
            quotes = []
            max_quotes = self.get_max_count()
            
            for quote_data in quotes_data[:max_quotes]:
                # 确保数据格式正确
                content = quote_data.get("content", "").strip()
                sender = quote_data.get("sender", "").strip()
                reason = quote_data.get("reason", "").strip()
                
                # 验证必要字段
                if not content or not sender or not reason:
                    logger.warning(f"金句数据格式不完整，跳过: {quote_data}")
                    continue
                
                quotes.append(GoldenQuote(
                    content=content,
                    sender=sender,
                    reason=reason
                ))
            
            return quotes
            
        except Exception as e:
            logger.error(f"创建金句对象失败: {e}")
            return []
    
    def extract_interesting_messages(self, messages: List[Dict]) -> List[Dict]:
        """
        提取圣经的文本消息
        
        Args:
            messages: 群聊消息列表
            
        Returns:
            圣经的文本消息列表
        """
        try:
            interesting_messages = []
            
            for msg in messages:
                sender = msg.get("sender", {})
                nickname = sender.get("nickname", "") or sender.get("card", "")
                msg_time = datetime.fromtimestamp(msg.get("time", 0)).strftime("%H:%M")
                
                for content in msg.get("message", []):
                    if content.get("type") == "text":
                        text = content.get("data", {}).get("text", "").strip()
                        # 过滤长度适中、可能圣经的消息
                        if 5 <= len(text) <= 100 and not text.startswith(("http", "www", "/")):
                            interesting_messages.append({
                                "sender": nickname,
                                "time": msg_time,
                                "content": text
                            })
            
            return interesting_messages
            
        except Exception as e:
            logger.error(f"提取圣经消息失败: {e}")
            return []
    
    async def analyze_golden_quotes(self, messages: List[Dict], umo: str = None) -> Tuple[List[GoldenQuote], TokenUsage]:
        """
        分析群聊金句
        
        Args:
            messages: 群聊消息列表
            umo: 模型唯一标识符
            
        Returns:
            (金句列表, Token使用统计)
        """
        try:
            # 提取圣经的文本消息
            interesting_messages = self.extract_interesting_messages(messages)
            
            if not interesting_messages:
                logger.info("没有符合条件的圣经消息，返回空结果")
                return [], TokenUsage()
            
            logger.info(f"开始从 {len(interesting_messages)} 条圣经消息中提取金句")
            return await self.analyze(interesting_messages, umo)
            
        except Exception as e:
            logger.error(f"金句分析失败: {e}")
            return [], TokenUsage()