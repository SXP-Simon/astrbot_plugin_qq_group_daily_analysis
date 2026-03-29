"""
网页日报发布器。
"""

from __future__ import annotations

from dataclasses import dataclass

import aiohttp

from ...utils.logger import logger


@dataclass(frozen=True)
class WebReportPublishResult:
    report_id: str
    url: str


class WebReportPublisher:
    """负责将日报 JSON 上传到 Worker。"""

    def __init__(self, config_manager):
        self.config_manager = config_manager

    def is_enabled(self) -> bool:
        return bool(self.config_manager.get_web_report_enabled())

    def is_configured(self) -> bool:
        return bool(
            self.config_manager.get_web_report_api_base().strip()
            and self.config_manager.get_web_report_upload_token().strip()
        )

    async def publish(
        self,
        report_payload: dict,
    ) -> WebReportPublishResult | None:
        if not self.is_enabled():
            logger.info("网页日报未启用，跳过 Worker 上传")
            return None

        if not self.is_configured():
            logger.warning("网页日报未配置完整，跳过 Worker 上传")
            return None

        api_base = self.config_manager.get_web_report_api_base().rstrip("/")
        upload_url = f"{api_base}/api/internal/reports"
        timeout_seconds = max(5, self.config_manager.get_web_report_timeout_seconds())

        payload = {
            "ttl_seconds": self.config_manager.get_web_report_ttl_days() * 86400,
            "report": report_payload,
        }
        headers = {
            "Authorization": (
                f"Bearer {self.config_manager.get_web_report_upload_token().strip()}"
            )
        }

        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        try:
            async with aiohttp.ClientSession(
                timeout=timeout, trust_env=True
            ) as session:
                async with session.post(
                    upload_url,
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status != 200:
                        body = await response.text()
                        logger.warning(
                            f"网页日报上传失败 ({response.status}): {body[:300]}"
                        )
                        return None

                    data = await response.json()
                    report_id = str(data.get("report_id", "") or "")
                    url = str(data.get("url", "") or "")
                    if not report_id or not url:
                        logger.warning("网页日报上传返回缺少 report_id 或 url")
                        return None
                    return WebReportPublishResult(report_id=report_id, url=url)
        except Exception as exc:
            logger.error(f"网页日报上传异常: {exc}", exc_info=True)
            return None
