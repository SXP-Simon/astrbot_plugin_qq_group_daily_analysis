"""
WebUI 插件配置中心路由 (Config Routes)
处理配置读取、Schema 结构下发、配置持久化更新、参考资源文件上传与缩略图获取。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import time
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from ....shared.constants import PLUGIN_NAME
from ....utils.logger import logger
from ...config.config_migrator import LEGACY_RENDERING_RESOURCE_KEYS
from ...config.rendering_config import (
    CUSTOM_RESOURCE_OPTION,
    DEFAULT_RENDERING_STRATEGY_PRESETS,
    parse_rendering_strategies,
)
from ...reporting.cdn_probe import probe_template_cdn
from ..web_compat import WebApiResponse, error_response, json_response, request

if TYPE_CHECKING:
    from collections.abc import Mapping

    from astrbot.api.star import Context

    from ....application.dto.webui_dto import (
        ConfigFileContentQueryDTO,
        ConfigSaveDTO,
    )
    from ....application.services.analysis_application_service import (
        AnalysisApplicationService,
    )
    from ...reporting.dispatcher import ReportDispatcher
    from ...scheduler.auto_scheduler import AutoScheduler


def _sanitize_path_segment(segment: str) -> str:
    cleaned = []
    for ch in segment:
        if ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ch.isdigit() or ch in {"-", "_"}:
            cleaned.append(ch)
        else:
            cleaned.append("_")
    result = "".join(cleaned).strip("_")
    return result or "_"


def _config_key_to_folder(key_path: str) -> str:
    """与 AstrBot 官方核心完全一致的 config_key 到存储目录转换规则（以 / 分隔）"""
    parts = [_sanitize_path_segment(part) for part in key_path.split(".") if part]
    return "/".join(parts) if parts else "_"


def _config_revision(config: Mapping[str, object]) -> str:
    """计算配置内容的只读版本，不将版本号写入用户配置。

    Args:
        config: 来自配置文件的 JSON 对象。

    Returns:
        配置内容稳定排序后的 SHA-256 摘要。

    Raises:
        TypeError: 配置包含不可序列化的数据。
    """
    content = json.dumps(
        dict(config), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class ConfigRoutes:
    """插件配置中心 Web API 路由处理器。"""

    analysis_service: AnalysisApplicationService | None
    report_dispatcher: ReportDispatcher | None
    context: Context | None
    auto_scheduler: AutoScheduler | None

    def __init__(
        self,
        analysis_service: AnalysisApplicationService | None,
        report_dispatcher: ReportDispatcher | None = None,
        context: Context | None = None,
        auto_scheduler: AutoScheduler | None = None,
    ) -> None:
        self.analysis_service = analysis_service
        self.report_dispatcher = report_dispatcher
        self.context = context
        self.auto_scheduler = auto_scheduler

    async def api_get_config(self) -> WebApiResponse:
        """获取插件当前配置数据与完整 Schema 结构定义"""
        try:
            cfg_mgr = (
                self.analysis_service.config_manager
                if self.analysis_service
                else (
                    self.report_dispatcher.config_manager
                    if self.report_dispatcher
                    else None
                )
            )
            config_dict = {}
            revision = _config_revision(config_dict)
            if cfg_mgr:
                cfg_mgr.refresh_rendering_schema_options()
                config_dict = {str(k): v for k, v in cfg_mgr.config.items()}
                revision = _config_revision(config_dict)
                rendering = config_dict.get("t2i_rendering")
                if isinstance(rendering, dict):
                    raw = rendering.get("t2i_rendering_strategies") or list(
                        DEFAULT_RENDERING_STRATEGY_PRESETS
                    )
                    try:
                        # 只补齐编辑视图，不写盘；保留顺序和扩展字段，迁移服务条目类型。
                        projected = []
                        if not isinstance(raw, list):
                            raise ValueError("渲染方案必须是列表")
                        for item in raw:
                            normalized = parse_rendering_strategies([item])[0]
                            projected_item = {**item, **normalized}
                            projected_item.pop("render_service", None)
                            # 自定义方案的空地址表示跟随资源环境，编辑与保存均保留此意图。
                            if normalized["render_service"] == "custom":
                                for key in ("cdn_base_url", "google_fonts", "gstatic"):
                                    if item.get(key) == "":
                                        projected_item[key] = ""
                            projected.append(projected_item)
                        config_dict["t2i_rendering"] = {
                            **rendering,
                            "t2i_rendering_strategies": projected,
                        }
                    except ValueError:
                        # 异常草稿原样交给编辑器，避免读取时吞掉用户配置。
                        pass

            plugin_root = Path(__file__).resolve().parents[4]
            schema_file = plugin_root / "_conf_schema.json"
            if not schema_file.exists():
                for candidate in [
                    Path.cwd() / "_conf_schema.json",
                    Path(__file__).resolve().parents[3] / "_conf_schema.json",
                    Path(__file__).resolve().parents[2] / "_conf_schema.json",
                    Path(__file__).resolve().parents[1] / "_conf_schema.json",
                ]:
                    if candidate.exists():
                        schema_file = candidate
                        break

            schema_dict = {}
            if schema_file.exists():
                try:
                    schema_dict = json.loads(schema_file.read_text(encoding="utf-8"))
                except Exception as e:
                    logger.warning(f"读取 _conf_schema.json 失败: {e}")

            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "config": config_dict,
                        "schema": schema_dict,
                        "revision": revision,
                    },
                }
            )
        except Exception as e:
            logger.error(f"获取配置信息异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_test_template_cdn(self) -> WebApiResponse:
        """检测输入的 CDN 地址，不保存配置。

        Returns:
            各文件的检测结果；输入无效时返回 400。
        """
        try:
            body = await request.json()
            base_url = body.get("base_url")
            if not isinstance(base_url, str) or len(base_url) > 2048:
                return error_response(
                    "base_url 必须是长度不超过 2048 的字符串", status_code=400
                )
            result = await probe_template_cdn(base_url)
            return json_response({"status": "ok", "data": result})
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        except Exception as exc:
            logger.error(f"模板 CDN 检测异常: {exc}", exc_info=True)
            return error_response("这次检测没能完成，请稍后再试。", status_code=500)

    async def api_save_config(self) -> WebApiResponse:
        """保存并更新插件配置"""
        try:
            try:
                body = await request.json()
            except Exception:
                body = {}
            new_config = body.get("config")
            if not isinstance(new_config, dict):
                return error_response("缺少有效的 config 配置数据", status_code=400)

            save_dto: ConfigSaveDTO = {"config": new_config}
            if "revision" in body:
                revision = body["revision"]
                if not isinstance(revision, str) or not re.fullmatch(
                    r"[0-9a-f]{64}", revision
                ):
                    return error_response(
                        "配置版本无效，请重新读取后再保存", status_code=400
                    )
                save_dto["revision"] = revision

            cfg_mgr = (
                self.analysis_service.config_manager
                if self.analysis_service
                else (
                    self.report_dispatcher.config_manager
                    if self.report_dispatcher
                    else None
                )
            )
            config_obj = cfg_mgr.config if cfg_mgr else None
            if config_obj is None:
                return error_response("配置管理器未初始化", status_code=500)

            # 比较、更新和同步保存之间没有 await，避免两个页面同时覆盖旧快照。
            if "revision" in save_dto and save_dto["revision"] != _config_revision(
                config_obj
            ):
                return error_response(
                    "配置已被其他页面修改，请重新读取后再保存。当前改动尚未保存。",
                    status_code=409,
                )

            if "t2i_rendering" in new_config:
                rendering_config = new_config["t2i_rendering"]
                if not isinstance(rendering_config, dict):
                    return error_response(
                        "t2i_rendering 必须是配置对象", status_code=400
                    )
                if "t2i_rendering_strategies" in rendering_config:
                    try:
                        strategies = rendering_config["t2i_rendering_strategies"]
                        if strategies == []:
                            strategies = [
                                dict(item)
                                for item in DEFAULT_RENDERING_STRATEGY_PRESETS
                            ]
                            rendering_config["t2i_rendering_strategies"] = strategies
                        if not isinstance(strategies, list):
                            raise ValueError("渲染方案必须是列表")
                        priorities: list[int] = []
                        for strategy in strategies:
                            normalized = parse_rendering_strategies([strategy])[0]
                            priorities.append(normalized["priority"])
                            for key in ("cdn_base_url", "google_fonts", "gstatic"):
                                if strategy.get(key) == CUSTOM_RESOURCE_OPTION:
                                    strategy[f"custom_{key}"] = normalized[key]
                                if (
                                    normalized["render_service"] == "custom"
                                    and strategy.get(key) == ""
                                ):
                                    continue
                                strategy[key] = normalized[key]
                            for key in (
                                "__template_key",
                                "environment",
                                "service_endpoint",
                                "service_token",
                            ):
                                strategy[key] = normalized[key]
                            if "request_timeout" in normalized:
                                strategy["request_timeout"] = normalized[
                                    "request_timeout"
                                ]
                            strategy.pop("render_service", None)
                        strategies[:] = [
                            item
                            for _priority, item in sorted(
                                zip(priorities, strategies, strict=True),
                                key=lambda pair: pair[0],
                            )
                        ]
                    except ValueError as exc:
                        return error_response(str(exc), status_code=400)
                for legacy_key in LEGACY_RENDERING_RESOURCE_KEYS:
                    rendering_config.pop(legacy_key, None)

            daily_comic_config = new_config.get("daily_comic")
            if isinstance(daily_comic_config, dict):
                daily_comic_config.pop("drawing_reference_image", None)

            auto_analysis_config = new_config.get("auto_analysis")
            if isinstance(auto_analysis_config, dict) and (
                "auto_analysis_time" in auto_analysis_config
            ):
                configured_times = auto_analysis_config["auto_analysis_time"]
                if isinstance(configured_times, str):
                    configured_times = [configured_times]
                if not isinstance(configured_times, list):
                    return error_response(
                        "自动分析时间必须是 HH:MM 格式的字符串列表",
                        status_code=400,
                    )
                for time_value in configured_times:
                    if not isinstance(time_value, str):
                        return error_response(
                            "自动分析时间必须是 HH:MM 格式的字符串列表",
                            status_code=400,
                        )
                    normalized_time = time_value.replace("：", ":").strip()
                    if not re.fullmatch(r"[0-9]{1,2}:[0-9]{1,2}", normalized_time):
                        return error_response(
                            f"无效的自动分析时间：{time_value}，请使用 HH:MM 格式",
                            status_code=400,
                        )
                    hour, minute = map(int, normalized_time.split(":"))
                    if hour > 23 or minute > 59:
                        return error_response(
                            f"无效的自动分析时间：{time_value}，有效范围为 00:00-23:59",
                            status_code=400,
                        )

            plugin_root = Path(__file__).resolve().parents[4]

            def _cleanse_reference_images(val: object, config_key: str = "") -> object:
                """仅清洗漫画角色与参考图，其他动态配置保持原样。

                Args:
                    val: 待保存的配置节点。
                    config_key: 当前节点的配置路径。

                Returns:
                    清洗后的配置节点。
                """
                if isinstance(val, list):
                    if config_key not in (
                        "daily_comic.comic_characters",
                        "daily_comic.comic_characters.reference_images",
                    ):
                        return val
                    cleaned = []
                    for item in val:
                        if isinstance(item, dict):
                            cleaned_item = _cleanse_reference_images(item, config_key)
                            if (
                                config_key == "daily_comic.comic_characters"
                                and isinstance(cleaned_item, dict)
                                and (
                                    "__template_key" not in cleaned_item
                                    or not cleaned_item["__template_key"]
                                )
                            ):
                                cleaned_item["__template_key"] = "character"
                            cleaned.append(cleaned_item)
                        elif isinstance(item, str) and config_key.endswith(
                            ".reference_images"
                        ):
                            folder = _config_key_to_folder(
                                "daily_comic.comic_characters.templates.character.reference_images"
                            )
                            if item.startswith("data:image/"):
                                try:
                                    _, b64 = item.split(",", 1)
                                    file_bytes = base64.b64decode(b64)
                                    ts = int(time.time() * 1000)
                                    filename = f"{ts}_migrated_image.png"
                                    for d in [
                                        Path.cwd()
                                        / "data"
                                        / "plugin_data"
                                        / PLUGIN_NAME
                                        / "files"
                                        / Path(folder),
                                        plugin_root / "files" / Path(folder),
                                    ]:
                                        d.mkdir(parents=True, exist_ok=True)
                                        (d / filename).write_bytes(file_bytes)
                                    cleaned.append(f"files/{folder}/{filename}")
                                except Exception:
                                    pass
                            elif item.startswith("files/"):
                                expected_prefix = f"files/{folder}/"
                                if item.startswith(expected_prefix):
                                    cleaned.append(item.strip())
                                else:
                                    clean_name = Path(item).name
                                    cleaned.append(f"files/{folder}/{clean_name}")
                            elif item.strip():
                                cleaned.append(item.strip())
                        else:
                            cleaned.append(item)
                    return cleaned
                if isinstance(val, dict):
                    return {
                        k: _cleanse_reference_images(
                            v, f"{config_key}.{k}" if config_key else k
                        )
                        for k, v in val.items()
                    }
                return val

            cleansed = _cleanse_reference_images(save_dto["config"])
            if isinstance(cleansed, dict):
                for k, v in cleansed.items():
                    config_obj[k] = v

            if cfg_mgr:
                cfg_mgr.save_config()

            saved_revision = _config_revision(config_obj)

            if self.auto_scheduler is not None and self.context is not None:
                self.auto_scheduler.schedule_jobs(self.context)
                if self.auto_scheduler.incremental_trigger is not None:
                    await (
                        self.auto_scheduler.incremental_trigger.refresh_target_states()
                    )

            logger.info("WebUI 配置中心已更新并保存插件配置。")
            return json_response(
                {
                    "status": "ok",
                    "message": "配置已成功保存并持久化生效",
                    "revision": saved_revision,
                    "data": dict(config_obj),
                }
            )
        except Exception as e:
            logger.error(f"保存配置异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_upload_config_file(self) -> WebApiResponse:
        """上传插件配置所需的文件/参考图，并存入合规的 files/{folder}/ 物理路径"""
        try:
            try:
                body = await request.json()
            except Exception:
                body = {}

            config_key = request.query.get("config_key", "")
            if not config_key and body.get("config_key"):
                config_key = str(body.get("config_key"))

            if not config_key or config_key == "reference_images":
                config_key = (
                    "daily_comic.comic_characters.templates.character.reference_images"
                )

            folder = _config_key_to_folder(config_key)

            target_dirs: list[Path] = []
            try:
                from astrbot.api.star import StarTools

                data_dir = StarTools.get_data_dir(PLUGIN_NAME)
                if data_dir:
                    target_dirs.append(data_dir / "files" / Path(folder))
            except Exception:
                pass

            target_dirs.append(
                Path.cwd()
                / "data"
                / "plugin_data"
                / PLUGIN_NAME
                / "files"
                / Path(folder)
            )
            plugin_root = Path(__file__).resolve().parents[4]
            target_dirs.append(plugin_root / "files" / Path(folder))

            for d in target_dirs:
                d.mkdir(parents=True, exist_ok=True)

            saved_paths: list[str] = []

            req_files = getattr(request, "files", None)
            if req_files is not None:
                try:
                    uploaded_files: object
                    if callable(req_files):
                        res_files = req_files()
                        uploaded_files = (
                            await res_files
                            if asyncio.iscoroutine(res_files)
                            else res_files
                        )
                    else:
                        uploaded_files = req_files

                    getlist_fn = getattr(uploaded_files, "getlist", None)
                    if callable(getlist_fn) and isinstance(uploaded_files, Iterable):
                        for key in uploaded_files:
                            file_items = getlist_fn(key)
                            if isinstance(file_items, list):
                                for f in file_items:
                                    orig_name = (
                                        getattr(f, "filename", "")
                                        or "uploaded_image.png"
                                    )
                                    clean_name = re.sub(
                                        r"[^\w\.\-]", "_", str(orig_name)
                                    )
                                    ts = int(time.time() * 1000)
                                    final_name = f"{ts}_{clean_name}"
                                    read_fn = getattr(f, "read", None)
                                    if callable(read_fn):
                                        res_read = read_fn()
                                        file_bytes = (
                                            await res_read
                                            if asyncio.iscoroutine(res_read)
                                            else res_read
                                        )
                                    else:
                                        file_bytes = None
                                    if isinstance(file_bytes, bytes):
                                        for d in target_dirs:
                                            (d / final_name).write_bytes(file_bytes)
                                        saved_paths.append(
                                            f"files/{folder}/{final_name}"
                                        )
                except Exception:
                    pass

            if not saved_paths and body:
                raw_data = (
                    body.get("file_data") or body.get("data") or body.get("base64")
                )
                file_name = str(body.get("filename") or "upload.png")
                clean_name = re.sub(r"[^\w\.\-]", "_", file_name)
                if raw_data and isinstance(raw_data, str):
                    if raw_data.startswith("data:"):
                        _, b64 = raw_data.split(",", 1)
                    else:
                        b64 = raw_data
                    file_bytes = base64.b64decode(b64)
                    ts = int(time.time() * 1000)
                    final_name = f"{ts}_{clean_name}"
                    for d in target_dirs:
                        (d / final_name).write_bytes(file_bytes)
                    saved_paths.append(f"files/{folder}/{final_name}")

            if not saved_paths:
                return error_response("未检测到有效的文件数据", status_code=400)

            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "path": saved_paths[0],
                        "paths": saved_paths,
                        "folder": folder,
                    },
                }
            )
        except Exception as e:
            logger.error(f"上传配置文件异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_config_file_content(self) -> WebApiResponse:
        """获取配置中的文件（如角色参考图）内容用于 WebUI 在线缩略图展示"""
        try:
            rel_path = request.query.get("path", "").strip()

            if not rel_path:
                try:
                    body = await request.json()
                    rel_path = str(body.get("path") or "").strip()
                except Exception:
                    pass

            if not rel_path:
                return error_response("Missing path parameter", status_code=400)

            query_dto: ConfigFileContentQueryDTO = {"path": rel_path}

            search_roots: list[Path] = []
            try:
                from astrbot.api.star import StarTools

                data_dir = StarTools.get_data_dir(PLUGIN_NAME)
                if data_dir:
                    search_roots.append(data_dir)
            except Exception:
                pass

            search_roots.append(Path.cwd() / "data" / "plugin_data" / PLUGIN_NAME)
            plugin_root = Path(__file__).resolve().parents[4]
            search_roots.append(plugin_root)
            search_roots.append(Path.cwd() / "data" / "plugins" / PLUGIN_NAME)

            target_file: Path | None = None
            clean_rel = query_dto["path"].lstrip("/\\")
            for root in search_roots:
                cand = (root / clean_rel).resolve()
                if cand.is_file() and cand.exists():
                    target_file = cand
                    break

            if not target_file:
                filename = Path(clean_rel).name
                for root in search_roots:
                    files_dir = root / "files"
                    if files_dir.exists():
                        for match in files_dir.rglob(filename):
                            if match.is_file():
                                target_file = match
                                break
                    if target_file:
                        break

            if not target_file or not target_file.is_file():
                return error_response(
                    f"File {query_dto['path']} not found", status_code=404
                )

            ext = target_file.suffix.lower().lstrip(".")
            mime_type = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
            with open(target_file, "rb") as f:
                b64_content = base64.b64encode(f.read()).decode("utf-8")

            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "path": query_dto["path"],
                        "filename": target_file.name,
                        "data_url": f"data:{mime_type};base64,{b64_content}",
                    },
                }
            )
        except Exception as e:
            logger.error(f"获取配置文件内容异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)
