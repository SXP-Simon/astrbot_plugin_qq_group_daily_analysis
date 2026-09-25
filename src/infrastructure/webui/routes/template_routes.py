"""
WebUI 视觉模板管理路由 (Template Routes)
处理报告主题模板列表获取、缩略图预览、GitHub 在线安装、ZIP 压缩包安装与卸载。
"""

from __future__ import annotations

import asyncio
import base64
from typing import TYPE_CHECKING

from ....utils.logger import logger
from ...reporting.template_installer import (
    MAX_ZIP_B64_SIZE,
    TemplateInstallError,
    default_template_store_dir,
    install_template_from_github_url,
    install_template_from_zip,
    is_path_within,
    preview_candidate_files,
    uninstall_template,
    validate_template_name,
)
from ..web_compat import WebApiResponse, error_response, json_response, request

if TYPE_CHECKING:
    from ....application.services.analysis_application_service import (
        AnalysisApplicationService,
    )
    from ...reporting.dispatcher import ReportDispatcher
    from ...reporting.templates import HTMLTemplates


class TemplateRoutes:
    """视觉模板 Web API 路由处理器。"""

    analysis_service: AnalysisApplicationService | None
    report_dispatcher: ReportDispatcher | None

    def __init__(
        self,
        analysis_service: AnalysisApplicationService | None,
        report_dispatcher: ReportDispatcher | None = None,
    ) -> None:
        self.analysis_service = analysis_service
        self.report_dispatcher = report_dispatcher

    def _get_html_templates(self) -> HTMLTemplates | None:
        """获取当前可用的 HTMLTemplates 实例。"""
        if self.report_dispatcher and self.report_dispatcher.report_generator:
            return getattr(
                self.report_dispatcher.report_generator, "html_templates", None
            )
        if self.analysis_service and self.analysis_service.report_generator:
            return getattr(
                self.analysis_service.report_generator, "html_templates", None
            )
        return None

    async def api_get_report_templates(self) -> WebApiResponse:
        """获取系统内置及用户自定义的所有可用报告视觉模板"""
        try:
            html_tpls = self._get_html_templates()
            if html_tpls and hasattr(html_tpls, "get_available_templates"):
                templates = html_tpls.get_available_templates()
            else:
                from ...reporting.templates import HTMLTemplates

                cfg_mgr = (
                    self.analysis_service.config_manager
                    if self.analysis_service
                    else (
                        self.report_dispatcher.config_manager
                        if self.report_dispatcher
                        else None
                    )
                )
                if not cfg_mgr:
                    return error_response("配置管理器未初始化", status_code=500)
                tpl_mgr = HTMLTemplates(cfg_mgr)
                templates = tpl_mgr.get_available_templates()
            return json_response({"status": "ok", "data": templates})
        except Exception as e:
            logger.error(f"获取模板列表异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_template_preview(self) -> WebApiResponse:
        """获取自定义模板的预览图（base64 data URL，供 WebUI 画廊等展示）"""
        try:
            template_name = str(request.query.get("template_name", "")).strip()
            if not template_name:
                return error_response("缺少模板名 (template_name)", status_code=400)
            try:
                template_name = validate_template_name(template_name)
            except TemplateInstallError as e:
                return error_response(str(e), status_code=400)

            # 防路径穿越：确认解析后的目标路径仍位于自定义模板根目录内
            store = default_template_store_dir().resolve()
            custom_dir = store / template_name
            if not is_path_within(custom_dir, store):
                return error_response("模板名非法", status_code=400)

            # 候选文件拒绝符号链接并确认解析后仍在模板目录内
            for candidate in preview_candidate_files(custom_dir):
                content = await asyncio.to_thread(candidate.read_bytes)
                mime = (
                    "image/png" if candidate.suffix.lower() == ".png" else "image/jpeg"
                )
                data_url = (
                    f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}"
                )
                return json_response({"status": "ok", "data": {"data_url": data_url}})
            return error_response("该模板没有预览图", status_code=404)
        except Exception as e:
            logger.error(f"获取模板预览图异常: {e}", exc_info=True)
            return error_response("读取模板预览图失败。", status_code=500)

    async def api_install_template_from_url(self) -> WebApiResponse:
        """从 GitHub 仓库链接安装自定义报告视觉模板"""
        try:
            try:
                body = await request.json()
            except Exception:
                body = {}

            repo_url = str(body.get("repo_url") or "")
            name = str(body.get("name") or "").strip() or None
            if not repo_url:
                return error_response(
                    "缺少 GitHub 仓库链接 (repo_url)", status_code=400
                )

            result = await install_template_from_github_url(repo_url, name=name)
            return json_response({"status": "ok", "data": result})
        except TemplateInstallError as e:
            return error_response(str(e), status_code=400)
        except Exception as e:
            logger.error(f"从 URL 安装模板异常: {e}", exc_info=True)
            return error_response("安装模板失败，请查看服务器日志。", status_code=500)

    async def api_install_template_from_file(self) -> WebApiResponse:
        """从上传的 zip 压缩包安装自定义报告视觉模板（JSON Base64 编码）"""
        try:
            try:
                body = await request.json()
            except Exception:
                body = {}

            file_data = body.get("file_data") or body.get("base64")
            name = str(body.get("name") or "").strip() or None
            if not file_data or not isinstance(file_data, str):
                return error_response("未检测到压缩包数据 (file_data)", status_code=400)

            if file_data.startswith("data:"):
                _, b64_payload = file_data.split(",", 1)
            else:
                b64_payload = file_data

            if len(b64_payload) > MAX_ZIP_B64_SIZE:
                return error_response("压缩包数据超出大小限制", status_code=400)
            try:
                zip_bytes = base64.b64decode(b64_payload)
            except Exception:
                return error_response("压缩包数据不是有效的 Base64", status_code=400)

            result = await asyncio.to_thread(
                install_template_from_zip, zip_bytes, None, name
            )
            return json_response({"status": "ok", "data": result})
        except TemplateInstallError as e:
            return error_response(str(e), status_code=400)
        except Exception as e:
            logger.error(f"从压缩包安装模板异常: {e}", exc_info=True)
            return error_response("安装模板失败，请查看服务器日志。", status_code=500)

    async def api_uninstall_template(self) -> WebApiResponse:
        """卸载通过安装器安装的自定义报告视觉模板（内置模板与手动放入的目录拒绝）"""
        try:
            try:
                body = await request.json()
            except Exception:
                body = {}

            name = str(body.get("name") or "").strip()
            if not name:
                return error_response("缺少模板名 (name)", status_code=400)

            result = await asyncio.to_thread(uninstall_template, name)

            html_tpls = self._get_html_templates()
            if html_tpls and hasattr(html_tpls, "invalidate_env"):
                html_tpls.invalidate_env(name)

            return json_response({"status": "ok", "data": result})
        except TemplateInstallError as e:
            return error_response(str(e), status_code=400)
        except Exception as e:
            logger.error(f"卸载模板异常: {e}", exc_info=True)
            return error_response("卸载模板失败，请查看服务器日志。", status_code=500)
