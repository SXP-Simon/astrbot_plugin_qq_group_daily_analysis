"""
WebUI 报告产物管理路由 (Report Routes)
处理历史报告查询、文件详情/Base64预览与免 Token 模板重新渲染。
"""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from ....utils.logger import logger
from ...reporting.template_installer import TemplateInstallError, validate_template_name
from ..web_compat import WebApiResponse, error_response, json_response, request

if TYPE_CHECKING:
    from ....application.dto.webui_dto import (
        ReportContentQueryDTO,
        RerenderReportRequestDTO,
    )
    from ....application.services.analysis_application_service import (
        AnalysisApplicationService,
    )
    from ...persistence.trace_sqlite_store import TraceSQLiteStore
    from ...reporting.dispatcher import ReportDispatcher


class ReportHistoryItemDTO(TypedDict):
    """历史报告文件元数据契约"""

    filename: str
    size_bytes: int
    modified_at: float
    absolute_path: str
    is_html: bool
    is_comic: bool
    report_type: str
    group_id: str
    group_name: str
    platform: str
    trace_id: str


class ReportRoutes:
    """报告产物 Web API 路由处理器。"""

    trace_store: TraceSQLiteStore
    analysis_service: AnalysisApplicationService | None
    report_dispatcher: ReportDispatcher | None
    report_output_dir: Path | None

    def __init__(
        self,
        trace_store: TraceSQLiteStore,
        analysis_service: AnalysisApplicationService | None,
        report_dispatcher: ReportDispatcher | None = None,
        report_output_dir: Path | None = None,
    ) -> None:
        self.trace_store = trace_store
        self.analysis_service = analysis_service
        self.report_dispatcher = report_dispatcher
        self.report_output_dir = report_output_dir

    async def api_get_report_history(self) -> WebApiResponse:
        """获取历史生成的报告文件列表（支持图片与 HTML 报告，包含群号、群名与平台归属精准解析）"""
        try:
            reports: list[ReportHistoryItemDTO] = []
            group_info_map = {
                str(g["group_id"]): {
                    "group_name": str(g.get("group_name", "")),
                    "platform": str(g.get("platform", "")),
                }
                for g in self.trace_store.get_distinct_groups()
            }
            candidate_dirs: list[Path] = []
            if self.report_output_dir and self.report_output_dir.exists():
                candidate_dirs.append(self.report_output_dir)

            # 兼容自托管 HTML 输出目录
            cfg_mgr = (
                self.analysis_service.config_manager
                if self.analysis_service
                else (
                    self.report_dispatcher.config_manager
                    if self.report_dispatcher
                    else None
                )
            )
            if cfg_mgr:
                custom_html_dir = cfg_mgr.get_html_output_dir() or ""
                if custom_html_dir:
                    p = Path(custom_html_dir)
                    if p.exists() and p not in candidate_dirs:
                        candidate_dirs.append(p)

            seen_paths: set[Path] = set()
            valid_exts = {".png", ".jpg", ".jpeg", ".html"}

            # 1. Level 1: 优先走数据库 report_artifacts 索引极速查询
            db_artifacts: list[dict[str, object]] = []
            try:
                db_artifacts = self.trace_store.query_report_artifacts(limit=150)
            except Exception:
                pass

            if db_artifacts:
                for art in db_artifacts:
                    fn = str(art.get("filename") or "")
                    rel_p = str(art.get("relative_path") or fn)
                    g_id = str(art.get("group_id") or "")
                    t_id = str(art.get("trace_id") or "")

                    matched_file: Path | None = None
                    for d in candidate_dirs:
                        cand = d / rel_p
                        if cand.is_file() and cand.exists():
                            matched_file = cand
                            break
                        if "/" in rel_p or "\\" in rel_p:
                            cand2 = d / Path(rel_p).name
                            if cand2.is_file() and cand2.exists():
                                matched_file = cand2
                                break

                    if not matched_file:
                        continue

                    res_p = matched_file.resolve()
                    if res_p in seen_paths:
                        continue
                    seen_paths.add(res_p)

                    try:
                        stat = matched_file.stat()
                        stem = matched_file.stem
                        is_html = matched_file.suffix.lower() == ".html"
                        is_comic = stem.lower().startswith("comic_") or stem.startswith(
                            "漫画_"
                        )
                        g_info = group_info_map.get(g_id, {})
                        reports.append(
                            {
                                "filename": matched_file.name,
                                "size_bytes": stat.st_size,
                                "modified_at": stat.st_mtime,
                                "absolute_path": str(res_p),
                                "is_html": is_html,
                                "is_comic": is_comic,
                                "report_type": "comic"
                                if is_comic
                                else ("html" if is_html else "image"),
                                "group_id": g_id or stem,
                                "group_name": g_info.get("group_name", ""),
                                "platform": g_info.get("platform", ""),
                                "trace_id": t_id,
                            }
                        )
                    except Exception:
                        pass

            # 2. Level 2: 若数据库暂无数据（初次升级/外部古老文件），回退磁盘扫描并自愈补录进数据库
            if not reports:
                all_files: list[Path] = []
                for d in candidate_dirs:
                    if not d.exists() or not d.is_dir():
                        continue
                    for p in d.rglob("*"):
                        if (
                            p.is_file()
                            and p.suffix.lower() in valid_exts
                            and not any(
                                part.startswith(".") for part in p.relative_to(d).parts
                            )
                        ):
                            resolved = p.resolve()
                            if resolved not in seen_paths:
                                seen_paths.add(resolved)
                                all_files.append(p)

                report_trace_map: dict[str, str] = {}
                try:
                    report_trace_map = self.trace_store.get_report_trace_map()
                except Exception:
                    pass

                for file_path in sorted(
                    all_files,
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )[:150]:
                    try:
                        stat = file_path.stat()
                        stem = file_path.stem
                        is_html = file_path.suffix.lower() == ".html"
                        is_comic = stem.lower().startswith("comic_") or stem.startswith(
                            "漫画_"
                        )
                        trace_id = report_trace_map.get(file_path.name, "")
                        group_id = ""

                        # 优先通过数据库已登记群号精确匹配
                        for known_gid in sorted(
                            group_info_map.keys(), key=len, reverse=True
                        ):
                            if not known_gid:
                                continue
                            if re.search(
                                rf"(?:^|_){re.escape(known_gid)}(?:_|$)", stem
                            ):
                                group_id = known_gid
                                break

                        # 若未匹配到已知群，按结构化模式解析群号
                        if not group_id:
                            m = re.match(
                                r"^(?:report|群聊分析报告|comic|漫画)_(.+?)_(?:\d{4}-?\d{2}-?\d{2}|\d{8})(?:_\d{6})?(?:_([a-zA-Z0-9_\-]+))?$",
                                stem,
                                re.IGNORECASE,
                            )
                            if m:
                                group_id = m.group(1)
                                if m.group(2) and not trace_id:
                                    cand = m.group(2)
                                    if "_" in cand or len(cand) < 26:
                                        trace_id = cand
                            else:
                                m = re.match(
                                    r"^(?:report|群聊分析报告|comic|漫画)_(.+?)_\d+$",
                                    stem,
                                    re.IGNORECASE,
                                )
                                if m:
                                    group_id = m.group(1)
                                else:
                                    m = re.match(
                                        r"^(?:report|群聊分析报告|comic|漫画)_(.+?)$",
                                        stem,
                                        re.IGNORECASE,
                                    )
                                    group_id = m.group(1) if m else stem

                        if (not group_id or group_id == stem) and (
                            file_path.parent.name in group_info_map
                            or re.match(r"^\d{5,12}$", file_path.parent.name)
                        ):
                            group_id = file_path.parent.name

                        if not trace_id:
                            trace_id = report_trace_map.get(file_path.name, "")
                        if not trace_id:
                            for tid in set(report_trace_map.values()):
                                if tid and tid in stem:
                                    trace_id = tid
                                    break

                        g_info = group_info_map.get(group_id, {})
                        reports.append(
                            {
                                "filename": file_path.name,
                                "size_bytes": stat.st_size,
                                "modified_at": stat.st_mtime,
                                "absolute_path": str(file_path.resolve()),
                                "is_html": is_html,
                                "is_comic": is_comic,
                                "report_type": "comic"
                                if is_comic
                                else ("html" if is_html else "image"),
                                "group_id": group_id,
                                "group_name": g_info.get("group_name", ""),
                                "platform": g_info.get("platform", ""),
                                "trace_id": trace_id,
                            }
                        )

                        # 自愈补录入数据库，使后续查询永久走索引
                        try:
                            fmt = "html" if is_html else "image"
                            self.trace_store.register_report_artifact(
                                filename=file_path.name,
                                group_id=group_id,
                                file_format=fmt,
                                relative_path=file_path.name,
                                created_at=stat.st_mtime,
                                trace_id=trace_id,
                            )
                        except Exception:
                            pass
                    except Exception:
                        pass
            return json_response({"status": "ok", "data": reports})
        except Exception as e:
            logger.error(f"查询历史报告异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_report_content(self) -> WebApiResponse:
        """获取单个历史报告文件（图片或 HTML）的内容用于在线预览与下载"""
        try:
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            filename = str(
                request.query.get("filename") or payload.get("filename") or ""
            ).strip()
            if not filename:
                return error_response("Missing filename parameter", status_code=400)

            query_dto: ReportContentQueryDTO = {"filename": filename}
            safe_filename = Path(query_dto["filename"]).name
            target_file: Path | None = None

            search_dirs = []
            if self.report_output_dir and self.report_output_dir.exists():
                search_dirs.append(self.report_output_dir)
            cfg_mgr = (
                self.analysis_service.config_manager
                if self.analysis_service
                else (
                    self.report_dispatcher.config_manager
                    if self.report_dispatcher
                    else None
                )
            )
            if cfg_mgr:
                custom_html_dir = cfg_mgr.get_html_output_dir() or ""
                if custom_html_dir:
                    p = Path(custom_html_dir)
                    if p.exists() and p not in search_dirs:
                        search_dirs.append(p)

            for d in search_dirs:
                cand = d / safe_filename
                if cand.is_file() and cand.exists():
                    target_file = cand
                    break
                sub_matches = [p for p in d.rglob(safe_filename) if p.is_file()]
                if sub_matches:
                    target_file = sub_matches[0]
                    break

            if not target_file:
                return error_response(
                    f"Report file {safe_filename} not found", status_code=404
                )

            ext = target_file.suffix.lower().lstrip(".")
            is_html = ext == "html"
            stat = target_file.stat()

            if is_html:
                raw_text = target_file.read_text(encoding="utf-8", errors="replace")
                b64_content = base64.b64encode(raw_text.encode("utf-8")).decode("utf-8")
                data_url = f"data:text/html;charset=utf-8;base64,{b64_content}"
                return json_response(
                    {
                        "status": "ok",
                        "data": {
                            "filename": safe_filename,
                            "size_bytes": stat.st_size,
                            "modified_at": stat.st_mtime,
                            "absolute_path": str(target_file.resolve()),
                            "is_html": True,
                            "html_content": raw_text,
                            "data_url": data_url,
                        },
                    }
                )
            mime_type = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
            with open(target_file, "rb") as f:
                b64_content = base64.b64encode(f.read()).decode("utf-8")
            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "filename": safe_filename,
                        "size_bytes": stat.st_size,
                        "modified_at": stat.st_mtime,
                        "absolute_path": str(target_file.resolve()),
                        "is_html": False,
                        "data_url": f"data:{mime_type};base64,{b64_content}",
                    },
                }
            )
        except Exception as e:
            logger.error(f"读取历史报告内容异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_rerender_report(self) -> WebApiResponse:
        """免 Token 切换模板重新渲染历史分析报告"""
        try:
            body = await request.json()
        except Exception:
            body = {}

        group_id = str(
            body.get("group_id") or request.query.get("group_id") or ""
        ).strip()
        date_str = str(
            body.get("date_str") or request.query.get("date_str") or ""
        ).strip()
        template_name = str(
            body.get("template_name")
            or body.get("template")
            or request.query.get("template_name")
            or request.query.get("template")
            or "default"
        ).strip()
        try:
            template_name = validate_template_name(template_name)
        except TemplateInstallError:
            return error_response("模板名包含非法字符。", status_code=400)
        render_format = str(
            body.get("render_format") or request.query.get("render_format") or "image"
        ).strip()
        platform_id = (
            str(body.get("platform_id"))
            if body.get("platform_id") is not None
            else request.query.get("platform_id")
        )
        trace_id = str(
            body.get("trace_id") or request.query.get("trace_id") or ""
        ).strip()

        if not group_id:
            return error_response("缺少群号参数 group_id", status_code=400)
        if not date_str:
            import datetime as _dt

            date_str = _dt.datetime.now().strftime("%Y-%m-%d")

        if not trace_id and self.trace_store:
            try:
                items, _ = self.trace_store.list_traces(group_id=group_id, limit=5)
                if items:
                    trace_id = str(items[0].get("trace_id", ""))
            except Exception:
                pass

        rerender_dto: RerenderReportRequestDTO = {
            "group_id": group_id,
            "date_str": date_str,
            "template_name": template_name,
            "render_format": render_format,
            "platform_id": platform_id,
            "trace_id": trace_id,
        }

        if not self.analysis_service:
            return error_response("分析服务未初始化", status_code=500)

        try:
            result = await self.analysis_service.rerender_report(
                group_id=rerender_dto["group_id"],
                date_str=rerender_dto["date_str"],
                template_name=rerender_dto["template_name"],
                platform_id=rerender_dto.get("platform_id"),
                render_format=rerender_dto["render_format"],
                trace_id=rerender_dto["trace_id"] or None,
            )
            if not result.get("success"):
                return error_response(
                    str(result.get("reason", "重新渲染失败")), status_code=400
                )
            return json_response({"status": "ok", "data": result})
        except Exception as e:
            logger.error(f"重新渲染报告异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)
