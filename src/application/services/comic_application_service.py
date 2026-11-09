from __future__ import annotations

import asyncio
import mimetypes
from contextlib import nullcontext
from pathlib import Path
from typing import TYPE_CHECKING

from ...domain.value_objects import ComicStoryboard
from ...infrastructure.drawing.drawing_client import (
    DrawingClient,
    ImageDownloadFailedError,
)
from ...infrastructure.drawing.external_drawing_adapter import ExternalDrawingAdapter
from ...shared.constants import AnalysisStage
from ...shared.trace_context import TraceContext
from ...shared.type_guards import is_string_mapping
from ...utils.logger import logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from astrbot.api.star import Context

    from ...domain.repositories.analysis_repository import IAnalysisProvider
    from ...domain.value_objects import SummaryTopic
    from ...domain.value_objects.group_session import GroupSession
    from ...infrastructure.config.config_manager import ConfigManager


class ComicApplicationService:
    """
    负责统筹每日群漫画的生成流程：
    1. 调用 LLMAnalyzer 将群聊话题生成拼贴分镜提示词。
    2. 调用 DrawingClient 直接生成单张连环漫画长图。
    3. 返回图片数据供外部上传。
    """

    llm_analyzer: IAnalysisProvider
    drawing_client: DrawingClient
    config_manager: ConfigManager
    plugin_data_dir: Path
    external_drawing: ExternalDrawingAdapter

    def __init__(
        self,
        llm_analyzer: IAnalysisProvider,
        drawing_client: DrawingClient,
        config_manager: ConfigManager,
        plugin_data_dir: Path,
        context: Context | None = None,
        external_drawing: ExternalDrawingAdapter | None = None,
    ) -> None:
        self.llm_analyzer = llm_analyzer
        self.drawing_client = drawing_client
        self.config_manager = config_manager
        self.plugin_data_dir = plugin_data_dir
        self.external_drawing = external_drawing or ExternalDrawingAdapter(context)

    async def generate_comic(
        self,
        topics: Sequence[SummaryTopic] | Sequence[dict[str, object]],
        group_id: str,
        umo: str | None = None,
        session: GroupSession | None = None,
    ) -> tuple[bytes | None, str | None]:
        """
        生成漫画并返回图片字节数据。

        Args:
            topics: 待改编的群聊话题。
            group_id: 目标群组标识。
            umo: 用于选择模型的消息来源。
            session: 已解析的真实群会话，用于隔离风格进度。

        Returns:
            (comic_bytes, fallback_url):
            - comic_bytes: 生成成功时为图片字节，失败时为 None。
            - fallback_url: 图片 API 返回了 URL 但下载失败时为该 URL，其他情况为 None。
        """
        if not self.config_manager.get_enable_daily_comic():
            return None, None

        character = self.config_manager.get_selected_comic_character()
        character_name = (
            str(character.get("name", "")).strip() if character else ""
        ) or "默认配置"
        persona_id = self.config_manager.get_comic_character_persona_id(character)
        reference_image_paths = self.config_manager.get_drawing_reference_images(
            character, select=False
        )
        prompt_template = await asyncio.to_thread(
            self.config_manager.get_comic_character_storyboard_prompt,
            character,
            session,
        )
        logger.info(
            f"[Comic] 开始为群 {group_id} 生成每日漫画，角色方案: {character_name}"
        )

        trace = TraceContext.current()

        scene_prompt = await self._generate_scene_prompt(
            topics, umo, character_name, persona_id, prompt_template
        )
        if not scene_prompt:
            return None, None

        logger.debug(f"[Comic] 漫画 Prompt 已生成，长度: {len(scene_prompt)}")

        # 3. 加载当前角色方案配置的全部参考图。
        images_data: list[tuple[bytes, str]] = []
        for reference_image_path in reference_image_paths:
            reference_image = await self._fetch_reference_image(reference_image_path)
            if reference_image:
                images_data.append(reference_image)
                logger.info(f"[Comic] 已加载参考图: {Path(reference_image_path).name}")
            else:
                logger.warning(
                    f"[Comic] 无法加载参考图: {Path(reference_image_path).name}"
                )

        draw_ctx = (
            trace.span_async(AnalysisStage.COMIC_DRAWING) if trace else nullcontext()
        )
        async with draw_ctx as draw_rec:
            # 4. 若配置为外部绘图后端，优先走对应插件出图
            backend = self.config_manager.get_drawing_backend()
            if backend in {"general_plugin", "big_banana"}:
                if backend == "general_plugin":
                    external_comic_bytes = await self.external_drawing.generate_general(
                        scene_prompt, images_data
                    )
                else:
                    external_comic_bytes = (
                        await self.external_drawing.generate_big_banana(
                            scene_prompt, images_data
                        )
                    )
                if external_comic_bytes and not any(
                    external_comic_bytes == reference[0] for reference in images_data
                ):
                    logger.info(
                        f"[Comic] 漫画生成成功（{backend} 后端），大小: {len(external_comic_bytes)} bytes"
                    )
                    if draw_rec:
                        draw_rec.setdefault("payload", {}).update(
                            {
                                "backend": backend,
                                "scene_prompt_len": len(scene_prompt),
                                "reference_images_count": len(images_data),
                                "image_bytes": len(external_comic_bytes),
                                "success": True,
                                "prompts": {
                                    "comic_drawing": {
                                        "prompt": scene_prompt,
                                        "system_prompt": f"绘图后端: {backend} | 角色方案: {character_name} | 参考图数: {len(images_data)}",
                                        "completion": f"出图完成（体积: {round(len(external_comic_bytes) / 1024, 1)} KB）",
                                        "provider_type": backend,
                                    }
                                },
                            }
                        )
                    return external_comic_bytes, None
                if external_comic_bytes:
                    logger.warning(
                        f"[Comic] {backend} 后端原样返回了参考图，拒绝发送并回退内置绘图后端。"
                    )
                if not self.config_manager.get_drawing_external_fallback():
                    logger.warning(
                        f"[Comic] {backend} 后端未产出结果，且已禁用回退内置后端，取消漫画生成。"
                    )
                    if draw_rec:
                        draw_rec.setdefault("payload", {}).update(
                            {
                                "backend": backend,
                                "error": f"{backend} 后端未产出结果且禁用回退",
                                "success": False,
                            }
                        )
                    return None, None
                logger.warning(f"[Comic] {backend} 后端未产出结果，回退内置绘图后端。")

            # 已通过外部后端返回的分支在上方结束；此处开始实际使用内置后端。
            backend = "builtin"
            # 5. 内置绘图后端未配置时直接取消，避免空跑
            if not self.config_manager.get_drawing_provider_configs():
                logger.warning(
                    "[Comic] 未配置绘图供应商（drawing_provider_overrides），取消漫画生成。"
                )
                if draw_rec:
                    draw_rec.setdefault("payload", {}).update(
                        {
                            "backend": "builtin",
                            "error": "未配置绘图供应商",
                            "success": False,
                        }
                    )
                return None, None

            (
                final_comic_bytes,
                last_error,
                fallback_url,
                scene_prompt,
            ) = await self._generate_builtin_comic(scene_prompt, images_data, umo)
            if fallback_url:
                if draw_rec:
                    draw_rec.setdefault("payload", {}).update(
                        {
                            "backend": "builtin",
                            "fallback_url": fallback_url,
                            "error": last_error,
                        }
                    )
                return None, fallback_url

            if draw_rec:
                draw_prompts = {
                    "comic_drawing": {
                        "prompt": scene_prompt,
                        "system_prompt": f"绘图引擎: {backend} | 角色方案: {character_name} | 参考图数: {len(images_data)}",
                        "completion": f"出图完成（体积: {round(len(final_comic_bytes) / 1024, 1)} KB）"
                        if final_comic_bytes
                        else (
                            f"出图未产出: {last_error}" if last_error else "未产出图像"
                        ),
                        "provider_type": backend,
                    }
                }
                draw_rec.setdefault("payload", {}).update(
                    {
                        "backend": backend,
                        "scene_prompt_len": len(scene_prompt),
                        "reference_images_count": len(images_data),
                        "image_bytes": len(final_comic_bytes)
                        if final_comic_bytes
                        else 0,
                        "success": bool(final_comic_bytes),
                        "last_error": last_error,
                        "prompts": draw_prompts,
                    }
                )

            if final_comic_bytes:
                logger.info(
                    f"[Comic] 漫画生成成功，大小: {len(final_comic_bytes)} bytes"
                )
            else:
                logger.error("[Comic] 漫画生成最终失败。")

            return final_comic_bytes, fallback_url

    async def _generate_scene_prompt(
        self,
        topics: Sequence[SummaryTopic] | Sequence[dict[str, object]],
        umo: str | None,
        character_name: str,
        persona_id: str,
        prompt_template: str,
    ) -> str | None:
        """生成漫画分镜并记录该步骤的提示词、Token 用量与空结果诊断。

        Args:
            topics: 待改编的群聊话题。
            umo: 用于选择分析模型的消息来源。
            character_name: 当前角色方案名称。
            persona_id: 当前角色使用的人格标识。
            prompt_template: 当前角色的分镜提示词模板。

        Returns:
            第一条有效分镜的绘图提示词；分镜缺失或为空时返回 None。
        """
        trace = TraceContext.current()
        # 1. 提取分镜和金句
        sb_ctx = (
            trace.span_async(AnalysisStage.COMIC_STORYBOARD) if trace else nullcontext()
        )
        async with sb_ctx as sb_rec:
            (
                storyboards,
                storyboard_usage,
            ) = await self.llm_analyzer.analyze_comic_storyboards(
                topics,
                umo,
                persona_id=persona_id or None,
                prompt_template=prompt_template or None,
            )
            if sb_rec:
                sb_prompts: dict[str, object] = {}
                llm_prompts = trace.metadata.get("llm_prompts") if trace else None
                if is_string_mapping(llm_prompts):
                    for k, p in llm_prompts.items():
                        if "comic" in str(k) or str(k) == "comic_storyboards":
                            sb_prompts[str(k)] = p
                if not sb_prompts and storyboards:
                    first_sb = storyboards[0] if storyboards else None
                    first_scene = (
                        (
                            first_sb.scene
                            if isinstance(first_sb, ComicStoryboard)
                            else first_sb.get("scene", "")
                        )
                        if first_sb
                        else ""
                    )
                    sb_prompts["comic_storyboards"] = {
                        "prompt": prompt_template
                        or "自动从群聊话题中提取漫画多格分镜与生图提示词",
                        "system_prompt": f"漫画分镜师 | 人格: {persona_id or character_name}",
                        "completion": first_scene,
                        "prompt_tokens": storyboard_usage.prompt_tokens,
                        "completion_tokens": storyboard_usage.completion_tokens,
                        "tokens": storyboard_usage.total_tokens,
                    }
                sb_rec.setdefault("payload", {}).update(
                    {
                        "character_name": character_name,
                        "topics_count": len(topics),
                        "storyboards_count": len(storyboards) if storyboards else 0,
                        "prompt_tokens": storyboard_usage.prompt_tokens,
                        "completion_tokens": storyboard_usage.completion_tokens,
                        "total_tokens": storyboard_usage.total_tokens,
                        "prompts": sb_prompts,
                    }
                )
                if not storyboards:
                    sb_rec["payload"]["warning"] = "未能从群聊话题中提取出漫画分镜"

        if not storyboards:
            logger.warning("[Comic] 未能提取到任何金句分镜，取消漫画生成。")
            return None

        logger.info("[Comic] 成功提取到全景分镜提示词，开始调用绘画 API...")

        # 2. 直接生成一张图片
        first_sb = storyboards[0]
        scene_prompt = (
            first_sb.scene
            if isinstance(first_sb, ComicStoryboard)
            else first_sb.get("scene", "")
        )
        if not scene_prompt:
            logger.error("[Comic] 提取到的场景提示词为空，取消漫画生成。")
            return None

        return scene_prompt

    async def _generate_builtin_comic(
        self,
        scene_prompt: str,
        images_data: list[tuple[bytes, str]],
        umo: str | None,
    ) -> tuple[bytes | None, str | None, str | None, str]:
        """调用内置绘图并按配置执行一次提示词重写，拒绝原样返回的参考图。

        Args:
            scene_prompt: 已生成的漫画提示词。
            images_data: 已加载的角色参考图。
            umo: 用于选择重写模型的消息来源。

        Returns:
            图片字节、最终失败原因、下载失败时的兜底 URL 和实际使用的提示词。
        """
        # 6. 调用绘图 API，捕获"有 URL 但下载失败"的情况
        try:
            (
                final_comic_bytes,
                last_error,
            ) = await self.drawing_client.generate_image(
                scene_prompt, images_data=images_data or None
            )
        except ImageDownloadFailedError as exc:
            logger.warning(
                f"[Comic] 图片下载失败，保留 fallback URL: {exc.fallback_url}"
            )
            return (
                None,
                "图片下载失败，使用 fallback URL 发送",
                exc.fallback_url,
                scene_prompt,
            )

        if final_comic_bytes and any(
            final_comic_bytes == reference[0] for reference in images_data
        ):
            logger.warning("[Comic] 内建绘图原样返回了参考图，拒绝发送。")
            final_comic_bytes = None
            last_error = "绘图服务原样返回了参考图"

        exception_keywords = (
            self.config_manager.get_drawing_output_exception_retry_keywords()
        )
        should_rewrite_prompt = bool(
            last_error
            and any(keyword in last_error for keyword in exception_keywords if keyword)
        )
        if not final_comic_bytes and last_error and should_rewrite_prompt:
            logger.info(
                f"[Comic] 画图重试已用尽，请求 LLM 分析报错并重写 Prompt: {last_error}"
            )
            new_prompt = await self.llm_analyzer.analyze_retry_prompt(
                scene_prompt, last_error, umo
            )
            if new_prompt:
                logger.info("[Comic] 获取到重写后的 Prompt，进行最后一次尝试...")
                scene_prompt = new_prompt
                try:
                    (
                        final_comic_bytes,
                        last_error,
                    ) = await self.drawing_client.generate_image(
                        scene_prompt,
                        images_data=images_data or None,
                        disable_retry=True,
                    )
                except ImageDownloadFailedError as exc:
                    logger.warning(
                        f"[Comic] 重写 Prompt 后图片下载仍失败，保留 fallback URL: {exc.fallback_url}"
                    )
                    return (
                        None,
                        "重写 Prompt 后下载仍失败",
                        exc.fallback_url,
                        scene_prompt,
                    )
                if final_comic_bytes and any(
                    final_comic_bytes == reference[0] for reference in images_data
                ):
                    logger.warning("[Comic] 重写 Prompt 后仍原样返回参考图，拒绝发送。")
                    final_comic_bytes = None
                    last_error = "绘图服务原样返回了参考图"

        return final_comic_bytes, last_error, None, scene_prompt

    async def _fetch_reference_image(self, image_ref: str) -> tuple[bytes, str] | None:
        """从插件目录、AstrBot files、本地路径、HTTP URL 或 Base64 Data URL 获取已选参考图。

        Args:
            image_ref: 包含文件路径、URL 或 Base64 Data URL 的字符串。

        Returns:
            图片字节和 MIME 类型；加载失败时返回 None。
        """
        import base64

        if not image_ref:
            return None

        image_ref = image_ref.strip()

        # 1. 支持 Data URL 格式 (data:image/png;base64,xxxx)
        if image_ref.startswith("data:image/"):
            try:
                header, b64_data = image_ref.split(",", 1)
                mime_type = header.split(";")[0].replace("data:", "").strip()
                image_data = base64.b64decode(b64_data, validate=True)
                if not image_data:
                    raise ValueError("参考图数据为空")
                return image_data, mime_type or "image/png"
            except ValueError as e:
                logger.error(f"[Comic] 解析 Data URL 参考图失败: {e}")
                return None

        # 2. 支持 base64:// 格式
        if image_ref.startswith("base64://"):
            try:
                image_data = base64.b64decode(image_ref[9:], validate=True)
                if not image_data:
                    raise ValueError("参考图数据为空")
                return image_data, "image/png"
            except ValueError as e:
                logger.error(f"[Comic] 解析 Base64 参考图失败: {e}")
                return None

        # 3. 支持 HTTP / HTTPS 远程 URL
        if image_ref.startswith(("http://", "https://")):
            try:
                import httpx

                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(image_ref)
                    if resp.status_code == 200:
                        mime_type = resp.headers.get("content-type", "image/png").split(
                            ";"
                        )[0]
                        return resp.content, mime_type
            except Exception as e:
                logger.error(f"[Comic] 下载远程参考图失败 {image_ref}: {e}")
                return None

        return await asyncio.to_thread(self._read_local_reference_image, image_ref)

    def _read_local_reference_image(self, image_ref: str) -> tuple[bytes, str] | None:
        """在线程中查找并读取本地参考图，避免递归目录扫描阻塞异步任务。

        Args:
            image_ref: 本地文件引用或已上传文件的相对路径。

        Returns:
            图片字节和 MIME 类型；找不到或无法读取时返回 None。
        """
        # 常见图片扩展名优先使用固定类型，避免依赖 Windows 注册表中的 MIME 注册情况。
        image_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        # 4. 支持本地文件路径（插件数据目录、插件代码目录、AstrBot 根目录、或绝对路径）
        try:
            clean_rel = image_ref.lstrip("/\\")
            requested_path = Path(image_ref)
            candidate_paths: list[Path] = (
                [requested_path] if requested_path.is_absolute() else []
            )
            if self.plugin_data_dir:
                p_data = Path(self.plugin_data_dir)
                candidate_paths.extend(
                    [
                        p_data / clean_rel,
                        p_data / "reference_images" / clean_rel,
                    ]
                )

            candidate_paths.append(
                Path.cwd()
                / "data"
                / "plugin_data"
                / "astrbot_plugin_qq_group_daily_analysis"
                / clean_rel
            )
            candidate_paths.append(Path(clean_rel))

            for p in candidate_paths:
                if p.is_file():
                    guessed_type, _ = mimetypes.guess_type(p.name)
                    return p.read_bytes(), image_types.get(
                        p.suffix.lower()
                    ) or guessed_type or "image/png"

            # 模糊查找纯文件名
            filename = Path(clean_rel).name
            search_roots: list[Path] = []
            if self.plugin_data_dir:
                search_roots.append(Path(self.plugin_data_dir))
            search_roots.append(
                Path.cwd()
                / "data"
                / "plugin_data"
                / "astrbot_plugin_qq_group_daily_analysis"
            )

            for root in search_roots:
                files_dir = root / "files"
                if files_dir.exists():
                    for match in files_dir.rglob(filename):
                        if match.is_file():
                            guessed_type, _ = mimetypes.guess_type(match.name)
                            return match.read_bytes(), image_types.get(
                                match.suffix.lower()
                            ) or guessed_type or "image/png"

            logger.warning(f"[Comic] 找不到已选参考图: {image_ref}")
            return None
        except Exception as exc:
            logger.error(f"[Comic] 获取已选参考图失败 {image_ref}: {exc}")
            return None
