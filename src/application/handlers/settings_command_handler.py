"""
设置与模板相关指令处理器 (Settings & Template Command Handler)

负责处理 /设置格式, /设置模板, /查看模板, /分析设置, /增量状态 等 Bot 交互命令。
"""

from __future__ import annotations

import time as time_mod
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

from ...domain.repositories.config_repository import IConfigProvider
from ...domain.repositories.persistence_repository import IIncrementalStore
from ...domain.services.incremental_merge_service import IncrementalMergeService
from ..services.analysis_application_service import DuplicateGroupTaskError
from ..services.template_command_service import TemplateCommandService


class SettingsCommandHandler:
    """管理设置、模板切换与状态查询的命令处理器。"""

    def __init__(
        self,
        config_manager: IConfigProvider,
        template_command_service: TemplateCommandService,
        template_preview_router: Any,
        auto_scheduler: Any,
        incremental_store: IIncrementalStore | None = None,
        incremental_merge_service: IncrementalMergeService | None = None,
        bot_manager: Any | None = None,
        context: Any | None = None,
    ) -> None:
        self.config_manager = config_manager
        self.template_command_service = template_command_service
        self.template_preview_router = template_preview_router
        self.auto_scheduler = auto_scheduler
        self.incremental_store = incremental_store
        self.incremental_merge_service = incremental_merge_service
        self.bot_manager = bot_manager
        self.context = context

    async def handle_set_output_format(
        self, event: AstrMessageEvent, format_input: str = ""
    ) -> AsyncGenerator[Any, None]:
        """处理 /设置格式 命令。

        Args:
            event: AstrBot 消息事件对象。
            format_input: 用户输入的格式名称或序号。

        Returns:
            AsyncGenerator[Any, None]: 结果消息生成器。
        """
        event.should_call_llm(True)

        available_formats = ["image", "text", "html"]
        format_display_names = {
            "image": "图片格式 (默认)",
            "text": "文本格式",
            "html": "交互式 HTML 网页",
        }

        if not format_input:
            current = ", ".join(self.config_manager.get_output_format())
            format_list_str = "\n".join(
                [
                    f"【{i}】{f} - {format_display_names[f]}"
                    for i, f in enumerate(available_formats, start=1)
                ]
            )
            yield event.plain_result(f"""📊 当前输出格式: {current}

可用格式:
{format_list_str}

用法: /设置格式 [名称或序号] 如 /设置格式 image,html""")
            return

        target_format = None
        if format_input.isdigit():
            idx = int(format_input) - 1
            if 0 <= idx < len(available_formats):
                target_format = available_formats[idx]

        if not target_format:
            input_lower = format_input.lower()
            if input_lower in available_formats:
                target_format = input_lower

        if not target_format:
            parts = [f.strip() for f in format_input.replace("，", ",").split(",")]
            if all(p in available_formats for p in parts) and len(parts) > 1:
                try:
                    self.config_manager.set_output_format(parts)
                    yield event.plain_result(f"✅ 输出格式已设置为: {', '.join(parts)}")
                except Exception as e:
                    yield event.plain_result(f"❌ 设置失败: {e}")
                return

        if not target_format:
            yield event.plain_result(
                f"❌ 无效的格式类型 '{format_input}'。可用: {', '.join(available_formats)} 或序号 1-{len(available_formats)}"
            )
            return

        try:
            self.config_manager.set_output_format(target_format)  # type: ignore[arg-type]
            yield event.plain_result(f"✅ 输出格式已设置为: {target_format}")
        except Exception as e:
            yield event.plain_result(f"❌ 设置失败: {e}")

    async def handle_set_report_template(
        self, event: AstrMessageEvent, template_input: str = ""
    ) -> AsyncGenerator[Any, None]:
        """处理 /设置模板 命令。

        Args:
            event: AstrBot 消息事件对象。
            template_input: 用户输入的模板名称或序号。

        Returns:
            AsyncGenerator[Any, None]: 结果消息生成器。
        """
        event.should_call_llm(True)

        available_templates = self.template_command_service.list_available_templates()

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

        template_name, parse_error = self.template_command_service.parse_template_input(
            template_input, available_templates
        )
        if parse_error:
            yield event.plain_result(parse_error)
            return

        if not template_name:
            yield event.plain_result(f"❌ 无法解析模板输入: {template_input}")
            return

        if not await self.template_command_service.template_exists(template_name):
            yield event.plain_result(f"❌ 模板 '{template_name}' 不存在")
            return

        self.config_manager.set_report_template(template_name)
        yield event.plain_result(f"✅ 报告模板已设置为: {template_name}")

    async def handle_view_templates(
        self, event: AstrMessageEvent, platform_id: str
    ) -> AsyncGenerator[Any, None]:
        """处理 /查看模板 命令。

        Args:
            event: AstrBot 消息事件对象。
            platform_id: 当前平台标识。

        Returns:
            AsyncGenerator[Any, None]: 结果消息生成器。
        """
        event.should_call_llm(True)

        available_templates = self.template_command_service.list_available_templates()
        if not available_templates:
            yield event.plain_result("❌ 未找到任何可用的报告模板")
            return

        if self.template_preview_router and self.context:
            await self.template_preview_router.ensure_handlers_registered(self.context)
            (
                handled,
                handler_results,
            ) = await self.template_preview_router.handle_view_templates(
                event=event,
                platform_id=platform_id,
                available_templates=available_templates,
            )
            if handled:
                for result in handler_results:
                    yield result
                return

        current_template = self.config_manager.get_report_template()
        bot_id = event.get_self_id()
        preview_nodes = self.template_command_service.build_template_preview_nodes(
            available_templates=available_templates,
            current_template=current_template,
            bot_id=bot_id,
        )
        yield event.chain_result([preview_nodes])

    async def handle_analysis_settings(
        self,
        event: AstrMessageEvent,
        action: str,
        group_id: str,
        platform_id: str,
    ) -> AsyncGenerator[Any, None]:
        """处理 /分析设置 命令。

        Args:
            event: AstrBot 消息事件对象。
            action: 操作动作子指令 (enable, disable, reload, test, incremental_debug, filter_bot, status 等)。
            group_id: 当前群聊 ID。
            platform_id: 当前平台标识。

        Returns:
            AsyncGenerator[Any, None]: 结果消息生成器。
        """
        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        if action == "enable":
            async for result in self._handle_settings_enable(event, group_id):
                yield result
            return
        elif action == "disable":
            async for result in self._handle_settings_disable(event, group_id):
                yield result
            return
        elif action == "reload":
            if self.auto_scheduler:
                self.auto_scheduler.schedule_jobs(self.context)
            await self._refresh_incremental_target_states()
            yield event.plain_result("✅ 已重新加载配置并重启定时任务")
            return
        elif action == "test":
            check_target = getattr(event, "unified_msg_origin", None)
            if not check_target:
                check_target = f"{platform_id}:GroupMessage:{group_id}"

            if not self.config_manager.is_group_allowed(check_target):
                yield event.plain_result("❌ 请先启用当前群的分析功能")
                return

            yield event.plain_result("🧪 开始测试自动分析功能...")

            if self.bot_manager:
                self.bot_manager.update_from_event(event)

            try:
                if self.auto_scheduler:
                    result = await self.auto_scheduler._perform_auto_analysis_for_group(
                        group_id
                    )
                else:
                    result = {"success": False, "reason": "auto_scheduler_missing"}

                if isinstance(result, dict) and result.get("success"):
                    yield event.plain_result("✅ 自动分析及报告发送成功，请查看群消息")
                else:
                    reason = (
                        result.get("reason", "unknown")
                        if isinstance(result, dict)
                        else "invalid_result"
                    )
                    yield event.plain_result(f"❌ 自动分析或报告发送失败: {reason}")
            except DuplicateGroupTaskError:
                yield event.plain_result("📊 该群的分析任务正在执行中，请稍后再试哦~")
            except Exception as e:
                yield event.plain_result(f"❌ 自动分析测试失败: {str(e)}")
            return
        elif action == "incremental_debug":
            current_state = self.config_manager.get_incremental_report_immediately()
            new_state = not current_state
            self.config_manager.set_incremental_report_immediately(new_state)
            status_text = "已启用" if new_state else "已禁用"
            yield event.plain_result(f"✅ 增量分析立即报告模式: {status_text}")
            return
        elif action == "filter_bot":
            current = self.config_manager.get_filter_bot_messages()
            new_state = not current
            self.config_manager.set_filter_bot_messages(new_state)
            status_text = "已启用" if new_state else "已禁用"
            yield event.plain_result(f"✅ 过滤机器人消息: {status_text}")
            return
        else:  # status
            check_target = getattr(event, "unified_msg_origin", None)
            if not check_target:
                check_target = f"{platform_id}:GroupMessage:{group_id}"

            is_allowed = self.config_manager.is_group_allowed(check_target)
            status = "已启用" if is_allowed else "未启用"
            mode = self.config_manager.get_group_list_mode()

            auto_status = (
                "已启用" if self.config_manager.is_auto_analysis_enabled() else "未启用"
            )
            auto_time_raw = self.config_manager.get_auto_analysis_time()
            auto_time_str = (
                ", ".join(auto_time_raw)
                if isinstance(auto_time_raw, list)
                else str(auto_time_raw)
            )

            output_formats = self.config_manager.get_output_format()
            output_format = output_formats[0] if output_formats else "image"
            min_threshold = self.config_manager.get_min_messages_threshold()

            incremental_enabled = self.config_manager.get_incremental_enabled()
            incremental_status_text = "未启用"
            if incremental_enabled:
                batch_messages = self.config_manager.get_incremental_min_messages()
                incremental_status_text = f"已启用 (每 {batch_messages} 条消息触发)"

            debug_report = self.config_manager.get_incremental_report_immediately()
            debug_status = "✅ 开启" if debug_report else "❌ 关闭"
            filter_bot = self.config_manager.get_filter_bot_messages()
            filter_bot_status = "✅ 开启" if filter_bot else "❌ 关闭"

            yield event.plain_result(f"""📊 当前群分析功能状态:
• 群分析功能: {status} (模式: {mode})
• 自动分析: {auto_status} ({auto_time_str})
• 增量分析: {incremental_status_text}
• 调试模式: {debug_status} (增量立即报告)
• 过滤机器人: {filter_bot_status}
• 输出格式: {output_format}
• 最小消息数: {min_threshold}

💡 可用命令: enable, disable, status, reload, test, filter_bot, incremental_debug
💡 支持的输出格式: image, text (图片包含活跃度可视化)
💡 其他命令: /设置格式, /增量状态""")

    async def handle_incremental_status(
        self, event: AstrMessageEvent, group_id: str
    ) -> AsyncGenerator[Any, None]:
        """处理 /增量状态 命令。

        Args:
            event: AstrBot 消息事件对象。
            group_id: 目标群号。

        Returns:
            AsyncGenerator[Any, None]: 结果消息生成器。
        """
        if not group_id:
            yield event.plain_result("❌ 请在群聊中使用此命令")
            return

        if not self.config_manager.get_incremental_enabled():
            yield event.plain_result("ℹ️ 增量分析模式未启用，请在插件配置中开启")
            return

        if not self.incremental_store or not self.incremental_merge_service:
            yield event.plain_result("❌ 增量分析组件未初始化")
            return

        analysis_days = self.config_manager.get_analysis_days()
        window_end = time_mod.time()
        window_start = window_end - (analysis_days * 24 * 3600)

        batches = await self.incremental_store.query_batches(
            group_id, window_start, window_end
        )

        if not batches:
            start_str = datetime.fromtimestamp(window_start).strftime("%m-%d %H:%M")
            end_str = datetime.fromtimestamp(window_end).strftime("%m-%d %H:%M")
            yield event.plain_result(
                f"📊 滑动窗口 ({start_str} ~ {end_str}) 内尚无增量分析数据"
            )
            return

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

    async def _handle_settings_enable(
        self, event: AstrMessageEvent, group_id: str
    ) -> AsyncGenerator[Any, None]:
        """处理启用设置的分支逻辑。

        Args:
            event: AstrBot 消息事件对象。
            group_id: 当前群聊 ID。

        Returns:
            AsyncGenerator[Any, None]: 结果消息生成器。
        """
        mode = self.config_manager.get_group_list_mode()
        target_id = event.unified_msg_origin or group_id

        if mode == "whitelist":
            glist = list(self.config_manager.get_group_list())
            if not self.config_manager.is_group_allowed(target_id):
                glist.append(target_id)
                self.config_manager.set_group_list(glist)
                if self.auto_scheduler:
                    self.auto_scheduler.schedule_jobs(self.context)
                await self._refresh_incremental_target_states()
                yield event.plain_result(f"✅ 已将当前群加入白名单\nID: {target_id}")
            else:
                yield event.plain_result("ℹ️ 当前群已在白名单中")
        elif mode == "blacklist":
            glist = list(self.config_manager.get_group_list())
            removed = False
            if target_id in glist:
                glist.remove(target_id)
                removed = True
            if group_id in glist:
                glist.remove(group_id)
                removed = True

            if removed:
                self.config_manager.set_group_list(glist)
                if self.auto_scheduler:
                    self.auto_scheduler.schedule_jobs(self.context)
                await self._refresh_incremental_target_states()
                yield event.plain_result("✅ 已将当前群从黑名单移除")
            else:
                yield event.plain_result("ℹ️ 当前群不在黑名单中")
        else:
            yield event.plain_result("ℹ️ 当前为无限制模式，所有群聊默认启用")

    async def _handle_settings_disable(
        self, event: AstrMessageEvent, group_id: str
    ) -> AsyncGenerator[Any, None]:
        """处理禁用设置的分支逻辑。

        Args:
            event: AstrBot 消息事件对象。
            group_id: 当前群聊 ID。

        Returns:
            AsyncGenerator[Any, None]: 结果消息生成器。
        """
        mode = self.config_manager.get_group_list_mode()
        target_id = event.unified_msg_origin or group_id

        if mode == "whitelist":
            glist = list(self.config_manager.get_group_list())
            removed = False
            if target_id in glist:
                glist.remove(target_id)
                removed = True
            if group_id in glist:
                glist.remove(group_id)
                removed = True

            if removed:
                self.config_manager.set_group_list(glist)
                if self.auto_scheduler:
                    self.auto_scheduler.schedule_jobs(self.context)
                await self._refresh_incremental_target_states()
                yield event.plain_result("✅ 已将当前群从白名单移除")
            else:
                yield event.plain_result("ℹ️ 当前群不在白名单中")
        elif mode == "blacklist":
            glist = list(self.config_manager.get_group_list())
            if self.config_manager.is_group_allowed(target_id):
                glist.append(target_id)
                self.config_manager.set_group_list(glist)
                if self.auto_scheduler:
                    self.auto_scheduler.schedule_jobs(self.context)
                await self._refresh_incremental_target_states()
                yield event.plain_result(f"✅ 已将当前群加入黑名单\nID: {target_id}")
            else:
                yield event.plain_result("ℹ️ 当前群已在黑名单中")
        else:
            yield event.plain_result("ℹ️ 当前为无限制模式，如需禁用请切换到黑名单模式")

    async def _refresh_incremental_target_states(self) -> None:
        """在插件内修改名单后立即同步增量状态。"""
        if self.auto_scheduler and self.auto_scheduler.incremental_trigger:
            await self.auto_scheduler.incremental_trigger.refresh_target_states()
