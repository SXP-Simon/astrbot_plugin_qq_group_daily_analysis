"""
WebUI 视觉模板管理路由 (Template Routes)
处理报告主题模板列表获取、缩略图预览、GitHub 在线安装、ZIP 压缩包安装与卸载。
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import TYPE_CHECKING, cast

from ....shared.comic_prompts import COMIC_PROMPT_PREVIEWS, COMIC_STORYBOARD_PROMPTS
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

COMIC_PREVIEW_DIRECTORY = (
    Path(__file__).resolve().parents[4] / "assets" / "comic_previews"
)

if TYPE_CHECKING:
    from ....application.dto.webui_dto import (
        TemplateInstallFileDTO,
        TemplateInstallUrlDTO,
        TemplatePreviewQueryDTO,
        TemplateUninstallDTO,
    )
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
            return self.report_dispatcher.report_generator.html_templates
        if self.analysis_service and self.analysis_service.report_generator:
            return self.analysis_service.report_generator.html_templates
        return None

    async def api_get_report_templates(self) -> WebApiResponse:
        """获取系统内置及用户自定义的所有可用报告视觉模板"""
        try:
            html_tpls = self._get_html_templates()
            if html_tpls:
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
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            template_name = str(
                request.query.get("template_name")
                or request.query.get("template")
                or payload.get("template_name")
                or payload.get("template")
                or ""
            ).strip()
            if not template_name:
                return error_response("缺少模板名 (template_name)", status_code=400)
            try:
                template_name = validate_template_name(template_name)
            except TemplateInstallError as e:
                return error_response(str(e), status_code=400)

            query_dto: TemplatePreviewQueryDTO = {"template_name": template_name}

            # 防路径穿越：确认解析后的目标路径仍位于自定义模板根目录内
            store = default_template_store_dir().resolve()
            custom_dir = store / query_dto["template_name"]
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

    async def api_get_comic_template_preview(self) -> WebApiResponse:
        """读取内置漫画模板示例图，沿用报告预览的宿主解包结构。

        Returns:
            包含 data_url 的成功响应；已知无图模板返回空值，非法模板返回 400，
            缺失资源返回 404，读取异常返回 500。
        """
        template_name = str(request.query.get("template_name") or "").strip()
        if template_name not in COMIC_STORYBOARD_PROMPTS:
            return error_response("未知的内置漫画模板", status_code=400)
        variant = request.query.get("variant", "full")
        if variant not in {"thumbnail", "full"}:
            return error_response("漫画预览图尺寸选项无效", status_code=400)
        query_dto: TemplatePreviewQueryDTO = {"template_name": template_name}
        filename = COMIC_PROMPT_PREVIEWS.get(query_dto["template_name"])
        if not filename:
            return json_response({"status": "ok", "data": {"data_url": None}})
        if variant == "thumbnail":
            filename = f"{Path(filename).stem}-thumb.webp"

        try:
            # 仅接受目录白名单资源，并拒绝指向目录外部的符号链接。
            candidate = COMIC_PREVIEW_DIRECTORY / filename
            if candidate.is_symlink() or not is_path_within(
                candidate, COMIC_PREVIEW_DIRECTORY
            ):
                return error_response("该漫画模板没有预览图", status_code=404)
            content = await asyncio.to_thread(candidate.read_bytes)
            data_url = (
                f"data:image/webp;base64,{base64.b64encode(content).decode('ascii')}"
            )
            return json_response({"status": "ok", "data": {"data_url": data_url}})
        except FileNotFoundError:
            return error_response("该漫画模板没有预览图", status_code=404)
        except Exception as e:
            logger.error(f"读取漫画模板预览图失败: {e}", exc_info=True)
            return error_response("读取漫画模板预览图失败。", status_code=500)

    async def api_get_comic_template_rotation_status(self) -> WebApiResponse:
        """只读获取已保存配置的模板轮换进度，不预占生成次数。

        Returns:
            当前范围的轮换状态；未选择群会话时返回引导提示。
        """
        # 防腐边界显式收窄宿主输入，兼容不遵循查询契约的旧宿主。
        group_id = cast("object", request.query.get("group_id", ""))
        umo = cast("object", request.query.get("umo"))
        if not isinstance(group_id, str) or len(group_id) > 128:
            return error_response("群号必须是长度不超过 128 的字符串", status_code=400)
        if umo is not None and (not isinstance(umo, str) or len(umo) > 512):
            return error_response(
                "群会话必须是长度不超过 512 的字符串", status_code=400
            )
        cfg_mgr = (
            self.analysis_service.config_manager
            if self.analysis_service
            else self.report_dispatcher.config_manager
            if self.report_dispatcher
            else None
        )
        if cfg_mgr is None:
            return error_response("配置管理器未初始化", status_code=503)
        try:
            status = await asyncio.to_thread(
                cfg_mgr.get_comic_template_rotation_status, group_id=group_id, umo=umo
            )
            return json_response({"status": "ok", "data": status})
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        except Exception as exc:
            logger.error(f"读取漫画模板轮换状态失败: {exc}", exc_info=True)
            return error_response("读取漫画模板轮换状态失败。", status_code=500)

    async def api_reset_comic_template_rotation(self) -> WebApiResponse:
        """重置所选范围的轮换进度，不清理其他群会话。

        Returns:
            重置后的状态；群独立模式缺少完整会话时返回 400。
        """
        try:
            body = cast("object", await request.json())
        except Exception:
            return error_response("重置请求必须是 JSON 对象", status_code=400)
        if not isinstance(body, dict):
            return error_response("重置请求必须是 JSON 对象", status_code=400)
        if body.get("action") != "reset":
            return error_response(
                "重置请求缺少明确的 action=reset 操作", status_code=400
            )
        group_id = body.get("group_id", "")
        umo = body.get("umo")
        if not isinstance(group_id, str) or len(group_id) > 128:
            return error_response("群号必须是长度不超过 128 的字符串", status_code=400)
        if umo is not None and (not isinstance(umo, str) or len(umo) > 512):
            return error_response(
                "群会话必须是长度不超过 512 的字符串", status_code=400
            )
        cfg_mgr = (
            self.analysis_service.config_manager
            if self.analysis_service
            else self.report_dispatcher.config_manager
            if self.report_dispatcher
            else None
        )
        if cfg_mgr is None:
            return error_response("配置管理器未初始化", status_code=503)
        try:
            status = await asyncio.to_thread(
                cfg_mgr.reset_comic_template_rotation, group_id=group_id, umo=umo
            )
            return json_response({"status": "ok", "data": status})
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        except Exception as exc:
            logger.error(f"重置漫画模板轮换进度失败: {exc}", exc_info=True)
            return error_response("重置漫画模板轮换进度失败。", status_code=500)

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

            install_dto: TemplateInstallUrlDTO = {"repo_url": repo_url, "name": name}

            result = await install_template_from_github_url(
                install_dto["repo_url"], name=install_dto.get("name")
            )
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

            install_dto: TemplateInstallFileDTO = {
                "file_data": file_data,
                "filename": str(body.get("filename") or "template.zip"),
                "name": name,
            }

            result = await asyncio.to_thread(
                install_template_from_zip, zip_bytes, None, install_dto.get("name")
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

            name = str(
                body.get("name")
                or body.get("template_name")
                or request.query.get("name")
                or request.query.get("template_name")
                or ""
            ).strip()
            if not name:
                return error_response("缺少模板名 (name)", status_code=400)

            uninstall_dto: TemplateUninstallDTO = {"name": name}

            result = await asyncio.to_thread(uninstall_template, uninstall_dto["name"])

            html_tpls = self._get_html_templates()
            if html_tpls:
                html_tpls.invalidate_env(uninstall_dto["name"])

            return json_response({"status": "ok", "data": result})
        except TemplateInstallError as e:
            return error_response(str(e), status_code=400)
        except Exception as e:
            logger.error(f"卸载模板异常: {e}", exc_info=True)
            return error_response("卸载模板失败，请查看服务器日志。", status_code=500)
