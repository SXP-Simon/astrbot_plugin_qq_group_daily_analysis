"""
WebUI 插件数据与持久化快照管理路由 (Data Management Routes)
处理各分区磁盘存储概览、缓存清理、增量分析批次/游标管理及断点续跑 Checkpoint 状态观测与 CRUD。
"""

from __future__ import annotations

import asyncio
import shutil
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from ....application.services.task_guard import DuplicateGroupTaskError
from ....domain.value_objects.group_session import GroupSession
from ....shared.constants import PLUGIN_NAME
from ....utils.logger import logger
from ...config.config_backup_reader import ConfigBackupReader
from ..web_compat import WebApiResponse, error_response, json_response, request

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from ....application.dto.webui_dto import (
        CheckpointDeleteDTO,
        CheckpointDetailQueryDTO,
        CheckpointListQueryDTO,
        IncrementalBatchDeleteDTO,
        IncrementalBatchDetailQueryDTO,
        IncrementalBatchesQueryDTO,
        IncrementalResetDTO,
    )
    from ....application.services.analysis_application_service import (
        AnalysisApplicationService,
    )
    from ....domain.repositories.persistence_repository import (
        ICheckpointStore,
        IIncrementalStore,
    )
    from ...persistence.trace_sqlite_store import TraceSQLiteStore


class IncrementalGroupDirectoryItemDTO(TypedDict):
    """按平台实例隔离的增量群聊目录。"""

    group_id: str
    platform_id: str
    group_name: str


