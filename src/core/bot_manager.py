"""
Bot实例管理模块
统一管理bot实例的获取、设置和使用
"""

from typing import Any

from astrbot.api import logger


class BotManager:
    """Bot实例管理器 - 统一管理所有bot相关操作"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self._bot_instances = {}  # 改为字典：{platform_id: bot_instance}
        self._platforms = {}  # 存储平台对象以访问配置
        self._bot_qq_ids = []  # 支持多个QQ号
        self._context = None
        self._is_initialized = False
        self._default_platform = "default"  # 默认平台

    def set_context(self, context):
        """设置AstrBot上下文"""
        self._context = context

    def set_bot_instance(self, bot_instance, platform_id=None):
        """设置bot实例，支持指定平台ID"""
        if not platform_id:
            platform_id = self._get_platform_id_from_instance(bot_instance)

        if bot_instance and platform_id:
            self._bot_instances[platform_id] = bot_instance
            # 自动提取QQ号
            bot_qq_id = self._extract_bot_qq_id(bot_instance)
            if bot_qq_id and bot_qq_id not in self._bot_qq_ids:
                self._bot_qq_ids.append(str(bot_qq_id))

    def set_bot_qq_ids(self, bot_qq_ids):
        """设置bot QQ号（支持单个QQ号或QQ号列表）"""
        if isinstance(bot_qq_ids, list):
            self._bot_qq_ids = [str(qq) for qq in bot_qq_ids if qq]
            if self._bot_qq_ids:
                self._bot_qq_id = self._bot_qq_ids[0]  # 保持向后兼容
        elif bot_qq_ids:
            self._bot_qq_id = str(bot_qq_ids)
            self._bot_qq_ids = [str(bot_qq_ids)]

    def get_bot_instance(self, platform_id=None):
        """获取指定平台的bot实例，如果不指定则返回第一个可用的实例"""
        if platform_id:
            # 如果指定了平台ID，尝试获取
            return self._bot_instances.get(platform_id)

        # 没有指定平台ID
        if self._bot_instances:
            # 如果只有一个实例，直接返回
            if len(self._bot_instances) == 1:
                return list(self._bot_instances.values())[0]

            # 如果有多个实例，必须指定 platform_id
            logger.error(
                f"存在多个Bot实例 {list(self._bot_instances.keys())} 但未指定 platform_id，"
                "无法确定使用哪个实例。请明确指定 platform_id。"
            )
            return None

        # 没有任何平台可用
        logger.error("没有任何可用的bot实例")
        return None

    def get_all_bot_instances(self) -> dict:
        """获取所有已加载的bot实例 {platform_id: bot_instance}"""
        return self._bot_instances.copy()

    def has_bot_instance(self) -> bool:
        """检查是否有可用的bot实例"""
        return bool(self._bot_instances)

    def has_bot_qq_id(self) -> bool:
        """检查是否有配置的bot QQ号"""
        return bool(self._bot_qq_ids)

    def is_ready_for_auto_analysis(self) -> bool:
        """检查是否准备好进行自动分析"""
        return self.has_bot_instance() and self.has_bot_qq_id()

    def _get_platform_id_from_instance(self, bot_instance):
        """从bot实例获取平台ID"""
        if hasattr(bot_instance, "platform") and isinstance(bot_instance.platform, str):
            return bot_instance.platform
        return self._default_platform

    async def auto_discover_bot_instances(self):
        """自动发现所有可用的bot实例"""
        if not self._context or not hasattr(self._context, "platform_manager"):
            return {}

        # 使用新版 API 获取所有平台实例
        platforms = self._context.platform_manager.get_insts()
        discovered = {}

        for platform in platforms:
            # 获取bot实例
            bot_client = None
            if hasattr(platform, "get_client"):
                bot_client = platform.get_client()
            elif hasattr(platform, "bot"):
                bot_client = platform.bot

            if (
                bot_client
                and hasattr(platform, "metadata")
                and hasattr(platform.metadata, "id")
            ):
                platform_id = platform.metadata.id
                self.set_bot_instance(bot_client, platform_id)
                self._platforms[platform_id] = platform
                discovered[platform_id] = bot_client

        return discovered

    async def initialize_from_config(self):
        """从配置初始化bot管理器"""
        # 设置配置的bot QQ号列表
        bot_qq_ids = self.config_manager.get_bot_qq_ids()
        if bot_qq_ids:
            self.set_bot_qq_ids(bot_qq_ids)

        # 自动发现所有bot实例
        discovered = await self.auto_discover_bot_instances()
        self._is_initialized = True

        # 返回发现的实例字典
        return discovered

    def get_status_info(self) -> dict[str, Any]:
        """获取bot管理器状态信息"""
        return {
            "has_bot_instance": self.has_bot_instance(),
            "has_bot_qq_id": self.has_bot_qq_id(),
            "bot_qq_ids": self._bot_qq_ids,
            "platform_count": len(self._bot_instances),
            "platforms": list(self._bot_instances.keys()),
            "ready_for_auto_analysis": self.is_ready_for_auto_analysis(),
        }

    def update_from_event(self, event):
        """从事件更新bot实例（用于手动命令）"""
        # 检查是否为 QQ 平台事件
        if (
            hasattr(event, "get_platform_name")
            and event.get_platform_name() != "aiocqhttp"
        ):
            return False

        if hasattr(event, "bot") and event.bot:
            # 从事件中获取平台ID
            platform_id = None
            if hasattr(event, "platform") and isinstance(event.platform, str):
                platform_id = event.platform
            elif hasattr(event, "metadata") and hasattr(event.metadata, "id"):
                platform_id = event.metadata.id

            self.set_bot_instance(event.bot, platform_id)
            # 每次都尝试从bot实例提取QQ号
            bot_qq_id = self._extract_bot_qq_id(event.bot)
            if bot_qq_id:
                # 将单个QQ号转换为列表，保持统一处理
                self.set_bot_qq_ids([bot_qq_id])
            else:
                # 如果bot实例没有QQ号，尝试使用配置的QQ号列表
                config_qq_ids = self.config_manager.get_bot_qq_ids()
                if config_qq_ids:
                    self.set_bot_qq_ids(config_qq_ids)
            return True
        return False

    def _extract_bot_qq_id(self, bot_instance):
        """从bot实例中提取QQ号（单个）"""
        # 尝试多种方式获取bot QQ号
        if hasattr(bot_instance, "self_id") and bot_instance.self_id:
            return str(bot_instance.self_id)
        elif hasattr(bot_instance, "qq") and bot_instance.qq:
            return str(bot_instance.qq)
        elif hasattr(bot_instance, "user_id") and bot_instance.user_id:
            return str(bot_instance.user_id)
        return None

    def validate_for_message_fetching(self, group_id: str) -> bool:
        """验证是否可以进行消息获取"""
        return self.has_bot_instance() and bool(group_id)

    def should_filter_bot_message(self, sender_id: str) -> bool:
        """判断是否应该过滤bot自己的消息（支持多个QQ号）"""
        if not self._bot_qq_ids:
            return False

        sender_id_str = str(sender_id)
        # 检查是否在QQ号列表中
        return sender_id_str in self._bot_qq_ids

    def is_plugin_enabled(self, platform_id: str, plugin_name: str) -> bool:
        """检查指定平台是否启用了该插件"""
        if platform_id not in self._platforms:
            # 如果找不到平台对象（例如是手动添加的），默认认为启用
            # 或者可以返回 True，因为无法进行否定检查
            return True

        platform = self._platforms[platform_id]
        if not hasattr(platform, "config") or not isinstance(platform.config, dict):
            return True

        plugin_set = platform.config.get("plugin_set", ["*"])

        if plugin_set is None:
            return False  # 如果明确为 None, 视为都不启用? 或者默认? Default is ["*"] usually.

        if "*" in plugin_set:
            return True

        return plugin_name in plugin_set
