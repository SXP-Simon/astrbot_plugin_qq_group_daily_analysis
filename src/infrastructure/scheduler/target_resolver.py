"""
计划分析目标解析器 (Scheduled Target Resolver)

负责跨平台群组自动发现、群组所属平台实例精准探测、以及分层名单规则（准入层、定时层、增量层）的匹配解析。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...shared.constants import PLUGIN_NAME
from ...utils.logger import logger
from ..platform.factory import PlatformAdapterFactory

if TYPE_CHECKING:
    from ..config.config_manager import ConfigManager
    from ..platform.bot_manager import BotManager


class ScheduledTargetResolver:
    """计划分析目标解析与群平台嗅探器。"""

    def __init__(self, config_manager: ConfigManager, bot_manager: BotManager):
        """初始化目标解析器。

        Args:
            config_manager: 配置管理器。
            bot_manager: 机器人平台管理器。
        """
        self.config_manager = config_manager
        self.bot_manager = bot_manager
        self._group_name_cache: dict[str, str] = {}

    async def get_platform_id_for_group(self, group_id: str | int) -> str | None:
        """根据群ID获取对应的平台ID（精准验证）。

        Args:
            group_id: 群聊 ID。

        Returns:
            str | None: 匹配的平台实例 ID，未找到返回 None。
        """
        try:
            adapters = (
                self.bot_manager.get_all_adapters()
                if hasattr(self.bot_manager, "get_all_adapters")
                else {}
            )
            if not adapters:
                logger.error("❌ 没有注册的平台适配器")
                return None

            logger.info(
                f"正在验证群 {group_id} 属于哪个平台 (已注册适配器: {list(adapters.keys())})..."
            )
            for platform_id, adapter in adapters.items():
                try:
                    if not self.bot_manager.is_plugin_enabled(
                        str(platform_id), PLUGIN_NAME, group_id=str(group_id)
                    ):
                        logger.debug(
                            f"平台 {platform_id} 对应的配置文件未启用插件，跳过群 {group_id} 探测"
                        )
                        continue
                    if adapter:
                        info = await adapter.get_group_info(str(group_id))
                        if info:
                            actual_pid = self.bot_manager.get_adapter_platform_id(
                                adapter
                            ) or str(platform_id)
                            logger.info(f"✅ 群 {group_id} 属于平台 {actual_pid}")
                            return actual_pid
                        logger.debug(f"平台 {platform_id} 无法获取群 {group_id} 信息")
                except Exception as e:
                    logger.debug(f"平台 {platform_id} 验证群 {group_id} 失败: {e}")
                    continue

            logger.error(
                f"❌ 无法确定群 {group_id} 属于哪个平台 (已尝试适配器: {list(adapters.keys())})"
            )
            return None
        except Exception as e:
            logger.error(f"❌ 获取平台ID失败: {e}")
            return None

    async def get_group_name_safe(
        self, group_id: str, platform_id: str | None = None
    ) -> str:
        """为 TraceID 生成解析可读的群名（带缓存机制）。

        Args:
            group_id: 群聊 ID。
            platform_id: 所属平台 ID（可选）。

        Returns:
            str: 群名称或回退的 group_id。
        """
        if group_id in self._group_name_cache:
            return self._group_name_cache[group_id]

        try:
            pid = platform_id or await self.get_platform_id_for_group(group_id)
            if pid:
                adapter = self.bot_manager.get_adapter(pid)
                if adapter:
                    info = await adapter.get_group_info(group_id)
                    if info and info.group_name:
                        self._group_name_cache[group_id] = info.group_name
                        return info.group_name
        except Exception:
            pass

        return group_id

    async def get_scheduled_targets(
        self, mode_filter: str | None = None
    ) -> list[tuple[str, str, str]]:
        """根据分层过滤逻辑判定所有应参与计划分析的目标群组及其分析策略。

        判定过程：
        1. 准入层：群组必须在基础设置的允许名单内。
        2. 定时层：群组需通过定时分析名单的过滤。
        3. 模式层：如果群组在增量名单内，则使用增量模式，否则使用传统模式。

        Args:
            mode_filter: 可选的模式过滤器 ('traditional' 或 'incremental')。

        Returns:
            list[tuple[str, str, str]]: [(group_id, platform_id, effective_mode), ...]
        """
        all_groups = await self.get_all_groups()
        result: list[tuple[str, str, str]] = []
        seen_targets: set[tuple[str, str, str]] = set()

        for platform_id, group_id_orig in all_groups:
            group_id = str(group_id_orig)
            umo = f"{platform_id}:GroupMessage:{group_id}"

            # 检查该群聊所属的会话/配置文件是否启用了本插件
            if not self.bot_manager.is_plugin_enabled(
                platform_id, PLUGIN_NAME, group_id=group_id
            ):
                logger.debug(
                    f"[调度决策] 群聊 {umo} 所在 AstrBot 配置文件未启用此插件，跳过计划分析"
                )
                continue

            # 配置管理器统一处理基础名单与定时 inherit/白黑名单
            if not self.config_manager.is_scheduled_group_allowed(umo):
                logger.debug(
                    f"[调度决策] 群聊 {umo} 未通过定时分析名单过滤 (scheduled_groups)，跳过计划分析"
                )
                continue

            # 配置管理器统一处理增量 inherit/白黑名单
            if self.config_manager.is_incremental_group_allowed(umo):
                effective_mode = "incremental"
            else:
                effective_mode = "traditional"

            if mode_filter and effective_mode != mode_filter:
                logger.debug(
                    f"[调度决策] 群聊 {umo} (模式: {effective_mode}) 与当前执行的模式过滤 '{mode_filter}' 不符，跳过"
                )
                continue

            logger.debug(
                f"[调度决策] 群聊 {umo} 准入通过，决议执行模式: {effective_mode}"
            )
            target_key = (group_id, platform_id, effective_mode)
            if target_key not in seen_targets:
                seen_targets.add(target_key)
                result.append(target_key)

        logger.info(
            f"分层调度解析完成：符合条件的群组共 {len(result)} 个"
            + (f" (模式过滤: {mode_filter})" if mode_filter else "")
        )
        return result

    async def get_all_groups(self) -> list[tuple[str, str]]:
        """获取所有 Bot 实例所在的所有群聊列表。

        Returns:
            list[tuple[str, str]]: [(platform_id, group_id), ...]
        """
        all_groups: set[tuple[str, str]] = set()

        # 韧性发现平台实例
        if hasattr(self.bot_manager, "auto_discover_bot_instances"):
            try:
                await self.bot_manager.auto_discover_bot_instances()
            except Exception as e:
                logger.warning(f"[AutoScheduler] 周期性扫描中的平台发现失败: {e}")

        bot_instances = self.bot_manager.get_all_bot_instances()
        bot_ids = list(bot_instances.keys())

        if not bot_ids:
            logger.warning(
                "[AutoScheduler] 分析周期开启，但全局未发现任何在线 Bot。任务将跳过。"
            )
            return []

        logger.info(f"[AutoScheduler] 正在扫描 {len(bot_ids)} 个平台的群聊资源...")

        for platform_id, bot_instance in bot_instances.items():
            try:
                adapter = self.bot_manager.get_adapter(platform_id)
                if not adapter:
                    platform_name = self.bot_manager._detect_platform_name(bot_instance)
                    if platform_name and PlatformAdapterFactory.is_supported(
                        platform_name
                    ):
                        adapter = PlatformAdapterFactory.create(
                            platform_name,
                            bot_instance,
                            config={
                                "bot_self_ids": (
                                    self.config_manager.get_bot_self_ids()
                                ),
                                "platform_id": str(platform_id),
                                # 兜底构造的适配器同样需要插件实例：Telegram 等平台
                                # 无法通过 API 列出群组，只能回查插件侧的群注册表。
                                "plugin_instance": self.bot_manager.plugin_instance,
                            },
                        )

                if adapter:
                    try:
                        actual_platform_id = self.bot_manager.get_adapter_platform_id(
                            adapter
                        ) or str(platform_id)
                        groups = await adapter.get_group_list()
                        groups = [
                            str(group_id).strip()
                            for group_id in groups
                            if str(group_id).strip()
                        ]

                        p_name = None
                        if hasattr(adapter, "get_platform_name"):
                            try:
                                p_name = adapter.get_platform_name()
                            except Exception:
                                p_name = None

                        enabled_count = 0
                        for group_id in groups:
                            if self.bot_manager.is_plugin_enabled(
                                actual_platform_id, PLUGIN_NAME, group_id=group_id
                            ):
                                all_groups.add((actual_platform_id, str(group_id)))
                                enabled_count += 1
                            else:
                                logger.debug(
                                    f"群组 {actual_platform_id}:{group_id} 所在 AstrBot 配置文件未启用插件 {PLUGIN_NAME}，跳过"
                                )

                        logger.info(
                            f"平台 {actual_platform_id} ({p_name or 'unknown'}) 扫描到 {len(groups)} 个群组 (启用插件: {enabled_count} 个)"
                        )
                        continue

                    except Exception as e:
                        logger.warning(f"适配器 {platform_id} 获取群列表失败: {e}")

                logger.debug(f"平台 {platform_id} 无匹配适配器，跳过获取群列表")

            except Exception as e:
                logger.error(f"平台 {platform_id} 获取群列表异常: {e}")

        return list(all_groups)