class DirectoryStatsDTO(TypedDict):
    """目录存储统计契约"""

    count: int
    size_bytes: int


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

    @asynccontextmanager
    async def _mutation_guard(self, group_id: str) -> AsyncGenerator[None, None]:
        """删除批次、重置游标和清理快照时，与群分析任务互斥。

        Args:
            group_id: 正在管理的存储群标识。

        Yields:
            None: 已持有相关群任务锁。

        Raises:
            DuplicateGroupTaskError: 群任务仍在执行。
        """
        async with AsyncExitStack() as stack:
            if self.analysis_service:
                for task_type in ("daily", "incremental", "final"):
                    await stack.enter_async_context(
                        self.analysis_service.group_lock(group_id, task_type)
                    )
            yield

    @property
    def _incremental_store(self) -> IIncrementalStore | None:
        return (
            self.analysis_service.incremental_store if self.analysis_service else None
        )

    @property
    def _checkpoint_store(self) -> ICheckpointStore | None:
        return self.analysis_service.checkpoint_store if self.analysis_service else None

    def _get_plugin_data_dir(self) -> Path | None:
        """获取 AstrBot 标准 plugin_data 目录（StarTools.get_data_dir）"""
        try:
            from astrbot.api.star import StarTools

            return StarTools.get_data_dir(PLUGIN_NAME)
        except Exception:
            return None

    def _dir_stats(self, directory: Path) -> DirectoryStatsDTO:
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
            avatar_dir = data_dir / "avatar" if data_dir else None
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
            report_stats: DirectoryStatsDTO = {"count": 0, "size_bytes": 0}
            if self.report_output_dir and Path(self.report_output_dir).exists():
                report_stats = self._dir_stats(Path(self.report_output_dir))

            # 宿主 io_temp_img_* 不包含插件归属，不统计或清理共享临时文件。
            temp_stats: DirectoryStatsDTO = {"count": 0, "size_bytes": 0}
            if data_dir:
                temp_stats = self._dir_stats(data_dir / "template_preview_cache")

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
            avatar_dir = data_dir / "avatar" if data_dir else None
            if not avatar_dir or not avatar_dir.exists():
                return json_response({"status": "ok", "data": {"deleted": 0}})
            from diskcache import Cache

            with Cache(str(avatar_dir)) as cache:
                deleted = await asyncio.to_thread(cache.clear)
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
        return error_response(
            "宿主临时文件无法按插件区分，请在文件与素材管理中逐项清理插件预览缓存",
            status_code=400,
        )

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

    async def api_get_config_backups(self) -> WebApiResponse:
        """列出只读配置备份及文件内的版本、时间。"""
        data_dir = self._get_plugin_data_dir()
        if data_dir is None:
            return error_response("插件数据目录尚不可用", status_code=503)
        try:
            items = await asyncio.to_thread(
                ConfigBackupReader(data_dir / "config_backups").list_backups
            )
            return json_response({"status": "ok", "data": {"items": items}})
        except OSError:
            return error_response("暂时无法读取配置备份目录", status_code=500)

    async def api_get_config_backup(self) -> WebApiResponse:
        """读取列表中一份备份的原始 JSON。"""
        data_dir = self._get_plugin_data_dir()
        if data_dir is None:
            return error_response("插件数据目录尚不可用", status_code=503)
        filename = request.query.get("filename", "")
        try:
            detail = await asyncio.to_thread(
                ConfigBackupReader(data_dir / "config_backups").read, filename
            )
            return json_response({"status": "ok", "data": detail})
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        except FileNotFoundError:
            return error_response("这份备份已不存在，请刷新列表", status_code=404)
        except OSError:
            return error_response("暂时无法读取这份备份", status_code=500)

    async def api_get_incremental_groups(self) -> WebApiResponse:
        """获取所有拥有增量批次或游标记录的群号列表"""
        try:
            store = self._incremental_store
            history = await asyncio.to_thread(
                self.trace_store.get_distinct_groups, by_session=True
            )
            sessions: set[GroupSession] = (
                set(await store.get_tracked_sessions()) if store else set()
            )
            # 旧键不包含平台；按升级前群号未碰撞的约定，归属最近一次已记录的平台。
            legacy = [session for session in sessions if not session.platform_id]
            if store and legacy:
                latest = {
                    item["group_id"]: item
                    for item in await asyncio.to_thread(
                        self.trace_store.get_distinct_groups
                    )
                }
                for session in legacy:
                    platform = latest.get(session.group_id, {}).get("platform", "")
                    if platform:
                        await store.for_session(session.group_id, platform)
                sessions = set(await store.get_tracked_sessions())
            names = {
                GroupSession(item["platform"], item["group_id"]): item["group_name"]
                for item in history
                if item["group_id"]
            }
            sessions.update(names)
            sorted_groups = sorted({session.group_id for session in sessions})
            details: list[IncrementalGroupDirectoryItemDTO] = [
                {
                    "group_id": session.group_id,
                    "platform_id": session.platform_id,
                    "group_name": names.get(session, ""),
                }
                for session in sorted(sessions)
            ]
            return json_response(
                {
                    "status": "ok",
                    "data": {"groups": sorted_groups, "group_details": details},
                }
            )
        except Exception as e:
            logger.error(f"获取增量群聊列表异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_incremental_batches(self) -> WebApiResponse:
        """获取指定群聊的增量批次列表与当前游标状态"""
        try:
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            group_id = str(
                request.query.get("group_id") or payload.get("group_id") or ""
            ).strip()
            if not group_id:
                return error_response("Missing group_id parameter", status_code=400)

            try:
                page = max(
                    1, int(str(request.query.get("page") or payload.get("page") or 1))
                )
                page_size = min(
                    100,
                    max(
                        1,
                        int(
                            str(
                                request.query.get("page_size")
                                or payload.get("page_size")
                                or 20
                            )
                        ),
                    ),
                )
            except (TypeError, ValueError):
                return error_response("页码和每页数量必须是整数", status_code=400)
            platform_id = str(
                request.query.get("platform_id") or payload.get("platform_id") or ""
            ).strip()
            query_dto: IncrementalBatchesQueryDTO = {
                "group_id": group_id,
                "platform_id": platform_id,
            }

            store = self._incremental_store
            if not store:
                return error_response(
                    "IncrementalStore not initialized", status_code=503
                )

            store = await store.for_session(group_id, platform_id)
            result = await store.list_batch_page(query_dto["group_id"], page, page_size)
            cursor_ts, cursor_msg_ids = await store.get_last_analyzed_cursor(
                query_dto["group_id"]
            )

            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "group_id": group_id,
                        "platform_id": platform_id,
                        "batches": result.items,
                        "total": result.total,
                        "page": result.page,
                        "page_size": result.page_size,
                        "cursor": {
                            "timestamp": cursor_ts,
                            "group_id": group_id,
                            "last_analyzed_timestamp": cursor_ts or 0,
                            "last_message_timestamp": result.last_message_timestamp,
                            "tracked_message_ids_count": len(cursor_msg_ids),
                        },
                    },
                }
            )
        except ValueError as e:
            return error_response(str(e), status_code=400)
        except Exception as e:
            logger.error(f"获取增量批次列表异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_incremental_batch_detail(self) -> WebApiResponse:
        """获取单条增量批次完整结构化数据"""
        try:
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            group_id = str(
                request.query.get("group_id") or payload.get("group_id") or ""
            ).strip()
            batch_id = str(
                request.query.get("batch_id") or payload.get("batch_id") or ""
            ).strip()
            if not group_id or not batch_id:
                return error_response("Missing group_id or batch_id", status_code=400)

            platform_id = str(
                request.query.get("platform_id") or payload.get("platform_id") or ""
            ).strip()
            query_dto: IncrementalBatchDetailQueryDTO = {
                "platform_id": platform_id,
                "group_id": group_id,
                "batch_id": batch_id,
            }

            store = self._incremental_store
            if not store:
                return error_response(
                    "IncrementalStore not initialized", status_code=503
                )

            store = await store.for_session(group_id, platform_id)
            batch = await store.get_batch_detail(
                query_dto["group_id"], query_dto["batch_id"]
            )
            if not batch:
                return error_response(
                    f"Batch {batch_id} not found for group {group_id}", status_code=404
                )

            return json_response({"status": "ok", "data": batch.to_dict()})
        except ValueError as e:
            return error_response(str(e), status_code=400)
        except Exception as e:
            logger.error(f"获取增量批次详情异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_delete_incremental_batch(self) -> WebApiResponse:
        """删除指定群的单个增量批次"""
        try:
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            group_id = str(
                payload.get("group_id") or request.query.get("group_id") or ""
            ).strip()
            batch_id = str(
                payload.get("batch_id") or request.query.get("batch_id") or ""
            ).strip()

            if not group_id or not batch_id:
                return error_response("Missing group_id or batch_id", status_code=400)

            platform_id = str(
                payload.get("platform_id") or request.query.get("platform_id") or ""
            ).strip()
            delete_dto: IncrementalBatchDeleteDTO = {
                "platform_id": platform_id,
                "group_id": group_id,
                "batch_id": batch_id,
            }

            store = self._incremental_store
            if not store:
                return error_response(
                    "IncrementalStore not initialized", status_code=503
                )

            async with self._mutation_guard(group_id):
                store = await store.for_session(group_id, platform_id)
                deleted = await store.delete_batch(
                    delete_dto["group_id"], delete_dto["batch_id"]
                )
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
        except DuplicateGroupTaskError:
            return error_response(
                "此群有任务正在执行，请结束后再修改业务数据", status_code=409
            )
        except ValueError as e:
            return error_response(str(e), status_code=400)
        except Exception as e:
            logger.error(f"删除增量批次异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_reset_incremental_group(self) -> WebApiResponse:
        """一键清空指定群全部增量批次并将游标归零"""
        try:
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            group_id = str(
                payload.get("group_id") or request.query.get("group_id") or ""
            ).strip()
            if not group_id:
                return error_response("Missing group_id", status_code=400)

            platform_id = str(
                payload.get("platform_id") or request.query.get("platform_id") or ""
            ).strip()
            reset_dto: IncrementalResetDTO = {
                "group_id": group_id,
                "platform_id": platform_id,
            }

            store = self._incremental_store
            if not store:
                return error_response(
                    "IncrementalStore not initialized", status_code=503
                )

            async with self._mutation_guard(group_id):
                store = await store.for_session(group_id, platform_id)
                deleted_count = await store.reset_group(reset_dto["group_id"])
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
        except DuplicateGroupTaskError:
            return error_response(
                "此群有任务正在执行，请结束后再修改业务数据", status_code=409
            )
        except ValueError as e:
            return error_response(str(e), status_code=400)
        except Exception as e:
            logger.error(f"重置增量状态异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_list_checkpoints(self) -> WebApiResponse:
        """分页条件查询 Checkpoint 列表"""
        try:
            limit_raw = request.query.get("limit", "50")
            offset_raw = request.query.get("offset", "0")
            try:
                limit = int(limit_raw) if str(limit_raw).strip() else 50
            except (ValueError, TypeError):
                limit = 50
            try:
                offset = int(offset_raw) if str(offset_raw).strip() else 0
            except (ValueError, TypeError):
                offset = 0

            group_id = (request.query.get("group_id") or "").strip() or None
            date_str = (request.query.get("date_str") or "").strip() or None
            stage_name = (request.query.get("stage_name") or "").strip() or None
            trace_id = (request.query.get("trace_id") or "").strip() or None

            query_dto: CheckpointListQueryDTO = {
                "limit": limit,
                "offset": offset,
                "group_id": group_id,
                "date_str": date_str,
                "stage_name": stage_name,
                "trace_id": trace_id,
            }

            store = self._checkpoint_store
            if not store:
                return error_response(
                    "CheckpointStore not initialized", status_code=503
                )

            items, total = await asyncio.to_thread(
                store.list_all_checkpoints,
                platform=request.query.get("platform"),
                limit=query_dto.get("limit", 50),
                offset=query_dto.get("offset", 0),
                group_id=query_dto.get("group_id"),
                date_str=query_dto.get("date_str"),
                stage_name=query_dto.get("stage_name"),
                trace_id=query_dto.get("trace_id"),
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
            groups = await asyncio.to_thread(
                store.get_distinct_checkpoint_groups,
            )
            sessions = await asyncio.to_thread(store.get_checkpoint_group_sessions)
            return json_response(
                {"status": "ok", "data": {"groups": groups, "sessions": sessions}}
            )
        except Exception as e:
            logger.error(f"获取 Checkpoint 群号列表异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)

    async def api_get_checkpoint_detail(self) -> WebApiResponse:
        """获取单条 Checkpoint 产物 JSON 与元数据"""
        try:
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            group_id = str(
                request.query.get("group_id") or payload.get("group_id") or ""
            ).strip()
            date_str = str(
                request.query.get("date_str") or payload.get("date_str") or ""
            ).strip()
            stage_name = str(
                request.query.get("stage_name") or payload.get("stage_name") or ""
            ).strip()
            trace_id = str(
                request.query.get("trace_id") or payload.get("trace_id") or ""
            ).strip()

            if not group_id or not date_str or not stage_name:
                return error_response(
                    "group_id, date_str, stage_name are all required", status_code=400
                )

            query_dto: CheckpointDetailQueryDTO = {
                "group_id": group_id,
                "date_str": date_str,
                "stage_name": stage_name,
                "trace_id": trace_id,
            }

            store = self._checkpoint_store
            if not store:
                return error_response(
                    "CheckpointStore not initialized", status_code=503
                )

            detail = await asyncio.to_thread(
                store.get_checkpoint_detail,
                query_dto["group_id"],
                query_dto["date_str"],
                query_dto["stage_name"],
                trace_id=query_dto["trace_id"],
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
            try:
                payload = await request.json()
            except Exception:
                payload = {}
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

            delete_dto: CheckpointDeleteDTO = {
                "group_id": group_id,
                "date_str": date_str,
                "stage_name": stage_name,
                "trace_id": trace_id,
            }

            store = self._checkpoint_store
            if not store:
                return error_response(
                    "CheckpointStore not initialized", status_code=503
                )

            async with self._mutation_guard(group_id):
                if delete_dto.get("stage_name"):
                    deleted = await asyncio.to_thread(
                        store.delete_checkpoint,
                        delete_dto["group_id"],
                        delete_dto["date_str"],
                        delete_dto["stage_name"],
                        trace_id=delete_dto["trace_id"],
                    )
                else:
                    await asyncio.to_thread(
                        store.clear_checkpoints,
                        delete_dto["group_id"],
                        delete_dto["date_str"],
                    )
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
        except DuplicateGroupTaskError:
            return error_response(
                "此群有任务正在执行，请结束后再修改业务数据", status_code=409
            )
        except Exception as e:
            logger.error(f"删除 Checkpoint 异常: {e}", exc_info=True)
            return error_response(str(e), status_code=500)
