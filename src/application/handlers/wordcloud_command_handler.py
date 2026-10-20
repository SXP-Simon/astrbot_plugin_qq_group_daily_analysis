"""群词云独立生成与重发指令。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...utils.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from astrbot.api.event import AstrMessageEvent, MessageEventResult

    from ..services.analysis_application_service import AnalysisApplicationService
    from ..services.wordcloud_delivery_service import WordCloudDeliveryService


class WordCloudCommandHandler:
    """仅处理词云，不触发 LLM、日报快照或分析游标。"""

    def __init__(
        self,
        analysis_service: AnalysisApplicationService,
        delivery: WordCloudDeliveryService,
    ) -> None:
        self.analysis_service = analysis_service
        self.delivery = delivery

    async def handle(
        self, event: AstrMessageEvent, days: int | None = None, *, retry: bool = False
    ) -> AsyncGenerator[MessageEventResult]:
        """校验当前群权限后采集词频或重绘已有词频。

        Args:
            event: 群聊指令事件。
            days: 采集天数，留空使用插件默认值。
            retry: 是否仅重发最近一次统计结果。

        Yields:
            进度或错误消息。
        """
        event.should_call_llm(False)
        group_id = event.get_group_id()
        platform_id = event.get_platform_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用词云指令。")
            return
        umo = event.unified_msg_origin or f"{platform_id}:GroupMessage:{group_id}"
        config = self.delivery.config_manager
        if not config.is_group_allowed(umo):
            yield event.plain_result("此群未启用日常分析功能。")
            return
        self.analysis_service.bot_manager.update_from_event(event)
        merged_mode = bool(
            self.delivery.merged_delivery
            and self.delivery.merged_delivery.enabled_for(platform_id, "wordcloud")
        )
        try:
            if not config.get_wordcloud_options(umo).enabled:
                yield event.plain_result(
                    "词云功能已关闭，请在插件的“词云”配置分组中启用。"
                )
                return
            if retry:
                data = self.delivery.store.latest(umo)
                if data is None:
                    yield event.plain_result(
                        "还没有可重发的词频记录，请先使用 /群词云。"
                    )
                    return
            else:
                yield event.plain_result("正在提取群聊词频并生成词云……")
                data = await self.analysis_service.collect_wordcloud(
                    group_id,
                    platform_id,
                    days=days if days is not None else config.get_analysis_days(),
                )
            if not data.frequencies:
                yield event.plain_result("这段时间还没有可用于词云的有效词语。")
                return
            if not await self.delivery.send(
                data, group_id, platform_id, force=True, umo=umo
            ):
                yield event.plain_result(
                    "词云出图或发送失败，词频已保存。可使用 /重发词云 再试，或查看插件日志。"
                )
            elif merged_mode:
                # 适配器直接转发不会更新宿主事件的发送标记，结束事件防止额外回复。
                event.stop_event()
        except Exception as exc:
            logger.warning(f"群 {group_id} 独立词云失败：{exc}")
            yield event.plain_result(f"词云生成失败：{exc}")
