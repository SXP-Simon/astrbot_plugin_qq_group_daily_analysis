"""
消息处理模块
负责群聊消息的获取、过滤和预处理
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import defaultdict
from astrbot.api import logger
from ...src.models.data_models import GroupStatistics, TokenUsage


class MessageHandler:
    """消息处理器"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.bot_qq_id = None

    async def set_bot_qq_id(self, bot_instance):
        """设置机器人QQ号"""
        try:
            if bot_instance and not self.bot_qq_id:
                login_info = await bot_instance.api.call_action("get_login_info")
                self.bot_qq_id = str(login_info.get("user_id", ""))
                logger.info(f"获取到机器人QQ号: {self.bot_qq_id}")
        except Exception as e:
            logger.error(f"获取机器人QQ号失败: {e}")

    async def fetch_group_messages(self, bot_instance, group_id: str, days: int) -> List[Dict]:
        """获取群聊消息记录"""
        try:
            if not bot_instance or not group_id:
                logger.error(f"群 {group_id} 无效的客户端或群组ID")
                return []

            # 计算时间范围
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            messages = []
            message_seq = 0
            query_rounds = 0
            max_rounds = self.config_manager.get_max_query_rounds()
            max_messages = self.config_manager.get_max_messages()
            consecutive_failures = 0
            max_failures = 3

            logger.info(f"开始获取群 {group_id} 近 {days} 天的消息记录")
            logger.info(f"时间范围: {start_time.strftime('%Y-%m-%d %H:%M:%S')} 到 {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

            while len(messages) < max_messages and query_rounds < max_rounds:
                try:
                    payloads = {
                        "group_id": group_id,
                        "message_seq": message_seq,
                        "count": 200,
                        "reverseOrder": True,
                    }

                    result = await bot_instance.api.call_action("get_group_msg_history", **payloads)

                    if not result or "messages" not in result:
                        logger.warning(f"群 {group_id} API返回无效结果: {result}")
                        consecutive_failures += 1
                        if consecutive_failures >= max_failures:
                            break
                        continue

                    round_messages = result.get("messages", [])

                    if not round_messages:
                        logger.info(f"群 {group_id} 没有更多消息，结束获取")
                        break

                    # 重置失败计数
                    consecutive_failures = 0

                    # 过滤时间范围内的消息
                    valid_messages_in_round = 0
                    oldest_msg_time = None

                    for msg in round_messages:
                        try:
                            msg_time = datetime.fromtimestamp(msg.get("time", 0))
                            oldest_msg_time = msg_time

                            # 过滤掉机器人自己的消息
                            sender_id = str(msg.get("sender", {}).get("user_id", ""))
                            if self.bot_qq_id and sender_id == self.bot_qq_id:
                                continue

                            if msg_time >= start_time and msg_time <= end_time:
                                messages.append(msg)
                                valid_messages_in_round += 1
                        except Exception as msg_error:
                            logger.warning(f"群 {group_id} 处理单条消息失败: {msg_error}")
                            continue

                    # 如果最老的消息时间已经超出范围，停止获取
                    if oldest_msg_time and oldest_msg_time < start_time:
                        logger.info(f"群 {group_id} 已获取到时间范围外的消息，停止获取。共获取 {len(messages)} 条消息")
                        break

                    if valid_messages_in_round == 0:
                        logger.warning(f"群 {group_id} 本轮未获取到有效消息")
                        break

                    message_seq = round_messages[0]["message_id"]
                    query_rounds += 1

                    # 添加延迟避免请求过快
                    if query_rounds % 5 == 0:
                        await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(f"群 {group_id} 获取消息失败 (第{query_rounds+1}轮): {e}")
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        logger.error(f"群 {group_id} 连续失败 {max_failures} 次，停止获取")
                        break
                    await asyncio.sleep(1)

            logger.info(f"群 {group_id} 消息获取完成，共获取 {len(messages)} 条消息，查询轮数: {query_rounds}")
            return messages

        except Exception as e:
            logger.error(f"群 {group_id} 获取群聊消息记录失败: {e}", exc_info=True)
            return []

    def calculate_statistics(self, messages: List[Dict]) -> GroupStatistics:
        """计算基础统计数据"""
        total_chars = 0
        participants = set()
        hour_counts = defaultdict(int)
        emoji_count = 0

        for msg in messages:
            sender_id = str(msg.get("sender", {}).get("user_id", ""))
            participants.add(sender_id)

            # 统计时间分布
            msg_time = datetime.fromtimestamp(msg.get("time", 0))
            hour_counts[msg_time.hour] += 1

            # 处理消息内容
            for content in msg.get("message", []):
                if content.get("type") == "text":
                    text = content.get("data", {}).get("text", "")
                    total_chars += len(text)
                elif content.get("type") == "face":
                    emoji_count += 1

        # 找出最活跃时段
        most_active_hour = max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else 0
        most_active_period = f"{most_active_hour:02d}:00-{(most_active_hour+1)%24:02d}:00"

        return GroupStatistics(
            message_count=len(messages),
            total_characters=total_chars,
            participant_count=len(participants),
            most_active_period=most_active_period,
            golden_quotes=[],
            emoji_count=emoji_count,
            token_usage=TokenUsage()
        )