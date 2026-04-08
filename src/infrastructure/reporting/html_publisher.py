"""
HTML 报告发布器
负责上传 HTML 报告到图床，或按现有逻辑发送本地文件/外链。
"""

import json
import os
from pathlib import Path
from urllib.parse import quote, urlsplit

import aiohttp

from ...utils.logger import logger


class HtmlReportPublisher:
    """HTML 报告发布器"""

    def __init__(self, config_manager, message_sender):
        self.config_manager = config_manager
        self.message_sender = message_sender

    def build_caption(
        self,
        html_path: str | None = None,
        public_url: str | None = None,
    ) -> str:
        """构建 HTML 报告提示文本。"""
        caption = "📊 每日群聊分析报告已生成"
        final_url = public_url
        if not final_url and not self.config_manager.get_html_upload_enabled():
            final_url = self._build_self_hosted_url(html_path)
        if final_url:
            return f"{caption}\n{final_url}"
        return caption

    async def publish(
        self,
        group_id: str,
        html_path: str,
        platform_id: str | None = None,
    ) -> bool:
        """发布 HTML 报告。"""
        if not html_path:
            return False

        public_url = None
        if self.config_manager.get_html_upload_enabled():
            public_url = await self.upload(html_path)
            if public_url:
                sent = await self.message_sender.send_text(
                    group_id,
                    self.build_caption(public_url=public_url),
                    platform_id,
                )
                if sent:
                    return True
                logger.warning("HTML 图床外链发送失败，回退为发送本地 HTML 文件。")
            else:
                logger.warning("HTML 图床上传失败，回退为发送本地 HTML 文件。")

        return await self.message_sender.send_file(
            group_id,
            html_path,
            caption=self.build_caption(html_path=html_path, public_url=public_url),
            platform_id=platform_id,
        )

    async def upload(self, html_path: str) -> str | None:
        """上传 HTML 报告到图床并返回最终外链。"""
        base_url = self._normalized_base_url()
        token = str(self.config_manager.get_html_upload_token() or "").strip()
        if not base_url:
            logger.warning("HTML 图床上传已启用，但未配置 html_base_url。")
            return None
        if not token:
            logger.warning("HTML 图床上传已启用，但未配置 html_upload_token。")
            return None

        upload_url = f"{base_url}/upload"
        params = {
            "returnFormat": "default",
            "uploadNameType": "origin",
        }
        channel = str(
            self.config_manager.get_html_upload_channel() or "default"
        ).strip()
        if channel and channel != "default":
            params["uploadChannel"] = channel

        timeout = aiohttp.ClientTimeout(total=60)
        headers = {"Authorization": f"Bearer {token}"}
        file_name = Path(html_path).name

        try:
            async with aiohttp.ClientSession(
                trust_env=True, timeout=timeout
            ) as session:
                with open(html_path, "rb") as file_obj:
                    form = aiohttp.FormData()
                    form.add_field(
                        "file",
                        file_obj,
                        filename=file_name,
                        content_type="text/html",
                    )
                    async with session.post(
                        upload_url,
                        params=params,
                        headers=headers,
                        data=form,
                    ) as response:
                        response_text = await response.text()
                        if response.status >= 400:
                            logger.warning(
                                "HTML 图床上传失败: status=%s body=%s",
                                response.status,
                                response_text[:300],
                            )
                            return None

                        try:
                            payload = json.loads(response_text)
                        except json.JSONDecodeError:
                            logger.warning(
                                "HTML 图床上传返回了非 JSON 响应: %s",
                                response_text[:300],
                            )
                            return None

        except FileNotFoundError:
            logger.warning("HTML 图床上传失败，本地文件不存在: %s", html_path)
            return None
        except Exception:
            logger.exception("HTML 图床上传异常")
            return None

        src = self._extract_src(payload)
        if not src:
            logger.warning("HTML 图床上传响应中缺少 src 字段: %s", payload)
            return None

        final_url = self._build_public_url(src)
        if not final_url:
            logger.warning("HTML 图床上传成功，但无法构建最终外链: %s", src)
            return None

        return final_url

    def _normalized_base_url(self) -> str:
        base_url = str(self.config_manager.get_html_base_url() or "").strip()
        return base_url.rstrip("/")

    def _build_self_hosted_url(self, html_path: str | None) -> str | None:
        if not html_path:
            return None

        base_url = self._normalized_base_url()
        if not base_url:
            return None

        output_dir = Path(self.config_manager.get_html_output_dir()).resolve(
            strict=False
        )
        try:
            relative_path = (
                Path(html_path).resolve(strict=False).relative_to(output_dir)
            )
            relative_url = str(relative_path).replace(os.sep, "/")
        except Exception:
            relative_url = Path(html_path).name

        encoded_relative_url = quote(relative_url, safe="/")
        return f"{base_url}/{encoded_relative_url.lstrip('/')}"

    def _build_public_url(self, src: str) -> str | None:
        base_url = self._normalized_base_url()
        if not base_url or not src:
            return None

        src = str(src).strip()
        if src.startswith(("http://", "https://")):
            parsed = urlsplit(src)
            relative = parsed.path or "/"
            if parsed.query:
                relative = f"{relative}?{parsed.query}"
            if parsed.fragment:
                relative = f"{relative}#{parsed.fragment}"
            return (
                f"{base_url}{relative if relative.startswith('/') else '/' + relative}"
            )

        return f"{base_url}/{src.lstrip('/')}"

    @staticmethod
    def _extract_src(payload) -> str | None:
        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, dict):
                src = first.get("src")
                if isinstance(src, str) and src.strip():
                    return src.strip()

        if isinstance(payload, dict):
            src = payload.get("src")
            if isinstance(src, str) and src.strip():
                return src.strip()

            data = payload.get("data")
            if isinstance(data, list) and data:
                first = data[0]
                if isinstance(first, dict):
                    src = first.get("src")
                    if isinstance(src, str) and src.strip():
                        return src.strip()
            elif isinstance(data, dict):
                src = data.get("src")
                if isinstance(src, str) and src.strip():
                    return src.strip()

        return None
