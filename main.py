"""
QQ群日常分析插件
基于群聊记录生成精美的日常分析报告，包含话题总结、用户画像、统计数据等

重构版本 - 使用模块化架构，支持跨平台
"""

import asyncio
import os
import re
from collections import Counter
from datetime import datetime, timezone

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.event.filter import PermissionType
from astrbot.api.star import Context, Star
from astrbot.core.message.components import File

from .src.application.services.analysis_application_service import (
    AnalysisApplicationService,
)
from .src.domain.services.analysis_domain_service import AnalysisDomainService
from .src.domain.services.incremental_merge_service import IncrementalMergeService
from .src.domain.services.statistics_service import StatisticsService
from .src.infrastructure.analysis.llm_analyzer import LLMAnalyzer
from .src.infrastructure.config.config_manager import ConfigManager
from .src.infrastructure.persistence.history_manager import HistoryManager
from .src.infrastructure.persistence.incremental_store import IncrementalStore
from .src.infrastructure.platform.bot_manager import BotManager
from .src.infrastructure.reporting.generators import ReportGenerator
from .src.infrastructure.scheduler.auto_scheduler import AutoScheduler
from .src.infrastructure.scheduler.retry import RetryManager
from .src.utils.pdf_utils import PDFInstaller


class QQGroupDailyAnalysis(Star):
    """QQ群日常分析插件主类"""

    _TG_GROUP_REGISTRY_KV_KEY = "telegram_seen_groups_v1"

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 1. 基础设施层
        self.config_manager = ConfigManager(config)
        self.bot_manager = BotManager(self.config_manager)
        self.bot_manager.set_context(context)
        self.history_manager = HistoryManager(self)
        self.report_generator = ReportGenerator(self.config_manager)

        # 2. 领域层
        self.statistics_service = StatisticsService()
        self.analysis_domain_service = AnalysisDomainService()

        # 3. 分析核心 (LLM Bridge)
        self.llm_analyzer = LLMAnalyzer(context, self.config_manager)

        # 4. 增量分析组件
        self.incremental_store = IncrementalStore(self)
        self.incremental_merge_service = IncrementalMergeService()

        # 5. 应用层
        self.analysis_service = AnalysisApplicationService(
            self.config_manager,
            self.bot_manager,
            self.history_manager,
            self.report_generator,
            self.llm_analyzer,
            self.statistics_service,
            self.analysis_domain_service,
            incremental_store=self.incremental_store,
            incremental_merge_service=self.incremental_merge_service,
        )

        # 调度与重试
        self.retry_manager = RetryManager(
            self.bot_manager, self.html_render, self.report_generator
        )
        self.auto_scheduler = AutoScheduler(
            self.config_manager,
            self.analysis_service,
            self.bot_manager,
            self.retry_manager,
            self.report_generator,
            self.html_render,
            plugin_instance=self,
        )

        self._initialized = False
        self._tg_registry_lock: asyncio.Lock | None = None
        # 异步注册任务，处理插件重载情况
        asyncio.create_task(self._run_initialization("Plugin Reload/Init"))

    def _resolve_template_base_dir(self) -> str:
        """解析报告模板目录（兼容新旧目录结构）"""
        plugin_root = os.path.dirname(__file__)
        candidate_dirs = [
            os.path.join(
                plugin_root, "src", "infrastructure", "reporting", "templates"
            ),
            os.path.join(plugin_root, "src", "reports", "templates"),
        ]
        for candidate in candidate_dirs:
            if os.path.isdir(candidate):
                return candidate
        return candidate_dirs[0]

    def _resolve_template_preview_path(self, template_name: str) -> str | None:
        """解析模板预览图路径（兼容新旧命名和目录）"""
        plugin_root = os.path.dirname(__file__)
        template_base_dir = self._resolve_template_base_dir()
        candidate_paths = [
            os.path.join(plugin_root, "assets", f"{template_name}-demo.jpg"),
        ]
        for candidate in candidate_paths:
            if os.path.exists(candidate):
                return candidate
        return None

    # orchestrators 缓存已移至 应用层逻辑 (分析服务) 或 暂时移除以简化。
    # 如果需要高性能缓存，后续可由 AnalysisApplicationService 内部维护。

    @filter.on_platform_loaded()
    async def on_platform_loaded(self):
        """平台加载完成后初始化"""
        await self._run_initialization("Platform Loaded")

    async def _run_initialization(self, source: str):
        """统一初始化逻辑"""
        if self._initialized:
            return

        # 稍微延迟，确保 context 和环境稳定
        await asyncio.sleep(2)
        if self._initialized:  # Double check after sleep
            return

        try:
            logger.info(f"正在执行插件初始化 (来源: {source})...")
            # 检查插件是否被启用 (Fix for empty plugin_set issue)
            if self.context:
                config = self.context.get_config()
                # ... 为空修正逻辑保持不变 ...
                plugin_set = config.get("plugin_set", [])
                if (
                    isinstance(plugin_set, list)
                    and "astrbot_plugin_qq_group_daily_analysis" not in plugin_set
                ):
                    # 此时不强制修改 config，但可以记录日志
                    pass

            # 初始化所有bot实例
            discovered = await self.bot_manager.initialize_from_config()
            if discovered:
                logger.info("Bot管理器初始化成功")
                # 启动调度器
                self.auto_scheduler.schedule_jobs(self.context)
            else:
                logger.warning("Bot管理器初始化失败，未发现任何适配器")

            # 始终启动重试管理器
            await self.retry_manager.start()

            self._initialized = True
            logger.info("插件任务注册完成")

        except Exception as e:
            logger.error(f"插件初始化失败: {e}", exc_info=True)

    async def terminate(self):
        """插件被卸载/停用时调用，清理资源"""
        try:
            logger.info("开始清理QQ群日常分析插件资源...")

            # 停止自动调度器
            if self.auto_scheduler:
                logger.info("正在停止自动调度器...")
                self.auto_scheduler.unschedule_jobs(self.context)
                logger.info("自动调度器已停止")

            if self.retry_manager:
                await self.retry_manager.stop()

            # 重置实例属性
            self.auto_scheduler = None
            self.bot_manager = None
            self.report_generator = None
            self.config_manager = None

            logger.info("QQ群日常分析插件资源清理完成")

        except Exception as e:
            logger.error(f"插件资源清理失败: {e}")

    # ==================== 消息历史存储（统一方法，可复用） ====================

    async def _store_message_to_history(self, event: AstrMessageEvent) -> None:
        """
        将消息存储到 AstrBot 的 message_history_manager

        这是一个可复用的统一方法，支持所有通过 context 机制存储消息的平台。
        不使用 fallback 值 - 如果获取不到必要数据会抛出异常。

        Args:
            event: AstrBot 消息事件

        Raises:
            ValueError: 当必要数据（group_id, sender_id, platform_id）无法获取时
            RuntimeError: 当消息内容为空时
        """
        # 1. 获取群组 ID（必需）
        group_id = self._get_group_id_from_event(event)
        if not group_id:
            raise ValueError("无法获取群组 ID，拒绝存储消息")

        # 2. 获取发送者 ID（必需）
        sender_id = event.get_sender_id()
        if not sender_id:
            raise ValueError(f"群 {group_id}: 无法获取发送者 ID，拒绝存储消息")
        sender_id = str(sender_id)

        # 3. 获取发送者名称（昵称优先，必要时回退）
        sender_name = self._resolve_sender_name(event, sender_id)

        # 4. 获取平台 ID（必需）
        platform_id = event.get_platform_id()
        if not platform_id:
            raise ValueError(f"群 {group_id}: 无法获取平台 ID，拒绝存储消息")

        # 5. 提取消息内容
        message_parts = self._extract_message_parts(event)
        if not message_parts:
            raise RuntimeError(
                f"群 {group_id}: 消息内容为空 (sender={sender_name})，拒绝存储"
            )

        # 6. 提取事件消息 ID（用于 Telegram 已见群/话题记录）
        msg_obj = getattr(event, "message_obj", None)
        event_message_id = str(getattr(msg_obj, "message_id", "") or "")

        # 7. 存储到数据库
        await self.context.message_history_manager.insert(
            platform_id=platform_id,
            user_id=group_id,
            content={"type": "user", "message": message_parts},
            sender_id=sender_id,
            sender_name=sender_name,
        )

        # Telegram: 记录已见群/话题，用于自动分析拉群回退
        if self._is_telegram_event(event, platform_id):
            try:
                await self._upsert_telegram_group_registry(
                    platform_id=platform_id,
                    group_id=group_id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    event_message_id=event_message_id,
                )
            except Exception as e:
                logger.warning(
                    "[TGRegistry] Upsert failed: "
                    f"platform_id={platform_id} group_id={group_id} error={e}"
                )

        logger.debug(
            f"[{platform_id}] 已缓存群 {group_id} 的消息 (发送者: {sender_name})"
        )

    @staticmethod
    def _is_telegram_event(event: AstrMessageEvent, platform_id: str) -> bool:
        """判断当前事件是否为 Telegram 平台。"""
        platform_name = str(event.get_platform_name() or "").strip().lower()
        if platform_name == "telegram":
            return True
        return str(platform_id or "").strip().lower().startswith("telegram")

    def _get_tg_registry_lock(self) -> asyncio.Lock:
        """懒加载 Telegram 群/话题注册表锁，避免并发读改写覆盖。"""
        if self._tg_registry_lock is None:
            self._tg_registry_lock = asyncio.Lock()
        return self._tg_registry_lock

    async def _upsert_telegram_group_registry(
        self,
        platform_id: str,
        group_id: str,
        sender_id: str,
        sender_name: str,
        event_message_id: str,
    ) -> None:
        """更新 Telegram 已见群/话题注册表（KV）。"""
        lock = self._get_tg_registry_lock()
        async with lock:
            registry = await self.get_kv_data(self._TG_GROUP_REGISTRY_KV_KEY, {})
            if not isinstance(registry, dict):
                registry = {}

            platforms = registry.get("platforms")
            if not isinstance(platforms, dict):
                platforms = {}
                registry["platforms"] = platforms

            platform_key = str(platform_id).strip()
            group_key = str(group_id).strip()

            platform_map = platforms.get(platform_key)
            if not isinstance(platform_map, dict):
                platform_map = {}
                platforms[platform_key] = platform_map

            now_iso = datetime.now(timezone.utc).isoformat()

            entry = platform_map.get(group_key)
            if not isinstance(entry, dict):
                entry = {}

            first_seen = entry.get("first_seen")
            if not isinstance(first_seen, str) or not first_seen:
                first_seen = now_iso

            entry.update(
                {
                    "first_seen": first_seen,
                    "last_seen": now_iso,
                    "last_sender_id": str(sender_id),
                    "last_sender_name": str(sender_name),
                    "last_event_message_id": str(event_message_id),
                }
            )
            platform_map[group_key] = entry

            registry["updated_at"] = now_iso
            await self.put_kv_data(self._TG_GROUP_REGISTRY_KV_KEY, registry)

    async def get_telegram_seen_group_ids(
        self, platform_id: str | None = None
    ) -> list[str]:
        """读取 Telegram 已见群/话题列表（给调度器回退使用）。"""
        lock = self._get_tg_registry_lock()
        async with lock:
            registry = await self.get_kv_data(self._TG_GROUP_REGISTRY_KV_KEY, {})
            if not isinstance(registry, dict):
                return []

            platforms = registry.get("platforms")
            if not isinstance(platforms, dict):
                return []

            groups: set[str] = set()
            if platform_id:
                platform_map = platforms.get(str(platform_id).strip(), {})
                if isinstance(platform_map, dict):
                    groups.update(
                        str(gid).strip()
                        for gid in platform_map.keys()
                        if str(gid).strip()
                    )
            else:
                for platform_map in platforms.values():
                    if not isinstance(platform_map, dict):
                        continue
                    groups.update(
                        str(gid).strip()
                        for gid in platform_map.keys()
                        if str(gid).strip()
                    )

            return sorted(groups)

    @staticmethod
    def _is_placeholder_sender_name(name: str | None, sender_id: str) -> bool:
        """判断 sender_name 是否为空或占位值。"""
        if not name:
            return True
        normalized = str(name).strip()
        if not normalized:
            return True
        if normalized.lower() in {"unknown", "none", "null", "nil", "undefined"}:
            return True
        return normalized == str(sender_id).strip()

    def _resolve_sender_name(self, event: AstrMessageEvent, sender_id: str) -> str:
        """
        解析发送者展示名。

        优先级：
        - Telegram:
          1. raw_message.from_user.full_name
          2. raw_message.from_user.first_name
          3. event.get_sender_name() / message_obj.sender.nickname
          4. raw_message.from_user.username
          5. sender_id
        - 其他平台：
          1. event.get_sender_name()
          2. message_obj.sender.nickname
          3. raw_message.from_user.full_name / first_name / username
          4. sender_id（最终回退，避免消息丢失）
        """
        platform_name = str(event.get_platform_name() or "").lower()
        candidates: list[str | None] = []

        msg_obj = getattr(event, "message_obj", None)
        sender_obj = getattr(msg_obj, "sender", None)
        raw_message = getattr(msg_obj, "raw_message", None)
        raw_msg_obj = getattr(raw_message, "message", raw_message)
        from_user = getattr(raw_msg_obj, "from_user", None)

        # Telegram 特殊策略：优先显示名，不优先 username
        if platform_name == "telegram":
            if from_user is not None:
                candidates.extend(
                    [
                        getattr(from_user, "full_name", None),
                        getattr(from_user, "first_name", None),
                    ]
                )

            candidates.append(event.get_sender_name())
            if sender_obj is not None:
                candidates.append(getattr(sender_obj, "nickname", None))

            if from_user is not None:
                candidates.append(getattr(from_user, "username", None))
        else:
            candidates.append(event.get_sender_name())
            if sender_obj is not None:
                candidates.append(getattr(sender_obj, "nickname", None))

        if from_user is not None:
            candidates.extend(
                [
                    getattr(from_user, "full_name", None),
                    getattr(from_user, "first_name", None),
                    getattr(from_user, "username", None),
                ]
            )

        for candidate in candidates:
            name = str(candidate or "").strip()
            if not self._is_placeholder_sender_name(name, sender_id):
                return name

        logger.warning(
            f"[HistoryStore] 无法解析昵称，回退为 sender_id: {sender_id} "
            f"(platform={event.get_platform_id()})"
        )
        return sender_id

    def _extract_message_parts(self, event: AstrMessageEvent) -> list[dict]:
        """
        从事件中提取消息内容

        Returns:
            消息部分列表，格式为 [{"type": "plain", "text": "..."}, ...]
        """
        message_parts = []
        message = event.message_obj

        # 先收集 @ 标记，后续用于从 plain 文本中去重
        pending_mentions: Counter[str] = Counter()
        if message and hasattr(message, "message"):
            for seg in message.message:
                if not hasattr(seg, "type"):
                    continue
                if seg.type not in ("At", "at"):
                    continue

                target = getattr(seg, "target", None)
                if target is None:
                    target = getattr(seg, "qq", None)
                if target is None and hasattr(seg, "data"):
                    target = seg.data.get("qq") or seg.data.get("target")

                target_str = str(target or "").strip()
                if target_str:
                    pending_mentions[target_str] += 1

                display_name = str(getattr(seg, "name", "") or "").strip()
                if display_name and display_name != target_str:
                    pending_mentions[display_name] += 1

        if message and hasattr(message, "message"):
            for seg in message.message:
                if not hasattr(seg, "type"):
                    continue

                seg_type = seg.type
                if seg_type in ("Plain", "text"):
                    text = getattr(seg, "text", None)
                    if text is None and hasattr(seg, "data"):
                        text = seg.data.get("text")
                    if text:
                        text = self._strip_known_mentions(text, pending_mentions)
                        message_parts.append({"type": "plain", "text": text})

                elif seg_type in ("Image", "image"):
                    url = getattr(seg, "url", None)
                    if url is None and hasattr(seg, "data"):
                        url = seg.data.get("url")
                    if url:
                        message_parts.append({"type": "image", "url": url})

                elif seg_type in ("At", "at"):
                    target = getattr(seg, "target", None)
                    if target is None:
                        target = getattr(seg, "qq", None)
                    if target is None and hasattr(seg, "data"):
                        target = seg.data.get("qq") or seg.data.get("target")
                    if target:
                        message_parts.append(
                            {
                                "type": "at",
                                "target_id": str(target),
                                "name": str(getattr(seg, "name", "") or ""),
                            }
                        )

        # 如果没有从消息链提取到内容，尝试使用 message_str
        if not message_parts and event.message_str:
            message_parts.append({"type": "plain", "text": event.message_str})

        # 清理空文本段，避免出现仅空格文本
        message_parts = [
            part
            for part in message_parts
            if not (
                part.get("type") == "plain" and not str(part.get("text", "")).strip()
            )
        ]

        return message_parts

    @staticmethod
    def _strip_known_mentions(text: str, pending_mentions: Counter[str]) -> str:
        """
        从文本中移除已识别的 @ 提及，避免与结构化 at 段重复。
        """
        cleaned = str(text)
        if not cleaned or not pending_mentions:
            return cleaned.strip()

        for mention, remaining in list(pending_mentions.items()):
            if not mention or remaining <= 0:
                continue

            pattern = re.compile(rf"(?<!\w)@{re.escape(mention)}(?!\w)")
            removed = 0
            while removed < remaining:
                cleaned, subn = pattern.subn("", cleaned, count=1)
                if subn == 0:
                    break
                removed += 1

            if removed > 0:
                pending_mentions[mention] -= removed
                if pending_mentions[mention] <= 0:
                    pending_mentions.pop(mention, None)

        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        return cleaned

    # ==================== Telegram 消息拦截器 ====================

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    @filter.platform_adapter_type(filter.PlatformAdapterType.TELEGRAM)
    async def intercept_telegram_messages(self, event: AstrMessageEvent):
        """
        拦截 Telegram 群消息并存储到数据库

        使用统一的 _store_message_to_history 方法存储消息。
        """
        try:
            await self._store_message_to_history(event)
        except (ValueError, RuntimeError) as e:
            logger.warning(f"[Telegram] 消息存储失败: {e}")
        except Exception as e:
            logger.error(f"[Telegram] 消息存储异常: {e}", exc_info=True)

    @filter.command("群分析", alias={"group_analysis"})
    @filter.permission_type(PermissionType.ADMIN)
    async def analyze_group_daily(
        self, event: AstrMessageEvent, days: int | None = None
    ):
        """
        分析群聊日常活动（跨平台支持）
        用法: /群分析 [天数]
        """
        group_id = self._get_group_id_from_event(event)
        platform_id = self._get_platform_id_from_event(event)

        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        # 更新bot实例
        self.bot_manager.update_from_event(event)

        # 优先使用 UMO 进行权限检查 (兼容白名单 UMO 格式)
        check_target = getattr(event, "unified_msg_origin", None)
        if not check_target:
            check_target = f"{platform_id}:GroupMessage:{group_id}"

        if not self.config_manager.is_group_allowed(check_target):
            # Fallback checks (simple ID) are handled inside is_group_allowed logic if list item has no colon
            # But if list item HAS colon, we need precise match.
            # If prompt fails, try simple ID as fallback for permissive cases?
            # No, config_manager.is_group_allowed already handles simple ID matching if whitelist item is simple ID.
            yield event.plain_result("❌ 此群未启用日常分析功能")
            return

        yield event.plain_result("🔍 正在启动跨平台分析引擎，正在拉取最近消息...")

        try:
            # 调用 DDD 应用级服务
            result = await self.analysis_service.execute_daily_analysis(
                group_id=group_id, platform_id=platform_id, manual=True
            )

            if not result.get("success"):
                reason = result.get("reason")
                if reason == "no_messages":
                    yield event.plain_result("❌ 未找到足够的群聊记录")
                else:
                    yield event.plain_result("❌ 分析失败，原因未知")
                return

            yield event.plain_result(
                f"📊 已获取{result['messages_count']}条消息，正在生成渲染报告..."
            )

            analysis_result = result["analysis_result"]
            adapter = result["adapter"]
            output_format = self.config_manager.get_output_format()

            # 定义头像获取回调 (Infrastructure delegate)
            async def avatar_getter(user_id: str) -> str | None:
                return await adapter.get_user_avatar_url(user_id)

            # 定义昵称获取回调
            async def nickname_getter(user_id: str) -> str | None:
                try:
                    member = await adapter.get_member_info(group_id, user_id)
                    if member:
                        return member.card or member.nickname
                except Exception:
                    pass
                return None

            if output_format == "image":
                (
                    image_url,
                    html_content,
                ) = await self.report_generator.generate_image_report(
                    analysis_result,
                    group_id,
                    self.html_render,
                    avatar_getter=avatar_getter,
                    nickname_getter=nickname_getter,
                )

                if image_url:
                    if not await adapter.send_image(group_id, image_url):
                        yield event.image_result(image_url)
                elif html_content:
                    yield event.plain_result("⚠️ 图片生成暂不可用，已尝试加入队列。")
                    await self.retry_manager.add_task(
                        html_content, analysis_result, group_id, platform_id
                    )
                else:
                    text_report = self.report_generator.generate_text_report(
                        analysis_result
                    )
                    yield event.plain_result(
                        f"⚠️ 图片生成失败，回退文本：\n\n{text_report}"
                    )

            elif output_format == "pdf":
                pdf_path = await self.report_generator.generate_pdf_report(
                    analysis_result,
                    group_id,
                    avatar_getter=avatar_getter,
                    nickname_getter=nickname_getter,
                )
                if pdf_path:
                    if not await adapter.send_file(group_id, pdf_path):
                        from pathlib import Path

                        yield event.chain_result(
                            [File(name=Path(pdf_path).name, file=pdf_path)]
                        )
                else:
                    yield event.plain_result("⚠️ PDF 生成失败。")

            else:
                text_report = self.report_generator.generate_text_report(
                    analysis_result
                )
                if not await adapter.send_text(group_id, text_report):
                    yield event.plain_result(text_report)

        except Exception as e:
            logger.error(f"群分析失败: {e}", exc_info=True)
            yield event.plain_result(
                f"❌ 分析失败: {str(e)}。请检查网络连接和LLM配置，或联系管理员"
            )

    @filter.command("设置格式", alias={"set_format"})
    @filter.permission_type(PermissionType.ADMIN)
    async def set_output_format(self, event: AstrMessageEvent, format_type: str = ""):
        """
        设置分析报告输出格式（跨平台支持）
        用法: /设置格式 [image|text|pdf]
        """
        group_id = self._get_group_id_from_event(event)

        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        if not format_type:
            current_format = self.config_manager.get_output_format()
            pdf_status = (
                "✅"
                if self.config_manager.playwright_available
                else "❌ (需安装 Playwright)"
            )
            yield event.plain_result(f"""📊 当前输出格式: {current_format}

可用格式:
• image - 图片格式 (默认)
• text - 文本格式
• pdf - PDF 格式 {pdf_status}

用法: /设置格式 [格式名称]""")
            return

        format_type = format_type.lower()
        if format_type not in ["image", "text", "pdf"]:
            yield event.plain_result("❌ 无效的格式类型，支持: image, text, pdf")
            return

        if format_type == "pdf" and not self.config_manager.playwright_available:
            yield event.plain_result("❌ PDF 格式不可用，请使用 /安装PDF 命令安装依赖")
            return

        self.config_manager.set_output_format(format_type)
        yield event.plain_result(f"✅ 输出格式已设置为: {format_type}")

    @filter.command("设置模板", alias={"set_template"})
    @filter.permission_type(PermissionType.ADMIN)
    async def set_report_template(
        self, event: AstrMessageEvent, template_input: str = ""
    ):
        """
        设置分析报告模板（跨平台支持）
        用法: /设置模板 [模板名称或序号]
        """
        # 获取模板目录和可用模板列表
        template_base_dir = self._resolve_template_base_dir()

        def _list_templates_sync():
            if os.path.exists(template_base_dir):
                return sorted(
                    [
                        d
                        for d in os.listdir(template_base_dir)
                        if os.path.isdir(os.path.join(template_base_dir, d))
                        and not d.startswith("__")
                    ]
                )
            return []

        available_templates = await asyncio.to_thread(_list_templates_sync)

        if not template_input:
            current_template = self.config_manager.get_report_template()
            template_list_str = "\n".join(
                [f"【{i}】{t}" for i, t in enumerate(available_templates, start=1)]
            )
            yield event.plain_result(f"""🎨 当前报告模板: {current_template}

可用模板:
{template_list_str}

用法: /设置模板 [模板名称或序号]
💡 使用 /查看模板 查看预览图""")
            return

        # 判断输入是序号还是模板名称
        template_name = template_input
        if template_input.isdigit():
            index = int(template_input)
            if 1 <= index <= len(available_templates):
                template_name = available_templates[index - 1]
            else:
                yield event.plain_result(
                    f"❌ 无效的序号 '{template_input}'，有效范围: 1-{len(available_templates)}"
                )
                return

        # 检查模板是否存在
        template_dir = os.path.join(template_base_dir, template_name)
        template_exists = await asyncio.to_thread(os.path.exists, template_dir)
        if not template_exists:
            yield event.plain_result(f"❌ 模板 '{template_name}' 不存在")
            return

        self.config_manager.set_report_template(template_name)
        yield event.plain_result(f"✅ 报告模板已设置为: {template_name}")

    @filter.command("查看模板", alias={"view_templates"})
    @filter.permission_type(PermissionType.ADMIN)
    async def view_templates(self, event: AstrMessageEvent):
        """
        查看所有可用的报告模板及预览图（跨平台支持）
        用法: /查看模板
        """
        from astrbot.api.message_components import Image, Node, Nodes, Plain

        # 获取模板目录
        template_dir = self._resolve_template_base_dir()

        def _list_templates_sync():
            if os.path.exists(template_dir):
                return sorted(
                    [
                        d
                        for d in os.listdir(template_dir)
                        if os.path.isdir(os.path.join(template_dir, d))
                        and not d.startswith("__")
                    ]
                )
            return []

        available_templates = await asyncio.to_thread(_list_templates_sync)

        if not available_templates:
            yield event.plain_result("❌ 未找到任何可用的报告模板")
            return

        current_template = self.config_manager.get_report_template()

        # 获取机器人信息用于合并转发消息
        bot_id = event.get_self_id()
        bot_name = "模板预览"

        # 圆圈数字序号
        circle_numbers = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]

        # 构建合并转发消息节点列表
        node_list = []

        # 添加标题节点
        header_content = [
            Plain(
                f"🎨 可用报告模板列表\n📌 当前使用: {current_template}\n💡 使用 /设置模板 [序号] 切换"
            )
        ]
        node_list.append(Node(uin=bot_id, name=bot_name, content=header_content))

        # 为每个模板创建一个节点
        for index, template_name in enumerate(available_templates):
            current_mark = " ✅" if template_name == current_template else ""
            num_label = (
                circle_numbers[index]
                if index < len(circle_numbers)
                else f"({index + 1})"
            )

            node_content = [Plain(f"{num_label} {template_name}{current_mark}")]

            # 添加预览图
            preview_image_path = self._resolve_template_preview_path(template_name)
            if preview_image_path:
                node_content.append(Image.fromFileSystem(preview_image_path))

            node_list.append(Node(uin=bot_id, name=template_name, content=node_content))

        # 使用 Nodes 包装成一个合并转发消息
        yield event.chain_result([Nodes(node_list)])

    @filter.command("安装PDF", alias={"install_pdf"})
    @filter.permission_type(PermissionType.ADMIN)
    async def install_pdf_deps(self, event: AstrMessageEvent):
        """
        安装 PDF 功能依赖（跨平台支持）
        用法: /安装PDF
        """
        yield event.plain_result("🔄 开始安装 PDF 功能依赖，请稍候...")

        try:
            result = await PDFInstaller.install_playwright(self.config_manager)
            yield event.plain_result(result)

        except Exception as e:
            logger.error(f"安装 PDF 依赖失败: {e}", exc_info=True)
            yield event.plain_result(f"❌ 安装过程中出现错误: {str(e)}")

    @filter.command("分析设置", alias={"analysis_settings"})
    @filter.permission_type(PermissionType.ADMIN)
    async def analysis_settings(self, event: AstrMessageEvent, action: str = "status"):
        """
        管理分析设置（跨平台支持）
        用法: /分析设置 [enable|disable|status|reload|test]
        - enable: 启用当前群的分析功能
        - disable: 禁用当前群的分析功能
        - status: 查看当前状态
        - reload: 重新加载配置并重启定时任务
        - test: 测试自动分析功能
        - incremental_debug: 切换增量分析立即报告模式（调试用）
        """
        group_id = self._get_group_id_from_event(event)

        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        elif action == "enable":
            mode = self.config_manager.get_group_list_mode()
            target_id = event.unified_msg_origin or group_id  # 优先使用 UMO

            if mode == "whitelist":
                glist = self.config_manager.get_group_list()
                # 检查 UMO 或 Group ID 是否已在列表中
                if not self.config_manager.is_group_allowed(target_id):
                    glist.append(target_id)
                    self.config_manager.set_group_list(glist)
                    yield event.plain_result(
                        f"✅ 已将当前群加入白名单\nID: {target_id}"
                    )
                    self.auto_scheduler.schedule_jobs(self.context)
                else:
                    yield event.plain_result("ℹ️ 当前群已在白名单中")
            elif mode == "blacklist":
                glist = self.config_manager.get_group_list()

                # 尝试移除 UMO 和 Group ID
                removed = False
                if target_id in glist:
                    glist.remove(target_id)
                    removed = True
                if group_id in glist:
                    glist.remove(group_id)
                    removed = True

                if removed:
                    self.config_manager.set_group_list(glist)
                    yield event.plain_result("✅ 已将当前群从黑名单移除")
                    self.auto_scheduler.schedule_jobs(self.context)
                else:
                    yield event.plain_result("ℹ️ 当前群不在黑名单中")
            else:
                yield event.plain_result("ℹ️ 当前为无限制模式，所有群聊默认启用")

        elif action == "disable":
            mode = self.config_manager.get_group_list_mode()
            target_id = event.unified_msg_origin or group_id  # 优先使用 UMO

            if mode == "whitelist":
                glist = self.config_manager.get_group_list()

                # 尝试移除 UMO 和 Group ID
                removed = False
                if target_id in glist:
                    glist.remove(target_id)
                    removed = True
                if group_id in glist:
                    glist.remove(group_id)
                    removed = True

                if removed:
                    self.config_manager.set_group_list(glist)
                    yield event.plain_result("✅ 已将当前群从白名单移除")
                    self.auto_scheduler.schedule_jobs(self.context)
                else:
                    yield event.plain_result("ℹ️ 当前群不在白名单中")
            elif mode == "blacklist":
                glist = self.config_manager.get_group_list()
                # 检查 UMO 或 Group ID 是否已在列表中
                if self.config_manager.is_group_allowed(
                    target_id
                ):  # 如果允许，说明不在黑名单
                    glist.append(target_id)
                    self.config_manager.set_group_list(glist)
                    yield event.plain_result(
                        f"✅ 已将当前群加入黑名单\nID: {target_id}"
                    )
                    self.auto_scheduler.schedule_jobs(self.context)
                else:
                    yield event.plain_result("ℹ️ 当前群已在黑名单中")
            else:
                yield event.plain_result(
                    "ℹ️ 当前为无限制模式，如需禁用请切换到黑名单模式"
                )

        elif action == "reload":
            self.auto_scheduler.schedule_jobs(self.context)
            yield event.plain_result("✅ 已重新加载配置并重启定时任务")

        elif action == "test":
            check_target = getattr(event, "unified_msg_origin", None)
            if not check_target:
                check_target = (
                    f"{self._get_platform_id_from_event(event)}:GroupMessage:{group_id}"
                )

            if not self.config_manager.is_group_allowed(check_target):
                yield event.plain_result("❌ 请先启用当前群的分析功能")
                return

            yield event.plain_result("🧪 开始测试自动分析功能...")

            # 更新bot实例（用于测试）
            self.bot_manager.update_from_event(event)

            try:
                await self.auto_scheduler._perform_auto_analysis_for_group(group_id)
                yield event.plain_result("✅ 自动分析测试完成，请查看群消息")
            except Exception as e:
                yield event.plain_result(f"❌ 自动分析测试失败: {str(e)}")

        elif action == "incremental_debug":
            current_state = self.config_manager.get_incremental_report_immediately()
            new_state = not current_state
            self.config_manager.set_incremental_report_immediately(new_state)
            status_text = "已启用" if new_state else "已禁用"
            yield event.plain_result(f"✅ 增量分析立即报告模式: {status_text}")

        else:  # status
            check_target = getattr(event, "unified_msg_origin", None)
            if not check_target:
                check_target = (
                    f"{self._get_platform_id_from_event(event)}:GroupMessage:{group_id}"
                )

            is_allowed = self.config_manager.is_group_allowed(check_target)
            status = "已启用" if is_allowed else "未启用"
            mode = self.config_manager.get_group_list_mode()

            auto_status = (
                "已启用" if self.config_manager.get_enable_auto_analysis() else "未启用"
            )
            auto_time = self.config_manager.get_auto_analysis_time()

            pdf_status = PDFInstaller.get_pdf_status(self.config_manager)
            output_format = self.config_manager.get_output_format()
            min_threshold = self.config_manager.get_min_messages_threshold()

            # 增量分析状态
            incremental_enabled = self.config_manager.get_incremental_enabled()
            incremental_status_text = "未启用"
            if incremental_enabled:
                interval = self.config_manager.get_incremental_interval_minutes()
                max_daily = self.config_manager.get_incremental_max_daily_analyses()
                active_start = self.config_manager.get_incremental_active_start_hour()
                active_end = self.config_manager.get_incremental_active_end_hour()
                incremental_status_text = (
                    f"已启用 (间隔{interval}分钟, 最多{max_daily}次/天, "
                    f"活跃时段{active_start}:00-{active_end}:00)"
                )

            debug_report = self.config_manager.get_incremental_report_immediately()
            debug_status = "✅ 开启" if debug_report else "❌ 关闭"

            yield event.plain_result(f"""📊 当前群分析功能状态:
• 群分析功能: {status} (模式: {mode})
• 自动分析: {auto_status} ({auto_time})
• 增量分析: {incremental_status_text}
• 调试模式: {debug_status} (增量立即报告)
• 输出格式: {output_format}
• PDF 功能: {pdf_status}
• 最小消息数: {min_threshold}

💡 可用命令: enable, disable, status, reload, test, incremental_debug
💡 支持的输出格式: image, text, pdf (图片和PDF包含活跃度可视化)
💡 其他命令: /设置格式, /安装PDF, /增量状态""")

    @filter.command("增量状态", alias={"incremental_status"})
    @filter.permission_type(PermissionType.ADMIN)
    async def incremental_status(self, event: AstrMessageEvent):
        """查看当前增量分析状态（滑动窗口）"""
        group_id = self._get_group_id_from_event(event)
        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        if not self.config_manager.get_incremental_enabled():
            yield event.plain_result("ℹ️ 增量分析模式未启用，请在插件配置中开启")
            return

        import time as time_mod

        # 计算滑动窗口范围
        analysis_days = self.config_manager.get_analysis_days()
        window_end = time_mod.time()
        window_start = window_end - (analysis_days * 24 * 3600)

        # 查询窗口内的批次
        batches = await self.incremental_store.query_batches(
            group_id, window_start, window_end
        )

        if not batches:
            from datetime import datetime

            start_str = datetime.fromtimestamp(window_start).strftime("%m-%d %H:%M")
            end_str = datetime.fromtimestamp(window_end).strftime("%m-%d %H:%M")
            yield event.plain_result(
                f"📊 滑动窗口 ({start_str} ~ {end_str}) 内尚无增量分析数据"
            )
            return

        # 合并批次获取聚合视图
        state = self.incremental_merge_service.merge_batches(
            batches, window_start, window_end
        )
        summary = state.get_summary()

        yield event.plain_result(
            f"📊 增量分析状态 (窗口: {summary['window']})\n"
            f"• 分析次数: {summary['total_analyses']}\n"
            f"• 累计消息: {summary['total_messages']}\n"
            f"• 话题数: {summary['topics_count']}\n"
            f"• 金句数: {summary['quotes_count']}\n"
            f"• 参与者: {summary['participants']}\n"
            f"• 高峰时段: {summary['peak_hours']}"
        )

    def _get_group_id_from_event(self, event: AstrMessageEvent) -> str | None:
        """从消息事件中安全获取群组 ID"""
        try:
            group_id = event.get_group_id()
            return group_id if group_id else None
        except Exception:
            return None

    def _get_platform_id_from_event(self, event: AstrMessageEvent) -> str:
        """从消息事件中获取平台唯一 ID"""
        try:
            return event.get_platform_id()
        except Exception:
            # 后备方案：从元数据获取
            if (
                hasattr(event, "platform_meta")
                and event.platform_meta
                and hasattr(event.platform_meta, "id")
            ):
                return event.platform_meta.id
            return "default"
