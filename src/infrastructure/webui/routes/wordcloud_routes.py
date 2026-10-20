"""词云编辑器的模板、草稿预览和字体上传接口。"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ....domain.value_objects.wordcloud import (
    WordCloudData,
    WordCloudOptions,
    WordFrequency,
)
from ....utils.logger import logger
from ..web_compat import WebApiResponse, error_response, json_response, request

if TYPE_CHECKING:
    from ...persistence.wordcloud_store import WordCloudSnapshot, WordCloudStore
    from ...reporting.wordcloud_renderer import WordCloudRenderer


@runtime_checkable
class FontUpload(Protocol):
    """宿主上传对象的最小协议。"""

    filename: str | None

    async def read(self, size: int = -1) -> bytes: ...


class WordCloudRoutes:
    """所有预览复用生产模板，不写入正式配置或群统计。"""

    def __init__(
        self,
        renderer: WordCloudRenderer | None,
        store: WordCloudStore | None = None,
        resource_lock: asyncio.Lock | None = None,
    ) -> None:
        self.renderer = renderer
        self.store = store
        self._font_lock = resource_lock if resource_lock is not None else asyncio.Lock()

    async def api_templates(self) -> WebApiResponse:
        """列出真正支持词云的模板及可用字体。"""
        if self.renderer is None:
            return error_response("词云渲染器尚未初始化", status_code=503)
        fonts: list[dict[str, object]] = [
            {"id": "wenkai", "label": "霞鹜文楷", "uploaded": False},
            {"id": "sans", "label": "无衬线", "uploaded": False},
            {"id": "serif", "label": "衬线", "uploaded": False},
        ]
        directory = self.renderer.data_dir / "wordcloud_fonts"
        if directory.is_dir() and not directory.is_symlink():
            for path in sorted(directory.iterdir()):
                if (
                    path.is_file()
                    and not path.is_symlink()
                    and re.fullmatch(r"[a-f0-9]{64}\.(?:woff2?|ttf|otf)", path.name)
                ):
                    fonts.append(
                        {
                            "id": "uploaded:" + path.name,
                            "label": self._font_label(path),
                            "uploaded": True,
                        }
                    )
        return json_response(
            {
                "status": "ok",
                "data": {
                    "templates": [
                        {
                            "name": item.id,
                            "label": item.label,
                            **self.renderer.template_details(item.id),
                        }
                        for item in self.renderer.discover_templates()
                    ],
                    "fonts": fonts,
                },
            }
        )

    async def api_snapshots(self) -> WebApiResponse:
        """只读返回每个群最近的已缓存词频，不拉取群消息。"""
        if self.store is None:
            return error_response("词云统计缓存尚未初始化", status_code=503)
        try:
            snapshots = await asyncio.to_thread(self.store.list_snapshots)
            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "snapshots": [
                            {
                                "id": item.id,
                                "umo": item.umo,
                                "updated_at": item.updated_at,
                                "group_id": item.data.group_id,
                                "group_label": "群 " + item.data.group_id,
                                "date_str": item.data.date_str,
                                "message_count": item.data.message_count,
                                "word_count": len(item.data.frequencies),
                                "start_timestamp": item.data.start_timestamp,
                                "end_timestamp": item.data.end_timestamp,
                            }
                            for item in snapshots
                        ]
                    },
                }
            )
        except Exception as exc:
            logger.warning(f"读取词云缓存列表失败：{exc}")
            return error_response("读取词云缓存失败，请稍后重试", status_code=500)

    async def api_preview(self) -> WebApiResponse:
        """使用未保存草稿生成快速 HTML 或框架 T2I 图片。

        Returns:
            HTML 或可预览的图片数据地址，错误时返回明确原因。
        """
        if self.renderer is None:
            return error_response("词云渲染器尚未初始化", status_code=503)
        try:
            body = await request.json()
            raw = body.get("options", {})
            if not isinstance(raw, dict):
                raise ValueError("预览设置必须是对象")
            umo = body.get("umo", "")
            if not isinstance(umo, str):
                raise ValueError("会话标识必须是字符串")
            source = body.get("source", "sample")
            if not isinstance(source, str) or source not in {"sample", "snapshot"}:
                raise ValueError("预览来源只能是 sample 或 snapshot")
            snapshot: WordCloudSnapshot | None = None
            if source == "snapshot":
                if self.store is None:
                    return error_response("词云统计缓存尚未初始化", status_code=503)
                snapshot_id = body.get("snapshot_id")
                if not isinstance(snapshot_id, str):
                    raise ValueError("请选择需要预览的群统计")
                snapshot = await asyncio.to_thread(self.store.get_snapshot, snapshot_id)
                if snapshot is None:
                    return error_response(
                        "这份群统计已失效，请刷新缓存列表后重新选择", status_code=404
                    )
                if umo and umo != snapshot.umo:
                    raise ValueError("所选群统计与当前群设置不一致")
                umo = snapshot.umo
            # 先覆盖草稿再校验，允许修正尚未保存的无效旧值后立即预览。
            configured: object = self.renderer.config_manager.config.get(
                "wordcloud", {}
            )
            if not isinstance(configured, dict):
                raise ValueError("词云配置必须是对象")
            overrides: object = raw.get(
                "group_overrides", configured.get("group_overrides", {})
            )
            if not isinstance(overrides, dict):
                raise ValueError("词云群级覆盖必须是对象")
            override: object = overrides.get(umo, {}) if umo else {}
            if not isinstance(override, dict):
                raise ValueError("词云群级覆盖内容必须是对象")
            explicit = {**configured, **override, **raw}
            template = WordCloudOptions.from_mapping(
                {"template": explicit.get("template", "ATRI")}
            ).template
            defaults = self.renderer.template_details(template)["defaults"]
            assert isinstance(defaults, dict)
            options = WordCloudOptions.from_mapping({**defaults, **explicit})
            mode = body.get("mode", "html")
            if not isinstance(mode, str) or mode not in {"html", "image"}:
                raise ValueError("预览模式只能是 html 或 image")
            terms = [
                "亚托莉",
                "高性能",
                "今天",
                "明天",
                "日常",
                "夏天",
                "海风",
                "夕阳",
                "相遇",
                "快乐",
                "聊天",
                "游戏",
                "动漫",
                "音乐",
                "可爱",
                "朋友",
                "世界",
                "晚安",
                "早安",
                "喜欢",
                "分享",
                "期待",
                "生活",
                "故事",
                "记忆",
                "学习",
                "工作",
                "周末",
                "旅行",
                "天空",
                "云朵",
                "星光",
                "月亮",
                "梦想",
                "温柔",
                "陪伴",
                "笑容",
                "感谢",
                "可乐",
                "咖啡",
                "蛋糕",
                "礼物",
                "手机",
                "电脑",
                "电影",
                "小说",
                "照片",
                "风景",
                "花园",
                "城市",
                "小镇",
                "海边",
                "烟花",
                "夜晚",
                "阳光",
                "清晨",
                "午后",
                "雨天",
                "晴天",
                "春天",
                "秋天",
                "冬天",
                "季节",
                "回忆",
                "时光",
                "美好",
                "勇气",
                "希望",
                "未来",
                "约定",
                "问候",
                "知识",
                "灵感",
                "绘画",
                "创作",
                "兴趣",
                "美食",
                "运动",
                "散步",
                "窗边",
                "音符",
                "花瓣",
                "浪花",
                "信件",
                "旅途",
            ]
            data = WordCloudData(
                frequencies=tuple(
                    WordFrequency(word, 150 - i, 100 - i)
                    for i, word in enumerate(terms)
                ),
                message_count=1200,
                group_id="预览群聊",
                date_str="词云外观预览",
            )
            if snapshot is not None:
                data = snapshot.data
            metadata: dict[str, object] = {
                "source": source,
                "umo": umo,
                "group_id": data.group_id,
                "group_label": "群 " + data.group_id if snapshot else data.group_id,
                "date_str": data.date_str,
                "message_count": data.message_count,
                "word_count": len(data.frequencies),
                "eligible_word_count": len(
                    data.top_words(replace(options, max_words=len(data.frequencies)))
                ),
                "display_word_count": len(data.top_words(options)),
                "start_timestamp": data.start_timestamp,
                "end_timestamp": data.end_timestamp,
                "notes": [
                    "使用已缓存的分词结果；调整保留词、排除词和门槛仅筛选现有词频，新增分词需重新分析群消息。"
                ]
                if snapshot
                else [],
            }
            if snapshot is not None:
                metadata.update(snapshot_id=snapshot.id, updated_at=snapshot.updated_at)
            if mode == "html":
                html = await asyncio.to_thread(
                    self.renderer.build_html, data, options, umo
                )
                return json_response(
                    {"status": "ok", "data": {"html": html, "metadata": metadata}}
                )
            result = await self.renderer.render(data, umo=umo, options=options)
            if isinstance(result, bytes):
                image = "data:image/png;base64," + base64.b64encode(result).decode()
            elif result.startswith("base64://"):
                image = "data:image/png;base64," + result[9:]
            elif result.startswith(("data:image/", "http://", "https://")):
                image = result
            else:
                image = (
                    "data:image/png;base64,"
                    + base64.b64encode(Path(result).read_bytes()).decode()
                )
            return json_response(
                {"status": "ok", "data": {"image": image, "metadata": metadata}}
            )
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        except Exception as exc:
            logger.warning(f"词云预览失败：{exc}")
            return error_response(f"词云预览失败：{exc}", status_code=500)

    async def api_upload_font(self) -> WebApiResponse:
        """接收不超过 20 MB 的字体，以内容摘要保存并返回稳定字体标识。"""
        if self.renderer is None:
            return error_response("词云渲染器尚未初始化", status_code=503)
        try:
            upload = (await request.uploaded_files()).get("file")
            if not isinstance(upload, FontUpload):
                raise ValueError("请选择需要上传的字体文件")
            filename = Path((upload.filename or "font").replace("\\", "/")).name
            suffix = Path(filename).suffix.lower()
            signatures = {
                ".woff": b"wOFF",
                ".woff2": b"wOF2",
                ".ttf": b"\x00\x01\x00\x00",
                ".otf": b"OTTO",
            }
            if suffix not in signatures:
                raise ValueError("支持 WOFF2、WOFF、TTF、OTF 字体")
            data = await upload.read(20 * 1024 * 1024 + 1)
            if len(data) > 20 * 1024 * 1024:
                raise ValueError("字体文件不能超过 20 MB")
            if len(data) < 12 or data[:4] != signatures[suffix]:
                raise ValueError("字体文件格式与扩展名不一致")
            name = hashlib.sha256(data).hexdigest() + suffix
            label = self._validate_label(filename)
            async with self._font_lock:
                path = self._font_path("uploaded:" + name)
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    # 同一文件再次上传不会覆盖已重命名的标签或现有字体内容。
                    if path.read_bytes() != data:
                        return error_response(
                            "相同字体标识已有不同内容，请检查字体目录", status_code=409
                        )
                    label = self._font_label(path)
                else:
                    with path.open("xb") as stream:
                        stream.write(data)
                    try:
                        self._write_label(path, label)
                    except Exception:
                        path.unlink(missing_ok=True)
                        raise
            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "id": "uploaded:" + name,
                        "label": label,
                        "uploaded": True,
                    },
                }
            )
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        except Exception as exc:
            logger.warning(f"字体上传失败：{exc}")
            return error_response("字体上传失败，请查看插件日志", status_code=500)

    def _font_path(self, font_id: object) -> Path:
        """限制字体操作只访问内容摘要命名的普通上传文件。"""
        if not isinstance(font_id, str) or not re.fullmatch(
            r"uploaded:[a-f0-9]{64}\.(?:woff2?|ttf|otf)", font_id
        ):
            raise ValueError("只能管理有效的已上传字体")
        assert self.renderer is not None
        root = self.renderer.data_dir / "wordcloud_fonts"
        path = root / font_id.partition(":")[2]
        label_path = path.with_suffix(path.suffix + ".label")
        if (
            root.is_symlink()
            or path.is_symlink()
            or label_path.is_symlink()
            or not path.resolve().is_relative_to(root.resolve())
            or (path.exists() and not path.is_file())
        ):
            raise ValueError("上传字体路径无效")
        return path

    @staticmethod
    def _validate_label(label: object) -> str:
        """验证显示名称长度和不可见控制字符，不将名称作为路径。"""
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 120:
            raise ValueError("字体名称应为 1～120 个字符")
        if any(ord(char) < 32 or ord(char) == 127 for char in label):
            raise ValueError("字体名称不能包含控制字符")
        return label.strip()

    @staticmethod
    def _font_label(path: Path) -> str:
        """读取受限长度的字体标签，旧文件缺少标签时使用摘要。"""
        label = path.with_suffix(path.suffix + ".label")
        if label.is_file() and not label.is_symlink() and label.stat().st_size <= 1024:
            try:
                return WordCloudRoutes._validate_label(
                    label.read_text(encoding="utf-8")
                )
            except (UnicodeError, ValueError):
                pass
        return path.name[:12]

    @staticmethod
    def _write_label(path: Path, label: str) -> None:
        """原子替换小型显示名称文件，写入失败时保留旧标签。"""
        with tempfile.NamedTemporaryFile(
            dir=path.parent, suffix=".tmp", mode="w", encoding="utf-8", delete=False
        ) as stream:
            pending = Path(stream.name)
            stream.write(label)
        try:
            pending.replace(path.with_suffix(path.suffix + ".label"))
        finally:
            pending.unlink(missing_ok=True)

    async def api_font_preview(self) -> WebApiResponse:
        """返回选中字体的固定文字样张，不生成群词云或保存配置。"""
        if self.renderer is None:
            return error_response("词云渲染器尚未初始化", status_code=503)
        try:
            body = await request.json()
            font = body.get("font")
            if not isinstance(font, str):
                raise ValueError("请选择需要预览的字体")
            html = await asyncio.to_thread(self.renderer.build_font_sample, font)
            return json_response({"status": "ok", "data": {"font": font, "html": html}})
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        except Exception as exc:
            logger.warning(f"字体样张预览失败：{exc}")
            return error_response("字体样张预览失败，请查看插件日志", status_code=500)

    async def api_rename_font(self) -> WebApiResponse:
        """只修改上传字体的显示名称，保持配置引用的标识稳定。"""
        if self.renderer is None:
            return error_response("词云渲染器尚未初始化", status_code=503)
        try:
            body = await request.json()
            async with self._font_lock:
                path = self._font_path(body.get("id"))
                label = self._validate_label(body.get("label"))
                if not path.is_file():
                    return error_response(
                        "字体不存在或已被删除，请刷新字体列表", status_code=404
                    )
                self._write_label(path, label)
            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "id": "uploaded:" + path.name,
                        "label": label,
                        "uploaded": True,
                    },
                }
            )
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        except Exception as exc:
            logger.warning(f"字体重命名失败：{exc}")
            return error_response("字体重命名失败，请查看插件日志", status_code=500)

    async def api_delete_font(self) -> WebApiResponse:
        """拒绝删除被全局或任意群引用的字体，其余字体移至可恢复目录。

        Returns:
            删除结果；引用冲突返回 409，不修改配置或文件。
        """
        if self.renderer is None:
            return error_response("词云渲染器尚未初始化", status_code=503)
        try:
            body = await request.json()
            async with self._font_lock:
                path = self._font_path(body.get("id"))
                font_id = "uploaded:" + path.name
                if not path.is_file():
                    return error_response(
                        "字体不存在或已被删除，请刷新字体列表", status_code=404
                    )
                config: object = self.renderer.config_manager.config.get(
                    "wordcloud", {}
                )
                if not isinstance(config, dict):
                    raise ValueError("词云配置无效，无法确认字体是否被引用")
                references: list[str] = []
                if self.renderer.config_manager.get_wordcloud_options().font == font_id:
                    references.append("全局默认")
                overrides: object = config.get("group_overrides", {})
                if not isinstance(overrides, dict):
                    raise ValueError("群级覆盖配置无效，无法确认字体是否被引用")
                for umo, override in overrides.items():
                    if not isinstance(override, dict):
                        raise ValueError("群级覆盖配置无效，无法确认字体是否被引用")
                    if (
                        self.renderer.config_manager.get_wordcloud_options(
                            str(umo)
                        ).font
                        == font_id
                    ):
                        references.append("群 " + str(umo))
                if references:
                    return error_response(
                        "此字体仍被以下设置引用，请先修改并保存："
                        + "、".join(references),
                        status_code=409,
                    )
                trash = path.parent / "trash"
                if trash.is_symlink() or (trash.exists() and not trash.is_dir()):
                    raise ValueError("字体回收目录无效")
                trash.mkdir(exist_ok=True)
                archive = Path(tempfile.mkdtemp(prefix=f"{time.time_ns()}-", dir=trash))
                label = self._font_label(path)
                (archive / "manifest.json").write_text(
                    json.dumps(
                        {
                            "id": font_id,
                            "label": label,
                            "deleted_at": time.time(),
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                label_path = path.with_suffix(path.suffix + ".label")
                moved_font = archive / path.name
                moved_label = archive / label_path.name
                try:
                    path.rename(moved_font)
                    if label_path.exists():
                        label_path.rename(moved_label)
                except Exception:
                    if moved_font.exists():
                        moved_font.rename(path)
                    if moved_label.exists():
                        moved_label.rename(label_path)
                    raise
            return json_response(
                {"status": "ok", "data": {"id": font_id, "deleted": True}}
            )
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        except Exception as exc:
            logger.warning(f"字体删除失败：{exc}")
            return error_response(
                "字体删除失败，请查看插件日志及回收目录", status_code=500
            )

    async def api_restore_font(self) -> WebApiResponse:
        """恢复最近删除的同标识字体，拒绝覆盖已经重新上传的文件。"""
        if self.renderer is None:
            return error_response("词云渲染器尚未初始化", status_code=503)
        try:
            body = await request.json()
            async with self._font_lock:
                path = self._font_path(body.get("id"))
                font_id = "uploaded:" + path.name
                label_path = path.with_suffix(path.suffix + ".label")
                if path.exists() or label_path.exists():
                    return error_response(
                        "同标识字体已存在，恢复操作不会覆盖现有文件", status_code=409
                    )
                trash = path.parent / "trash"
                if trash.is_symlink():
                    raise ValueError("字体回收目录无效")
                archives = (
                    sorted(trash.iterdir(), reverse=True) if trash.is_dir() else []
                )
                for archive in archives:
                    if not archive.is_dir() or archive.is_symlink():
                        continue
                    manifest = archive / "manifest.json"
                    saved = archive / path.name
                    if (
                        not saved.is_file()
                        or saved.is_symlink()
                        or not manifest.is_file()
                        or manifest.is_symlink()
                        or manifest.stat().st_size > 4096
                    ):
                        continue
                    try:
                        raw: object = json.loads(manifest.read_text(encoding="utf-8"))
                        if not isinstance(raw, dict) or raw.get("id") != font_id:
                            continue
                        label = self._validate_label(raw.get("label"))
                    except (ValueError, UnicodeError):
                        continue
                    if (
                        saved.stat().st_size > 20 * 1024 * 1024
                        or hashlib.sha256(saved.read_bytes()).hexdigest() != path.stem
                    ):
                        return error_response(
                            "回收字体的内容校验失败，已保留归档文件", status_code=409
                        )
                    saved.rename(path)
                    try:
                        self._write_label(path, label)
                    except Exception:
                        path.rename(saved)
                        raise
                    return json_response(
                        {
                            "status": "ok",
                            "data": {
                                "id": font_id,
                                "label": label,
                                "uploaded": True,
                            },
                        }
                    )
                return error_response("没有找到可恢复的字体文件", status_code=404)
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        except Exception as exc:
            logger.warning(f"字体恢复失败：{exc}")
            return error_response("字体恢复失败，请查看插件日志", status_code=500)
