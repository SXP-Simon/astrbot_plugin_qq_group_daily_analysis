"""
Bot实例管理模块
统一管理bot实例的获取、设置和使用

已重构以集成 DDD PlatformAdapter 架构，支持多平台扩展。
"""

from typing import Any, Optional

from ..utils.logger import logger

from ..infrastructure.platform import PlatformAdapter, PlatformAdapterFactory


class BotManager:
    """
    Bot实例管理器 - 统一管理所有bot相关操作

    与 DDD 架构集成，为每个 bot 实例创建对应的 PlatformAdapter，
    实现跨平台支持。
    """

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self._bot_instances = {}  # {platform_id: bot_instance}
        self._adapters = {}  # {platform_id: PlatformAdapter} - DDD 集成
        self._platforms = {}  # 存储平台对象以访问配置
        self._bot_self_ids = []  # 支持多个机器人账号 ID (原 _bot_qq_ids)
        self._context = None
        self._is_initialized = False
        self._default_platform = "default"  # 默认平台

    def set_context(self, context):
        """设置AstrBot上下文"""
        self._context = context

    def set_bot_instance(self, bot_instance, platform_id=None, platform_name=None):
        """
        设置bot实例，支持指定平台ID

        同时会创建对应的 PlatformAdapter（如果平台被支持）。
        """
        if not platform_id:
            platform_id = self._get_platform_id_from_instance(bot_instance)

        if bot_instance and platform_id:
            self._bot_instances[platform_id] = bot_instance

            # 为 DDD 集成创建 PlatformAdapter
            if platform_name is None:
                platform_name = self._detect_platform_name(bot_instance)

            if platform_name and PlatformAdapterFactory.is_supported(platform_name):
                adapter_config = {
                    "bot_self_ids": self._bot_self_ids.copy(),
                    "bot_qq_ids": self._bot_self_ids.copy(),  # 兼容旧适配器
                }
                adapter = PlatformAdapterFactory.create(
                    platform_name, bot_instance, adapter_config
                )
                if adapter:
                    self._adapters[platform_id] = adapter
                    logger.debug(
                        f"已为 {platform_id} ({platform_name}) 创建 PlatformAdapter"
                    )

            # 自动提取机器人 ID
            bot_self_id = self._extract_bot_self_id(bot_instance)
            if bot_self_id and bot_self_id not in self._bot_self_ids:
                self._bot_self_ids.append(str(bot_self_id))

    def set_bot_self_ids(self, bot_self_ids):
        """设置机器人 ID 列表（支持单个 ID 或 ID 列表）"""
        if isinstance(bot_self_ids, list):
            self._bot_self_ids = [str(uid) for uid in bot_self_ids if uid]
        elif bot_self_ids:
            self._bot_self_ids = [str(bot_self_ids)]

    def set_bot_qq_ids(self, bot_qq_ids):
        """设置bot QQ号（兼容旧方法，建议使用 set_bot_self_ids）"""
        self.set_bot_self_ids(bot_qq_ids)

    def get_bot_instance(self, platform_id=None):
        """获取指定平台的bot实例，如果不指定则返回第一个可用的实例"""
        if platform_id:
            # 如果指定了平台ID，尝试获取
            instance = self._bot_instances.get(platform_id)
            if not instance and platform_id in self._platforms:
                self._refresh_from_stored_platforms()
                instance = self._bot_instances.get(platform_id)
            return instance

        # 没有指定平台ID
        if not self._bot_instances and self._platforms:
            self._refresh_from_stored_platforms()

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

    def _refresh_from_stored_platforms(self):
        """尝试从已存储的平台对象中刷新 bot 实例 (Lazy Load)"""
        for platform_id, platform in self._platforms.items():
            if platform_id in self._bot_instances:
                continue

            bot_client = None
            # 优先尝试 get_client()
            if hasattr(platform, "get_client"):
                bot_client = platform.get_client()

            # 如果 get_client() 返回 None，尝试直接访问属性
            if not bot_client and hasattr(platform, "bot"):
                bot_client = platform.bot
            if not bot_client and hasattr(platform, "client"):
                # AstrBot v4.14.4 DiscordPlatformAdapter uses 'client' attribute
                bot_client = platform.client

            if bot_client:
                platform_name = None
                if hasattr(platform, "metadata"):
                    # 优先使用 type
                    if hasattr(platform.metadata, "type"):
                        platform_name = platform.metadata.type
                    elif hasattr(platform.metadata, "name"):
                        platform_name = platform.metadata.name

                # 后备检测：如果不支持名称
                if not platform_name or not PlatformAdapterFactory.is_supported(
                    str(platform_name)
                ):
                    detected = self._detect_platform_name(bot_client)
                    if detected:
                        platform_name = detected

                self.set_bot_instance(bot_client, platform_id, platform_name)
                logger.info(f"懒加载发现平台 {platform_id} 的 bot 实例")

    def get_all_bot_instances(self) -> dict:
        """获取所有已加载的bot实例 {platform_id: bot_instance}"""
        return self._bot_instances.copy()

    def has_bot_instance(self) -> bool:
        """检查是否有可用的bot实例"""
        return bool(self._bot_instances)

    def has_bot_self_id(self) -> bool:
        """检查是否有配置的机器人 ID"""
        return bool(self._bot_self_ids)

    def has_bot_qq_id(self) -> bool:
        """检查是否有配置的bot QQ号 (兼容旧方法)"""
        return self.has_bot_self_id()

    def is_ready_for_auto_analysis(self) -> bool:
        """检查是否准备好进行自动分析"""
        return self.has_bot_instance() and self.has_bot_self_id()

    def _get_platform_id_from_instance(self, bot_instance):
        """从bot实例获取平台ID"""
        if hasattr(bot_instance, "platform") and isinstance(bot_instance.platform, str):
            return bot_instance.platform
        return self._default_platform

    def _detect_platform_name(self, bot_instance) -> Optional[str]:
        """
        从 bot 实例检测平台名称，用于创建适配器。

        返回平台名称如 'aiocqhttp', 'discord' 等。

        检测优先级:
        1. bot 实例的 platform 属性
        2. 已知的 API 特征检测
        3. 类名模式匹配（作为后备方案）
        """
        # 优先使用 platform 属性
        if hasattr(bot_instance, "platform"):
            platform = bot_instance.platform
            if isinstance(platform, str):
                return platform

        # 检查已知的 API 特征（平台无关的方式）
        # OneBot/aiocqhttp 特征: 有 call_action 方法
        if hasattr(bot_instance, "call_action"):
            return "aiocqhttp"

        # 使用工厂的已注册平台列表进行类名匹配
        class_name = type(bot_instance).__name__.lower()
        for platform_name in PlatformAdapterFactory.get_supported_platforms():
            if platform_name in class_name:
                return platform_name

        # 通用类名模式匹配（用于尚未注册的平台）
        known_patterns = {
            "cqhttp": "aiocqhttp",
            "onebot": "aiocqhttp",
        }
        for pattern, platform in known_patterns.items():
            if pattern in class_name:
                return platform

        return None

    # ==================== DDD 集成方法 ====================

    def get_adapter(self, platform_id: str = None) -> Optional[PlatformAdapter]:
        """
        获取指定平台的 PlatformAdapter。

        这是 DDD 架构操作的主要方法。
        """
        if platform_id:
            return self._adapters.get(platform_id)

        if self._adapters:
            if len(self._adapters) == 1:
                return list(self._adapters.values())[0]

            logger.error(
                f"存在多个适配器 {list(self._adapters.keys())}，但未指定 platform_id。"
            )
            return None

        return None

    def get_all_adapters(self) -> dict:
        """获取所有 PlatformAdapter 实例 {platform_id: adapter}"""
        return self._adapters.copy()

    def has_adapter(self, platform_id: str = None) -> bool:
        """检查指定平台是否有适配器"""
        if platform_id:
            return platform_id in self._adapters
        return bool(self._adapters)

    def can_analyze(self, platform_id: str = None) -> bool:
        """使用 DDD 能力检查平台是否支持分析"""
        adapter = self.get_adapter(platform_id)
        if adapter:
            return adapter.get_capabilities().can_analyze()
        return False

    async def auto_discover_bot_instances(self):
        """
        自动发现所有可用的bot实例

        同时为每个发现的 bot 创建对应的 PlatformAdapter。
        """
        if not self._context or not hasattr(self._context, "platform_manager"):
            return {}

        # 使用新版 API 获取所有平台实例
        platforms = self._context.platform_manager.get_insts()
        discovered = {}

        logger.info(
            f"auto_discover_bot_instances: 在管理器中发现 {len(platforms)} 个平台。"
        )

        for platform in platforms:
            # 获取bot实例
            bot_client = None
            if hasattr(platform, "get_client"):
                bot_client = platform.get_client()

            if not bot_client and hasattr(platform, "bot"):
                bot_client = platform.bot
            if not bot_client and hasattr(platform, "client"):
                bot_client = platform.client

            # 健壮地获取元数据
            metadata = getattr(platform, "metadata", None)
            if not metadata and hasattr(platform, "meta"):
                try:
                    metadata = platform.meta()
                except Exception:
                    pass

            # 检查是否有有效的元数据和ID
            platform_id = None
            if metadata:
                if hasattr(metadata, "id"):
                    platform_id = metadata.id
                elif isinstance(metadata, dict):
                    platform_id = metadata.get("id")

            if platform_id:
                # KNOWLEDGE DISCOVERY: Log metadata for debugging custom IDs
                logger.info(
                    f"[群分析插件 BotManager]: Log metadata for debugging custom IDs ,Platform: {platform_id}, Metadata Type: {getattr(metadata, 'type', 'N/A')}, Metadata Name: {getattr(metadata, 'name', 'N/A')}"
                )

                # 从元数据检测平台名称
                platform_name = None
                # 优先使用 type
                if hasattr(metadata, "type"):
                    platform_name = metadata.type
                elif isinstance(metadata, dict) and "type" in metadata:
                    platform_name = metadata["type"]
                elif hasattr(metadata, "name"):
                    platform_name = metadata.name
                elif isinstance(metadata, dict) and "name" in metadata:
                    platform_name = metadata["name"]

                logger.info(
                    f"[群分析插件 BotManager] Initial platform_name detection: {platform_name}"
                )

                # 验证此平台名称是否受支持，如果不支持，尝试从bot实例检测（如果可用）
                if (
                    not platform_name
                    or not PlatformAdapterFactory.is_supported(str(platform_name))
                ) and bot_client:
                    detected = self._detect_platform_name(bot_client)
                    if detected:
                        platform_name = detected

                logger.debug(
                    f"发现平台: {platform_id} ({platform_name}), 客户端就绪: {bool(bot_client)}"
                )

                # 无论bot客户端状态如何，都存储平台实例
                self._platforms[platform_id] = platform

                if bot_client:
                    self.set_bot_instance(bot_client, platform_id, platform_name)
                    discovered[platform_id] = bot_client
                else:
                    logger.info(
                        f"发现平台 {platform_id} 但客户端未就绪。将进行懒加载。"
                    )
                    discovered[platform_id] = platform
            else:
                # 后备方案：如果元数据丢失/损坏但我们有客户端，尝试使用它
                if bot_client:
                    platform_name = self._detect_platform_name(bot_client)
                    if platform_name:
                        # 生成临时ID或使用名称
                        platform_id = platform_name
                        logger.warning(
                            f"平台元数据丢失，使用检测到的类型 '{platform_name}' 作为 ID。"
                        )

                        self._platforms[platform_id] = platform
                        self.set_bot_instance(bot_client, platform_id, platform_name)
                        discovered[platform_id] = bot_client

        # 记录适配器创建结果
        if self._adapters:
            logger.info(
                f"已创建 {len(self._adapters)} 个 PlatformAdapter: "
                f"{list(self._adapters.keys())}"
            )

        return discovered

    async def initialize_from_config(self):
        """从配置初始化bot管理器"""
        # 设置配置的bot ID 列表
        bot_self_ids = self.config_manager.get_bot_self_ids()
        if bot_self_ids:
            self.set_bot_self_ids(bot_self_ids)

        # 自动发现所有bot实例
        discovered = await self.auto_discover_bot_instances()
        self._is_initialized = True

        # 返回发现的实例字典
        return discovered

    def get_status_info(self) -> dict[str, Any]:
        """获取bot管理器状态信息"""
        adapter_info = {}
        for pid, adapter in self._adapters.items():
            caps = adapter.get_capabilities()
            adapter_info[pid] = {
                "platform_name": caps.platform_name,
                "can_analyze": caps.can_analyze(),
                "supports_image": caps.supports_image_message,
            }

        return {
            "has_bot_instance": self.has_bot_instance(),
            "has_bot_qq_id": self.has_bot_self_id(),
            "bot_qq_ids": self._bot_self_ids,
            "bot_self_ids": self._bot_self_ids,
            "platform_count": len(self._bot_instances),
            "platforms": list(self._bot_instances.keys()),
            "adapters": adapter_info,  # DDD 集成信息
            "ready_for_auto_analysis": self.is_ready_for_auto_analysis(),
        }

    def update_from_event(self, event):
        """从事件更新bot实例（用于手动命令）"""
        # 检查是否为 QQ 平台事件 (兼容性检查)
        # 注意: 非 aiocqhttp 平台也可以使用，只要适配器已注册

        if hasattr(event, "bot") and event.bot:
            # 从事件中获取平台ID
            platform_id = None
            if hasattr(event, "platform") and isinstance(event.platform, str):
                platform_id = event.platform
            elif hasattr(event, "metadata") and hasattr(event.metadata, "id"):
                platform_id = event.metadata.id

            self.set_bot_instance(event.bot, platform_id)
            # 每次都尝试从bot实例提取ID
            bot_self_id = self._extract_bot_self_id(event.bot)
            if bot_self_id:
                # 将单个ID转换为列表，保持统一处理
                self.set_bot_self_ids([bot_self_id])
            else:
                # 如果bot实例没有ID，尝试使用配置的ID列表
                config_self_ids = self.config_manager.get_bot_self_ids()
                if config_self_ids:
                    self.set_bot_self_ids(config_self_ids)
            return True
        return False

    def _extract_bot_self_id(self, bot_instance):
        """从bot实例中提取自身ID（单个）"""
        return self._extract_bot_self_id_impl(bot_instance)

    def _extract_bot_self_id_impl(self, bot_instance):
        """从bot实例中提取ID（通用实现）"""
        # 尝试多种方式获取bot ID
        if hasattr(bot_instance, "self_id") and bot_instance.self_id:
            return str(bot_instance.self_id)
        elif hasattr(bot_instance, "qq") and bot_instance.qq:
            return str(bot_instance.qq)
        elif hasattr(bot_instance, "user_id") and bot_instance.user_id:
            return str(bot_instance.user_id)
        # Discord.py style: client.user.id
        elif hasattr(bot_instance, "user") and hasattr(bot_instance.user, "id"):
            return str(bot_instance.user.id)
        return None

    def _extract_bot_qq_id(self, bot_instance):
        """从bot实例中提取QQ号（兼容旧方法名称）"""
        return self._extract_bot_self_id_impl(bot_instance)

    def validate_for_message_fetching(self, group_id: str) -> bool:
        """验证是否可以进行消息获取"""
        return self.has_bot_instance() and bool(group_id)

    def should_filter_bot_message(self, sender_id: str) -> bool:
        """判断是否应该过滤bot自己的消息（支持多个ID）"""
        if not self._bot_self_ids:
            return False

        sender_id_str = str(sender_id)
        # 检查是否在ID列表中
        return sender_id_str in self._bot_self_ids

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
