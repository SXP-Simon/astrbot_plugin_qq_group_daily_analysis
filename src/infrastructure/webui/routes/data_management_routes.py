"""
WebUI 插件数据与持久化快照管理路由 (Data Management Routes)
处理各分区磁盘存储概览、缓存清理、增量分析批次/游标管理及断点续跑 Checkpoint 状态观测与 CRUD。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from ....shared.constants import PLUGIN_NAME
from ....utils.logger import logger
from ..web_compat import WebApiResponse, error_response, json_response, request

if TYPE_CHECKING:
    from ....application.services.analysis_application_service import (
        AnalysisApplicationService,
    )
    from ...persistence.checkpoint_store import CheckpointStore
    from ...persistence.incremental_store import IncrementalStore
    from ...persistence.trace_sqlite_store import TraceSQLiteStore


class DataManagementRoutes:
    """插件数据管理与持久化观测 Web API 路由处理器。"""

    def __init__(
        self,
        trace_store: TraceSQLiteStore,
        analysis_service: AnalysisApplicationService | None = None,
        report_output_dir: Path | None = None,
    ) -> None:
        self.trace_store = trace_store
        self.analysis_service = analysis_service
        self.report_output_dir = report_output_dir

    @property
    def _incremental_store(self) -> IncrementalStore | None:
        return getattr(self.analysis_service, "incremental_store", None)

    @property
    def _checkpoint_store(self) -> CheckpointStore | None:
        return getattr(self.analysis_service, "checkpoint_store", None)

    def _get_plugin_data_dir(self) -> Path | None:
        """获取 AstrBot 标准 plugin_data 目录（StarTools.get_data_dir）"""
        try:
            from astrbot.api.star import StarTools

            return StarTools.get_data_dir(PLUGIN_NAME)
        except Exception:
            return None

    def _dir_stats(self, directory: Path) -> dict:
        """统计目录下文件数量与总字节数，目录不存在时返回零值。"""
        if not directory.exists():
            return {"count": 0, "size_bytes": 0}
        count = 0
        total = 0
        for p in directory.rglob("*"):
            if p.is_file():
                count += 1
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
        return {"count": count, "size_bytes": total}

    async def api_get_plugin_data_overview(self) -> WebApiResponse:
        """返回各数据分区的文件数量与字节大小概览"""
        try:
            data_dir = self._get_plugin_data_dir()

            # 头像缓存
            avatar_dir = data_dir / "cache" / "avatars" if data_dir else None
            avatar_stats = (
                self._dir_stats(avatar_dir)
                if avatar_dir
                else {"count": 0, "size_bytes": 0}
            )

            # 自定义报告模板
            custom_tmpl_dir = data_dir / "custom_t2i_templates" if data_dir else None
            custom_tmpl_stats = (
                self._dir_stats(custom_tmpl_dir)
                if custom_tmpl_dir
                else {"count": 0, "size_bytes": 0}
            )

            # 上传的配置参考图
            config_files_dir = data_dir / "files" if data_dir else None
            config_files_stats = (
                self._dir_stats(config_files_dir)
                if config_files_dir
                else {"count": 0, "size_bytes": 0}
            )

            # 配置自动备份
            config_backups_dir = data_dir / "config_backups" if data_dir else None
            config_backups_stats = (
                self._dir_stats(config_backups_dir)
                if config_backups_dir
                else {"count": 0, "size_bytes": 0}
            )

            # 历史报告
            report_stats: dict = {"count": 0, "size_bytes": 0}
            if self.report_output_dir and Path(self.report_output_dir).exists():
                report_stats = self._dir_stats(Path(self.report_output_dir))

            # 临时文件（AstrBot 全局 temp 目录下本插件生成的图片）
            temp_stats: dict = {"count": 0, "size_bytes": 0}
            try:
                from astrbot.core.utils.astrbot_path import get_astrbot_temp_path

                temp_dir = Path(get_astrbot_temp_path())
                if temp_dir.exists():
                    count = 0
                    size = 0
                    for f in temp_dir.iterdir():
                        if f.is_file() and f.name.startswith("io_temp_img_"):
                            count += 1
                            try:
                                size += f.stat().st_size
                            except OSError:
                                pass
                    temp_stats = {"count": count, "size_bytes": size}
            except Exception:
                pass

            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "avatars": avatar_stats,
                        "custom_templates": custom_tmpl_stats,
                        "config_files": config_files_stats,
                        "config_backups": config_backups_stats,
                        "reports": report_stats,
                        "temp_files": temp_stats,
                    },
                }
            )
        except Exception as e:
            logger.error(f"获取插件数据概览异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_clear_avatar_cache(self) -> WebApiResponse:
        """清空头像缓存目录"""
        try:
            data_dir = self._get_plugin_data_dir()
            avatar_dir = data_dir / "cache" / "avatars" if data_dir else None
            if not avatar_dir or not avatar_dir.exists():
                return json_response({"status": "ok", "data": {"deleted": 0}})
            deleted = 0
            for f in avatar_dir.iterdir():
                if f.is_file():
                    try:
                        f.unlink()
                        deleted += 1
                    except OSError:
                        pass
            logger.info(f"[plugin-data] 已清空头像缓存，删除 {deleted} 个文件")
            return json_response({"status": "ok", "data": {"deleted": deleted}})
        except Exception as e:
            logger.error(f"清空头像缓存异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_clear_reports(self) -> WebApiResponse:
        """清空历史报告目录（图片与 HTML 文件）"""
        try:
            if not self.report_output_dir:
                return json_response({"status": "ok", "data": {"deleted": 0}})
            report_dir = Path(self.report_output_dir)
            if not report_dir.exists():
                return json_response({"status": "ok", "data": {"deleted": 0}})
            deleted = 0
            for f in report_dir.iterdir():
                if f.is_file() and f.suffix.lower() in {
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp",
                    ".html",
                }:
                    try:
                        f.unlink()
                        deleted += 1
                    except OSError:
                        pass
            logger.info(f"[plugin-data] 已清空历史报告，删除 {deleted} 个文件")
            return json_response({"status": "ok", "data": {"deleted": deleted}})
        except Exception as e:
            logger.error(f"清空历史报告异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_clear_temp_files(self) -> WebApiResponse:
        """清空由本插件产生的临时图片文件（io_temp_img_* 前缀）"""
        try:
            from astrbot.core.utils.astrbot_path import get_astrbot_temp_path

            temp_dir = Path(get_astrbot_temp_path())
            if not temp_dir.exists():
                return json_response({"status": "ok", "data": {"deleted": 0}})
            deleted = 0
            for f in temp_dir.iterdir():
                if f.is_file() and f.name.startswith("io_temp_img_"):
                    try:
                        f.unlink()
                        deleted += 1
                    except OSError:
                        pass
            logger.info(f"[plugin-data] 已清空临时文件，删除 {deleted} 个文件")
            return json_response({"status": "ok", "data": {"deleted": deleted}})
        except Exception as e:
            logger.error(f"清空临时文件异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_clear_custom_templates(self) -> WebApiResponse:
        """清空用户自定义报告模板目录"""
        try:
            data_dir = self._get_plugin_data_dir()
            custom_tmpl_dir = data_dir / "custom_t2i_templates" if data_dir else None
            if not custom_tmpl_dir or not custom_tmpl_dir.exists():
                return json_response({"status": "ok", "data": {"deleted": 0}})
            count = sum(1 for p in custom_tmpl_dir.rglob("*") if p.is_file())
            shutil.rmtree(custom_tmpl_dir, ignore_errors=True)
            custom_tmpl_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[plugin-data] 已清空自定义报告模板，删除 {count} 个文件")
            return json_response({"status": "ok", "data": {"deleted": count}})
        except Exception as e:
            logger.error(f"清空自定义报告模板异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_clear_config_files(self) -> WebApiResponse:
        """清空上传的配置参考图文件"""
        try:
            data_dir = self._get_plugin_data_dir()
            files_dir = data_dir / "files" if data_dir else None
            if not files_dir or not files_dir.exists():
                return json_response({"status": "ok", "data": {"deleted": 0}})
            count = sum(1 for p in files_dir.rglob("*") if p.is_file())
            shutil.rmtree(files_dir, ignore_errors=True)
            files_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[plugin-data] 已清空配置参考图，删除 {count} 个文件")
            return json_response({"status": "ok", "data": {"deleted": count}})
        except Exception as e:
            logger.error(f"清空配置参考图异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_clear_config_backups(self) -> WebApiResponse:
        """清空配置自动备份历史文件"""
        try:
            data_dir = self._get_plugin_data_dir()
            backups_dir = data_dir / "config_backups" if data_dir else None
            if not backups_dir or not backups_dir.exists():
                return json_response({"status": "ok", "data": {"deleted": 0}})
            count = sum(1 for p in backups_dir.rglob("*") if p.is_file())
            shutil.rmtree(backups_dir, ignore_errors=True)
            backups_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[plugin-data] 已清空配置历史自动备份，删除 {count} 个文件")
            return json_response({"status": "ok", "data": {"deleted": count}})
        except Exception as e:
            logger.error(f"清空配置历史自动备份异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_incremental_groups(self) -> WebApiResponse:
        """获取所有拥有增量批次或游标记录的群号列表"""
        try:
            store = self._incremental_store
            tracked: set[str] = set()
            if store and hasattr(store, "get_tracked_groups"):
                tracked.update(await store.get_tracked_groups())

            if self.trace_store:
                for g in self.trace_store.get_distinct_groups():
                    gid = str(g.get("group_id", "")).strip()
                    if gid:
                        tracked.add(gid)

            sorted_groups = sorted(tracked)
            return json_response({"status": "ok", "data": {"groups": sorted_groups}})
        except Exception as e:
            logger.error(f"获取增量群聊列表异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_incremental_batches(self) -> WebApiResponse:
        """获取指定群聊的增量批次列表与当前游标状态"""
        try:
            group_id = request.query.get("group_id", "").strip()
            if not group_id:
                return error_response("Missing group_id parameter", status_code=400)

            store = self._incremental_store
            if not store:
                return error_response(
                    "IncrementalStore not initialized", status_code=503
                )

            batches = await store.get_all_batches_with_details(group_id)
            cursor_ts, cursor_msg_ids = await store.get_last_analyzed_cursor(group_id)

            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "group_id": group_id,
                        "batches": batches,
                        "cursor": {
                            "timestamp": cursor_ts,
                            "tracked_message_ids_count": len(cursor_msg_ids),
                        },
                    },
                }
            )
        except Exception as e:
            logger.error(f"获取增量批次列表异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_incremental_batch_detail(self) -> WebApiResponse:
        """获取单条增量批次完整结构化数据"""
        try:
            group_id = request.query.get("group_id", "").strip()
            batch_id = request.query.get("batch_id", "").strip()
            if not group_id or not batch_id:
                return error_response("Missing group_id or batch_id", status_code=400)

            store = self._incremental_store
            if not store:
                return error_response(
                    "IncrementalStore not initialized", status_code=503
                )

            batch = await store.get_batch_detail(group_id, batch_id)
            if not batch:
                return error_response(
                    f"Batch {batch_id} not found for group {group_id}", status_code=404
                )

            return json_response({"status": "ok", "data": batch.to_dict()})
        except Exception as e:
            logger.error(f"获取增量批次详情异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_delete_incremental_batch(self) -> WebApiResponse:
        """删除指定群的单个增量批次"""
        try:
            payload_raw = await request.json(default={})
            payload: dict[str, object] = (
                payload_raw if isinstance(payload_raw, dict) else {}
            )
            group_id = str(
                payload.get("group_id") or request.query.get("group_id") or ""
            ).strip()
            batch_id = str(
                payload.get("batch_id") or request.query.get("batch_id") or ""
            ).strip()

            if not group_id or not batch_id:
                return error_response("Missing group_id or batch_id", status_code=400)

            store = self._incremental_store
            if not store:
                return error_response(
                    "IncrementalStore not initialized", status_code=503
                )

            deleted = await store.delete_batch(group_id, batch_id)
            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "deleted": deleted,
                        "group_id": group_id,
                        "batch_id": batch_id,
                    },
                }
            )
        except Exception as e:
            logger.error(f"删除增量批次异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_reset_incremental_group(self) -> WebApiResponse:
        """一键清空指定群全部增量批次并将游标归零"""
        try:
            payload_raw = await request.json(default={})
            payload: dict[str, object] = (
                payload_raw if isinstance(payload_raw, dict) else {}
            )
            group_id = str(
                payload.get("group_id") or request.query.get("group_id") or ""
            ).strip()
            if not group_id:
                return error_response("Missing group_id", status_code=400)

            store = self._incremental_store
            if not store:
                return error_response(
                    "IncrementalStore not initialized", status_code=503
                )

            deleted_count = await store.reset_group(group_id)
            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "group_id": group_id,
                        "deleted_batches": deleted_count,
                        "message": f"Successfully reset incremental state for group {group_id}",
                    },
                }
            )
        except Exception as e:
            logger.error(f"重置增量状态异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_list_checkpoints(self) -> WebApiResponse:
        """分页条件查询 Checkpoint 列表"""
        try:
            limit = int(request.query.get("limit", 50))
            offset = int(request.query.get("offset", 0))
            group_id = request.query.get("group_id") or None
            date_str = request.query.get("date_str") or None
            stage_name = request.query.get("stage_name") or None
            trace_id = request.query.get("trace_id") or None

            store = self._checkpoint_store
            if not store:
                return error_response(
                    "CheckpointStore not initialized", status_code=503
                )

            items, total = store.list_all_checkpoints(
                limit=limit,
                offset=offset,
                group_id=group_id,
                date_str=date_str,
                stage_name=stage_name,
                trace_id=trace_id,
            )
            return json_response(
                {"status": "ok", "data": {"items": items, "total": total}}
            )
        except Exception as e:
            logger.error(f"查询 Checkpoint 列表异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_checkpoint_groups(self) -> WebApiResponse:
        """获取所有拥有有效 Checkpoint 的群号列表"""
        try:
            store = self._checkpoint_store
            if not store:
                return error_response(
                    "CheckpointStore not initialized", status_code=503
                )
            groups = store.get_distinct_checkpoint_groups()
            return json_response({"status": "ok", "data": {"groups": groups}})
        except Exception as e:
            logger.error(f"获取 Checkpoint 群号列表异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_checkpoint_detail(self) -> WebApiResponse:
        """获取单条 Checkpoint 产物 JSON 与元数据"""
        try:
            group_id = request.query.get("group_id", "").strip()
            date_str = request.query.get("date_str", "").strip()
            stage_name = request.query.get("stage_name", "").strip()
            trace_id = request.query.get("trace_id", "").strip()

            if not group_id or not date_str or not stage_name:
                return error_response(
                    "group_id, date_str, stage_name are all required", status_code=400
                )

            store = self._checkpoint_store
            if not store:
                return error_response(
                    "CheckpointStore not initialized", status_code=503
                )

            detail = store.get_checkpoint_detail(
                group_id, date_str, stage_name, trace_id=trace_id
            )
            if not detail:
                return error_response(
                    "Checkpoint not found or expired", status_code=404
                )

            return json_response({"status": "ok", "detail": detail, "data": detail})
        except Exception as e:
            logger.error(f"获取 Checkpoint 详情异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_delete_checkpoint(self) -> WebApiResponse:
        """删除指定 Checkpoint 或清空群指定日期所有 Checkpoint"""
        try:
            payload_raw = await request.json(default={})
            payload: dict[str, object] = (
                payload_raw if isinstance(payload_raw, dict) else {}
            )
            group_id = str(
                payload.get("group_id") or request.query.get("group_id") or ""
            ).strip()
            date_str = str(
                payload.get("date_str") or request.query.get("date_str") or ""
            ).strip()
            stage_name = str(
                payload.get("stage_name") or request.query.get("stage_name") or ""
            ).strip()
            trace_id = str(
                payload.get("trace_id") or request.query.get("trace_id") or ""
            ).strip()

            if not group_id or not date_str:
                return error_response(
                    "group_id and date_str are required", status_code=400
                )

            store = self._checkpoint_store
            if not store:
                return error_response(
                    "CheckpointStore not initialized", status_code=503
                )

            if stage_name:
                deleted = store.delete_checkpoint(
                    group_id, date_str, stage_name, trace_id=trace_id
                )
            else:
                store.clear_checkpoints(group_id, date_str)
                deleted = True

            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "deleted": deleted,
                        "group_id": group_id,
                        "date_str": date_str,
                        "stage_name": stage_name or None,
                        "trace_id": trace_id or None,
                    },
                }
            )
        except Exception as e:
            logger.error(f"删除 Checkpoint 异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)
