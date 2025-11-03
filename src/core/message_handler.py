"""
消息处理模块
负责群聊消息的获取、过滤和预处理
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import defaultdict
from astrbot.api import logger
from ...src.models.data_models import GroupStatistics, TokenUsage, EmojiStatistics, ActivityVisualization
from ...src.visualization.activity_charts import ActivityVisualizer


class MessageHandler:
    """消息处理器"""

    def __init__(self, config_manager, bot_manager=None):
        self.config_manager = config_manager
        self.activity_visualizer = ActivityVisualizer()
        self.bot_manager = bot_manager

    async def set_bot_qq_id(self, bot_qq_id: str):
        """设置机器人QQ号（保持向后兼容）"""
        try:
            if self.bot_manager:
                self.bot_manager.set_bot_qq_id(bot_qq_id)
            logger.info(f"设置机器人QQ号: {bot_qq_id}")
        except Exception as e:
            logger.error(f"设置机器人QQ号失败: {e}")

    def set_bot_manager(self, bot_manager):
        """设置bot管理器"""
        self.bot_manager = bot_manager

    def _extract_bot_qq_id_from_instance(self, bot_instance):
        """从bot实例中提取QQ号"""
        if hasattr(bot_instance, 'self_id') and bot_instance.self_id:
            return str(bot_instance.self_id)
        elif hasattr(bot_instance, 'qq') and bot_instance.qq:
            return str(bot_instance.qq)
        elif hasattr(bot_instance, 'user_id') and bot_instance.user_id:
            return str(bot_instance.user_id)
        return None

    async def fetch_group_messages(self, bot_instance, group_id: str, days: int) -> List[Dict]:
        """获取群聊消息记录"""
        try:
            # 验证参数
            if not group_id or not bot_instance:
                logger.error(f"群 {group_id} 参数无效")
                return []

            # 确保bot_manager有QQ号用于过滤
            if self.bot_manager and not self.bot_manager.has_bot_qq_id():
                # 尝试从bot_instance提取QQ号
                bot_qq_id = self._extract_bot_qq_id_from_instance(bot_instance)
                if bot_qq_id:
                    self.bot_manager.set_bot_qq_id(bot_qq_id)

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

            while query_rounds < max_rounds:
                try:
                    # 构造请求参数
                    payloads = {
                        "group_id": int(group_id) if group_id.isdigit() else group_id,
                        "count": 200,
                    }
                    
                    # 添加 message_seq（如果不是第一轮）
                    if message_seq:
                        payloads["message_seq"] = message_seq

                    # 尝试调用 API
                    result = None
                    api_error = None
                    
                    if hasattr(bot_instance, 'call_action'):
                        try:
                            # aiocqhttp (CQHttp) 方式
                            result = await bot_instance.call_action("get_group_msg_history", **payloads)
                        except Exception as api_err:
                            api_error = api_err
                            logger.error(f"群 {group_id} API 调用失败: {api_err}")
                            
                            # 第一次失败就放弃（该 API 不支持）
                            if query_rounds == 0:
                                logger.error(f"群 {group_id} 当前 OneBot 实现不支持 get_group_msg_history API")
                                return []
                    elif hasattr(bot_instance, 'api'):
                        # QQ官方 bot (botClient) 方式 - 官方API不支持历史消息
                        logger.error(f"群 {group_id} 检测到 QQ 官方 Bot，官方 API 不支持获取历史消息")
                        return []
                    else:
                        logger.error(f"群 {group_id} 未知的 bot_instance 类型，无法调用 API")
                        logger.error(f"bot_instance 类型: {type(bot_instance)}")
                        return []

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
                    has_out_of_range_message = False

                    for msg in round_messages:
                        try:
                            msg_time = datetime.fromtimestamp(msg.get("time", 0))
                            
                            # 记录本轮最老的消息时间
                            if oldest_msg_time is None or msg_time < oldest_msg_time:
                                oldest_msg_time = msg_time
                            
                            # 检查是否已经超出时间范围
                            if msg_time < start_time:
                                has_out_of_range_message = True
                                # 继续处理本轮剩余消息，但不再查询下一轮
                                continue

                            # 过滤掉机器人自己的消息
                            sender_id = str(msg.get("sender", {}).get("user_id", ""))
                            if self.bot_manager and self.bot_manager.should_filter_bot_message(sender_id):
                                continue

                            if msg_time >= start_time and msg_time <= end_time:
                                messages.append(msg)
                                valid_messages_in_round += 1
                        except Exception as msg_error:
                            logger.warning(f"群 {group_id} 处理单条消息失败: {msg_error}")
                            continue

                    # 如果本轮有消息已经超出时间范围，立即停止获取
                    if has_out_of_range_message:
                        logger.info(f"群 {group_id} 已获取到时间范围外的消息（最老消息时间: {oldest_msg_time.strftime('%Y-%m-%d %H:%M:%S')}），停止获取。共获取 {len(messages)} 条消息")
                        break

                    # 如果本轮没有获取到任何有效消息，停止获取
                    if valid_messages_in_round == 0:
                        logger.warning(f"群 {group_id} 本轮未获取到有效消息，停止获取")
                        break

                    # 如果已经获取到足够的消息（达到 max_messages），停止获取
                    if len(messages) >= max_messages:
                        logger.info(f"群 {group_id} 已达到消息数量限制（{len(messages)} 条，限制 {max_messages} 条），停止获取")
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

            # ========== 最终清理步骤:严格过滤和限制 ==========
            original_count = len(messages)
            
            # 1. 严格过滤时间范围外的消息
            messages = [
                msg for msg in messages
                if start_time <= datetime.fromtimestamp(msg.get("time", 0)) <= end_time
            ]
            time_filtered_count = len(messages)
            
            # 2. 严格限制消息数量
            if len(messages) > max_messages:
                # 保留最新的消息(假设messages已按时间排序,从新到旧)
                messages = messages[:max_messages]
                logger.info(f"群 {group_id} 消息数量超过限制，已截断: {time_filtered_count} -> {max_messages} 条")
            
            # 记录清理结果
            if original_count != len(messages):
                logger.info(f"群 {group_id} 最终清理: 原始 {original_count} 条 -> 时间过滤 {time_filtered_count} 条 -> 最终 {len(messages)} 条")
            
            logger.info(f"群 {group_id} 消息获取完成，共获取到 {len(messages)} 条有效消息（时间范围: 近{days}天），查询轮数: {query_rounds}")
            return messages

        except Exception as e:
            logger.error(f"群 {group_id} 获取群聊消息记录失败: {e}", exc_info=True)
            return []

    def calculate_statistics(self, messages: List[Dict]) -> GroupStatistics:
        """计算基础统计数据"""
        total_chars = 0
        participants = set()
        hour_counts = defaultdict(int)
        emoji_statistics = EmojiStatistics()

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
                    # QQ基础表情
                    emoji_statistics.face_count += 1
                    face_id = content.get("data", {}).get("id", "unknown")
                    emoji_statistics.face_details[f"face_{face_id}"] = emoji_statistics.face_details.get(f"face_{face_id}", 0) + 1
                elif content.get("type") == "mface":
                    # 动画表情/魔法表情
                    emoji_statistics.mface_count += 1
                    emoji_id = content.get("data", {}).get("emoji_id", "unknown")
                    emoji_statistics.face_details[f"mface_{emoji_id}"] = emoji_statistics.face_details.get(f"mface_{emoji_id}", 0) + 1
                elif content.get("type") == "bface":
                    # 超级表情
                    emoji_statistics.bface_count += 1
                    emoji_id = content.get("data", {}).get("p", "unknown")
                    emoji_statistics.face_details[f"bface_{emoji_id}"] = emoji_statistics.face_details.get(f"bface_{emoji_id}", 0) + 1
                elif content.get("type") == "sface":
                    # 小表情
                    emoji_statistics.sface_count += 1
                    emoji_id = content.get("data", {}).get("id", "unknown")
                    emoji_statistics.face_details[f"sface_{emoji_id}"] = emoji_statistics.face_details.get(f"sface_{emoji_id}", 0) + 1
                elif content.get("type") == "image":
                    # 检查是否是动画表情（通过summary字段判断）
                    data = content.get("data", {})
                    summary = data.get("summary", "")
                    if "动画表情" in summary or "表情" in summary:
                        # 动画表情（以image形式发送）
                        emoji_statistics.mface_count += 1
                        file_name = data.get("file", "unknown")
                        emoji_statistics.face_details[f"animated_{file_name}"] = emoji_statistics.face_details.get(f"animated_{file_name}", 0) + 1
                    else:
                        # 普通图片，不计入表情统计
                        pass
                elif content.get("type") in ["record", "video"] and "emoji" in str(content.get("data", {})).lower():
                    # 其他可能的表情类型
                    emoji_statistics.other_emoji_count += 1

        # 找出最活跃时段
        most_active_hour = max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else 0
        most_active_period = f"{most_active_hour:02d}:00-{(most_active_hour+1)%24:02d}:00"

        # 生成活跃度可视化数据
        activity_visualization = self.activity_visualizer.generate_activity_visualization(messages)

        return GroupStatistics(
            message_count=len(messages),
            total_characters=total_chars,
            participant_count=len(participants),
            most_active_period=most_active_period,
            golden_quotes=[],
            emoji_count=emoji_statistics.total_emoji_count,  # 保持向后兼容
            emoji_statistics=emoji_statistics,
            activity_visualization=activity_visualization,
            token_usage=TokenUsage()
        )