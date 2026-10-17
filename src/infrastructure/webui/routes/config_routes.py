"""
WebUI 插件配置中心路由 (Config Routes)
处理配置读取、Schema 结构下发、配置持久化更新、参考资源文件上传与缩略图获取。
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import time
from collections.abc import Iterable, Mapping
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

from astrbot.api.star import StarTools

from ....shared.comic_prompts import COMIC_STORYBOARD_PROMPTS
from ....shared.constants import PLUGIN_NAME
from ....utils.cdn_utils import normalize_cdn_base_url
from ....utils.logger import logger
from ...reporting.cdn_probe import probe_template_cdn
from ...reporting.wordcloud_renderer import WordCloudRenderer
from ..web_compat import WebApiResponse, error_response, json_response, request

if TYPE_CHECKING:
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


def validate_comic_template_rotation_config(config: Mapping[str, object]) -> None:
    """校验漫画模板轮换配置，兼容没有新增字段的旧配置。

    Args:
        config: 将要保存的完整有效配置。

    Raises:
        ValueError: 模式、范围或候选模板配置不合法。
    """
    daily = config.get("daily_comic", {})
    if not isinstance(daily, dict):
        raise ValueError("每日漫画配置必须是对象")
    mode = daily.get("comic_template_mode", "fixed")
    if not isinstance(mode, str) or mode not in {
        "fixed",
        "sequential",
        "daily_sequential",
        "random",
        "daily_random",
        "shuffle",
    }:
        raise ValueError("漫画模板切换模式无效")
    scope = daily.get("comic_template_scope", "global")
    if not isinstance(scope, str) or scope not in {"global", "group"}:
        raise ValueError("漫画模板切换范围无效")
    candidates = daily.get("comic_template_candidates", list(COMIC_STORYBOARD_PROMPTS))
    if not isinstance(candidates, list) or any(
        not isinstance(item, str) for item in candidates
    ):
        raise ValueError("漫画模板候选池必须是模板标识列表")
    if len(candidates) != len(set(candidates)):
        raise ValueError("漫画模板候选池不能包含重复模板")
    if any(
        item not in COMIC_STORYBOARD_PROMPTS and item != "custom" for item in candidates
    ):
        raise ValueError("漫画模板候选池包含未知模板")
    if mode != "fixed" and not candidates:
        raise ValueError("启用漫画模板切换时，候选池至少需要一个模板")
    if mode != "fixed" and "custom" in candidates:
        prompts = config.get("prompts", {})
        comic_prompts = (
            prompts.get("comic_analysis_prompts", {})
            if isinstance(prompts, dict)
            else {}
        )
        custom = (
            comic_prompts.get("comic_storyboard_prompt", "")
            if isinstance(comic_prompts, dict)
            else ""
        )
        if not isinstance(custom, str) or not custom.strip():
            raise ValueError("候选池包含自定义模板时，必须填写自定义漫画场景分析提示词")


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
        wordcloud_renderer: WordCloudRenderer | None = None,
        resource_lock: asyncio.Lock | None = None,
    ) -> None:
        self.analysis_service = analysis_service
        self.report_dispatcher = report_dispatcher
        self.context = context
        self.auto_scheduler = auto_scheduler
        self.wordcloud_renderer = wordcloud_renderer
        self._wordcloud_resource_lock = (
            resource_lock if resource_lock is not None else asyncio.Lock()
        )

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
            if cfg_mgr:
                config_dict = {str(k): v for k, v in cfg_mgr.config.items()}

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

            if "basic" in new_config:
                basic = new_config["basic"]
                if not isinstance(basic, dict):
                    return error_response("基础设置必须是对象", status_code=400)
                if (
                    "enable_merged_forward" in basic
                    and type(basic["enable_merged_forward"]) is not bool
                ):
                    return error_response("合并转发开关必须为布尔值", status_code=400)
                if "merged_forward_timeout" in basic:
                    timeout = basic["merged_forward_timeout"]
                    if type(timeout) is not int or not 10 <= timeout <= 3600:
                        return error_response(
                            "合并转发等待超时必须为 10–3600 秒的整数",
                            status_code=400,
                        )

            wordcloud: dict[str, object] | None = None
            if "wordcloud" in new_config:
                raw_wordcloud = new_config["wordcloud"]
                if not isinstance(raw_wordcloud, dict):
                    return error_response("词云配置必须是对象", status_code=400)
                wordcloud = raw_wordcloud

            if "t2i_rendering" in new_config:
                rendering_config = new_config["t2i_rendering"]
                if not isinstance(rendering_config, dict):
                    return error_response(
                        "t2i_rendering 必须是配置对象", status_code=400
                    )
                if "t2i_cdn_base_url" in rendering_config:
                    cdn_value = rendering_config["t2i_cdn_base_url"]
                    if not isinstance(cdn_value, str) or len(cdn_value) > 2048:
                        return error_response(
                            "CDN 地址必须是长度不超过 2048 的字符串", status_code=400
                        )
                    try:
                        rendering_config["t2i_cdn_base_url"] = (
                            normalize_cdn_base_url(cdn_value)
                            if cdn_value.strip()
                            else ""
                        )
                    except ValueError as exc:
                        return error_response(str(exc), status_code=400)

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

            async with self._wordcloud_resource_lock:
                # 与持久化共用锁，防止并发保存后使用过期的提示词校验候选池。
                effective_config = {**dict(config_obj), **new_config}
                try:
                    validate_comic_template_rotation_config(effective_config)
                except ValueError as exc:
                    return error_response(str(exc), status_code=400)

                if wordcloud is not None:
                    if self.wordcloud_renderer is None:
                        # 兼容旧装配入口，但仍使用正式目录进行资源校验。
                        assert cfg_mgr is not None
                        self.wordcloud_renderer = WordCloudRenderer(
                            cfg_mgr, StarTools.get_data_dir(PLUGIN_NAME)
                        )
                    try:
                        await asyncio.to_thread(
                            self.wordcloud_renderer.validate_config_resources, wordcloud
                        )
                    except ValueError as exc:
                        return error_response(str(exc), status_code=400)

                plugin_root = Path(__file__).resolve().parents[4]

                def _cleanse_reference_images(
                    val: object, config_key: str = ""
                ) -> object:
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
                                cleaned_item = _cleanse_reference_images(
                                    item, config_key
                                )
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
                previous_config = deepcopy(dict(config_obj))
                try:
                    if isinstance(cleansed, dict):
                        config_obj.update(cleansed)
                    if cfg_mgr:
                        cfg_mgr.save_config()
                except Exception:
                    # 在保存锁内恢复，既保留配置对象引用，也移除本次新增的键。
                    config_obj.clear()
                    config_obj.update(previous_config)
                    raise

            if self.auto_scheduler is not None and self.context is not None:
                self.auto_scheduler.schedule_jobs(self.context)
                if self.auto_scheduler.incremental_trigger is not None:
                    await (
                        self.auto_scheduler.incremental_trigger.refresh_target_states()
                    )

            logger.info("WebUI 配置中心已更新并保存插件配置。")
            # 宿主 Page Bridge 会优先转发响应的 data，成功回执必须在解包后仍然存在。
            return json_response(
                {
                    "status": "ok",
                    "message": "配置已成功保存并持久化生效",
                    "data": {
                        "status": "ok",
                        "message": "配置已成功保存并持久化生效",
                        "config": dict(config_obj),
                    },
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
