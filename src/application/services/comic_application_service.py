import mimetypes
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from astrbot.api.star import Context

from ...infrastructure.analysis.llm_analyzer import LLMAnalyzer
from ...infrastructure.config.config_manager import ConfigManager
from ...infrastructure.drawing.drawing_client import (
    DrawingClient,
    ImageDownloadFailedError,
)
from ...shared.trace_context import TraceContext
from ...utils.logger import logger


class ComicApplicationService:
    """
    负责统筹每日群漫画的生成流程：
    1. 调用 LLMAnalyzer 将群聊话题生成拼贴分镜提示词。
    2. 调用 DrawingClient 直接生成单张连环漫画长图。
    3. 返回图片数据供外部上传。
    """

    def __init__(
        self,
        llm_analyzer: LLMAnalyzer,
        drawing_client: DrawingClient,
        config_manager: ConfigManager,
        plugin_data_dir: Path,
        context: Context | None = None,
    ):
        self.llm_analyzer = llm_analyzer
        self.drawing_client = drawing_client
        self.config_manager = config_manager
        self.plugin_data_dir = plugin_data_dir
        self.context = context

    async def generate_comic(
        self,
        topics: list[dict],
        group_id: str,
        umo: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """
        生成漫画并返回图片字节数据。

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
        prompt_template = self.config_manager.get_comic_character_storyboard_prompt(
            character
        )
        logger.info(
            f"[Comic] 开始为群 {group_id} 生成每日漫画，角色方案: {character_name}"
        )

        trace = TraceContext.current()

        # 1. 提取分镜和金句
        sb_ctx = trace.span("COMIC_STORYBOARD") if trace else nullcontext()
        with sb_ctx as sb_rec:
            (
                storyboards,
                storyboard_usage,
            ) = await self.llm_analyzer.analyze_comic_storyboards(
                topics,
                umo,
                persona_id=persona_id or None,
                prompt_template=prompt_template or None,
            )
            if sb_rec and isinstance(sb_rec, dict):
                sb_prompts: dict[str, Any] = {}
                if trace and trace.metadata.get("llm_prompts"):
                    for k, p in trace.metadata["llm_prompts"].items():
                        if "comic" in k or k == "comic_storyboards":
                            sb_prompts[k] = p
                if not sb_prompts and storyboards:
                    sb_prompts["comic_storyboards"] = {
                        "prompt": prompt_template
                        or "自动从群聊话题中提取漫画多格分镜与生图提示词",
                        "system_prompt": f"漫画分镜师 | 人格: {persona_id or character_name}",
                        "completion": storyboards[0].get("scene", "")
                        if storyboards
                        else "",
                        "prompt_tokens": getattr(storyboard_usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(
                            storyboard_usage, "completion_tokens", 0
                        ),
                        "tokens": getattr(storyboard_usage, "total_tokens", 0),
                    }
                sb_rec.setdefault("payload", {}).update(
                    {
                        "character_name": character_name,
                        "topics_count": len(topics),
                        "storyboards_count": len(storyboards) if storyboards else 0,
                        "prompt_tokens": getattr(storyboard_usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(
                            storyboard_usage, "completion_tokens", 0
                        ),
                        "total_tokens": getattr(storyboard_usage, "total_tokens", 0),
                        "prompts": sb_prompts,
                    }
                )
                if not storyboards:
                    sb_rec["payload"]["warning"] = "未能从群聊话题中提取出漫画分镜"

        if not storyboards:
            logger.warning(
                f"[Comic] 群 {group_id} 未能提取到任何金句分镜，取消漫画生成。"
            )
            return None, None

        logger.info("[Comic] 成功提取到全景分镜提示词，开始调用绘画 API...")

        # 2. 直接生成一张图片
        scene_prompt = storyboards[0].get("scene", "")
        if not scene_prompt:
            logger.error("[Comic] 提取到的场景提示词为空，取消漫画生成。")
            return None, None

        logger.debug(f"[Comic] 漫画 Prompt 已生成，长度: {len(scene_prompt)}")

        # 3. 加载当前角色方案配置的全部参考图。
        images_data = []
        reference_image_paths = self.config_manager.get_drawing_reference_images()
        for reference_image_path in reference_image_paths:
            reference_image = await self._fetch_reference_image(reference_image_path)
            if reference_image:
                images_data.append(reference_image)
                logger.info(f"[Comic] 已加载参考图: {Path(reference_image_path).name}")
            else:
                logger.warning(
                    f"[Comic] 无法加载参考图: {Path(reference_image_path).name}"
                )

        draw_ctx = trace.span("COMIC_DRAWING") if trace else nullcontext()
        with draw_ctx as draw_rec:
            # 4. 若配置为外部绘图后端，优先走对应插件出图
            backend = self.config_manager.get_drawing_backend()
            if backend in {"general_plugin", "big_banana"}:
                if backend == "general_plugin":
                    external_comic_bytes = await self._generate_via_general_plugin(
                        scene_prompt, images_data
                    )
                else:
                    external_comic_bytes = await self._generate_via_big_banana(
                        scene_prompt, images_data
                    )
                if external_comic_bytes and not any(
                    external_comic_bytes == reference[0] for reference in images_data
                ):
                    logger.info(
                        f"[Comic] 漫画生成成功（{backend} 后端），大小: {len(external_comic_bytes)} bytes"
                    )
                    if draw_rec and isinstance(draw_rec, dict):
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
                    if draw_rec and isinstance(draw_rec, dict):
                        draw_rec.setdefault("payload", {}).update(
                            {
                                "backend": backend,
                                "error": f"{backend} 后端未产出结果且禁用回退",
                                "success": False,
                            }
                        )
                    return None, None
                logger.warning(f"[Comic] {backend} 后端未产出结果，回退内置绘图后端。")

            # 5. 内置绘图后端未配置时直接取消，避免空跑
            if not self.config_manager.get_drawing_provider_configs():
                logger.warning(
                    "[Comic] 未配置绘图供应商（drawing_provider_overrides），取消漫画生成。"
                )
                if draw_rec and isinstance(draw_rec, dict):
                    draw_rec.setdefault("payload", {}).update(
                        {
                            "backend": "builtin",
                            "error": "未配置绘图供应商",
                            "success": False,
                        }
                    )
                return None, None

            # 6. 调用绘图 API，捕获"有 URL 但下载失败"的情况
            fallback_url: str | None = None
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
                if draw_rec and isinstance(draw_rec, dict):
                    draw_rec.setdefault("payload", {}).update(
                        {
                            "backend": "builtin",
                            "fallback_url": exc.fallback_url,
                            "error": "图片下载失败，使用 fallback URL 发送",
                        }
                    )
                return None, exc.fallback_url

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
                and any(
                    keyword in last_error for keyword in exception_keywords if keyword
                )
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
                    try:
                        final_comic_bytes, _ = await self.drawing_client.generate_image(
                            new_prompt,
                            images_data=images_data or None,
                            disable_retry=True,
                        )
                    except ImageDownloadFailedError as exc:
                        logger.warning(
                            f"[Comic] 重写 Prompt 后图片下载仍失败，保留 fallback URL: {exc.fallback_url}"
                        )
                        if draw_rec and isinstance(draw_rec, dict):
                            draw_rec.setdefault("payload", {}).update(
                                {
                                    "backend": "builtin",
                                    "fallback_url": exc.fallback_url,
                                    "error": "重写 Prompt 后下载仍失败",
                                }
                            )
                        return None, exc.fallback_url
                    if final_comic_bytes and any(
                        final_comic_bytes == reference[0] for reference in images_data
                    ):
                        logger.warning(
                            "[Comic] 重写 Prompt 后仍原样返回参考图，拒绝发送。"
                        )
                        final_comic_bytes = None

            if draw_rec and isinstance(draw_rec, dict):
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

    async def _generate_via_general_plugin(
        self,
        scene_prompt: str,
        images_data: list[tuple[bytes, str]] | None,
    ) -> bytes | None:
        """通过「通用生图」插件的公共 API 生成漫画。

        未安装、未激活、未配置 API 或调用失败时返回 None，由调用方回退内置 DrawingClient。

        Returns:
            生成图片的二进制数据；失败时返回 None。
        """
        if self.context is None:
            logger.debug("[Comic] 未注入插件 Context，跳过通用生图后端。")
            return None
        try:
            meta = self.context.get_registered_star("astrbot_plugin_image_generation")
        except Exception as exc:
            logger.debug(f"[Comic] 获取通用生图插件注册信息失败: {exc}")
            return None
        image_plugin = meta.star_cls if meta and meta.activated else None
        if image_plugin is None:
            logger.warning(
                "[Comic] 未检测到已激活的「通用生图」插件，回退内置绘图后端。"
            )
            return None

        public_api = getattr(image_plugin, "public_api", None)
        if public_api is None:
            logger.warning("[Comic] 通用生图插件未暴露 public_api，回退内置绘图后端。")
            return None

        try:
            logger.info("[Comic] 通过「通用生图」插件公共 API 生成漫画...")
            result = await public_api.generate_image_files(
                prompt=scene_prompt,
                source="群分析插件",
                aspect_ratio="16:9",
                reference_image_data=images_data,
                timeout_seconds=600,
            )
        except Exception as exc:
            logger.error(f"[Comic] 通用生图后端调用异常: {exc}")
            return None

        if not getattr(result, "ok", False):
            code = str(getattr(result, "code", ""))
            message = getattr(result, "message", "") or getattr(result, "error", "")
            hint = ""
            if code == "prompt_blocked":
                hint = "（提示词被通用生图插件安全审核拦截，可调整其审核配置或精简 scene 提示词）"
            elif code == "api_key_missing":
                hint = "（通用生图插件未配置 API Key，需先在通用生图插件中配置）"
            elif code == "timeout":
                hint = "（等待通用生图任务结果超时）"
            elif code == "rate_limited":
                hint = "（命中通用生图插件额度/频率限制）"
            logger.warning(f"[Comic] 通用生图后端失败 [{code}]: {message}{hint}")
            return None

        paths = list(getattr(result, "paths", None) or [])
        if not paths:
            logger.warning(
                "[Comic] 通用生图后端未返回图片路径（可能参考图被忽略或结果为空，请检查通用生图插件配置与参考图大小限制）。"
            )
            return None
        try:
            return Path(paths[0]).read_bytes()
        except OSError as exc:
            logger.warning(f"[Comic] 读取通用生图后端结果失败: {exc}")
            return None

    async def _generate_via_big_banana(
        self,
        scene_prompt: str,
        images_data: list[tuple[bytes, str]] | None,
    ) -> bytes | None:
        """通过「大香蕉」插件的绘图管线生成漫画。

        大香蕉支持 Gemini、SiliconFlow、OpenAI 等多家提供商。

        Returns:
            生成图片的二进制数据；失败时返回 None。
        """
        if self.context is None:
            logger.debug("[Comic] 未注入插件 Context，跳过「大香蕉」后端。")
            return None
        try:
            meta = self.context.get_registered_star("astrbot_plugin_big_banana")
        except Exception as exc:
            logger.debug(f"[Comic] 获取「大香蕉」插件注册信息失败: {exc}")
            return None
        plugin = meta.star_cls if meta and meta.activated else None
        if plugin is None:
            logger.warning("[Comic] 未检测到已激活的「大香蕉」插件，回退内置绘图后端。")
            return None

        drawing_pipeline = getattr(plugin, "drawing_pipeline", None)
        if drawing_pipeline is None:
            logger.warning("[Comic] 「大香蕉」插件未初始化绘图管线，回退内置绘图后端。")
            return None

        ImageResource = self._import_big_banana_image_resource(plugin)
        if ImageResource is None:
            logger.warning("[Comic] 无法导入「大香蕉」图片资源类型，回退内置绘图后端。")
            return None

        image_list = None
        if images_data:
            image_list = []
            for img_bytes, _mime in images_data:
                resource = ImageResource.from_bytes(img_bytes)
                if resource:
                    image_list.append(resource)
            if not image_list:
                logger.warning(
                    "[Comic] 参考图无法解析为「大香蕉」图片资源，将不带参考图生成。"
                )

        params: dict[str, Any] = {
            "prompt": scene_prompt,
            "capability": "image_generation",
            "sub_brain": False,
            "url": False,
            "aspect_ratio": "16:9",
            "image_size": "1K",
        }

        try:
            logger.info("[Comic] 通过「大香蕉」插件绘图管线生成漫画...")
            result = await drawing_pipeline.run(params, image_list)
        except Exception as exc:
            logger.error(f"[Comic] 「大香蕉」绘图管线调用异常: {exc}")
            return None

        if getattr(result, "error_message", None):
            logger.warning(f"[Comic] 「大香蕉」生成失败: {result.error_message}")
            return None

        images = getattr(result, "images", None) or []
        if not images:
            logger.warning("[Comic] 「大香蕉」未返回图片。")
            return None
        try:
            image_bytes = images[0].bytes
        except Exception as exc:
            logger.warning(f"[Comic] 读取「大香蕉」生成结果失败: {exc}")
            return None
        if not image_bytes:
            logger.warning("[Comic] 「大香蕉」返回的图片为空。")
            return None
        return image_bytes

    @staticmethod
    def _import_big_banana_image_resource(plugin: Any):
        """导入「大香蕉」插件的 ImageResource 类型。

        AstrBot 以 ``data.plugins.<插件名>.main`` 形式加载插件，模块名并非
        ``astrbot_plugin_big_banana``，因此先从插件类的模块路径推导包名导入；
        推导失败时回退直接导入，兼容 pip 安装或测试环境注入的场景。

        Args:
            plugin: 已激活的大香蕉插件实例。

        Returns:
            ImageResource 类型；无法导入时返回 None。
        """
        import importlib

        module_name = getattr(type(plugin), "__module__", "") or ""
        candidate_modules = []
        if module_name and "." in module_name:
            candidate_modules.append(module_name.rsplit(".", 1)[0] + ".core.schemas")
        candidate_modules.append("astrbot_plugin_big_banana.core.schemas")

        for module_path in candidate_modules:
            try:
                schemas_module = importlib.import_module(module_path)
            except Exception:
                continue
            image_resource = getattr(schemas_module, "ImageResource", None)
            if image_resource is not None:
                return image_resource
        return None

    async def _fetch_reference_image(self, image_ref: str) -> tuple[bytes, str] | None:
        """从插件目录、AstrBot files、本地路径、HTTP URL 或 Base64 Data URL 获取已选参考图。

        Args:
            image_ref: 包含文件路径、URL 或 Base64 Data URL 的字符串。

        Returns:
            图片字节和 MIME 类型；加载失败时返回 None。
        """
        import base64

        if not image_ref or not isinstance(image_ref, str):
            return None

        image_ref = image_ref.strip()

        # 1. 支持 Data URL 格式 (data:image/png;base64,xxxx)
        if image_ref.startswith("data:image/"):
            try:
                header, b64_data = image_ref.split(",", 1)
                mime_type = header.split(";")[0].replace("data:", "").strip()
                return base64.b64decode(b64_data), mime_type or "image/png"
            except Exception as e:
                logger.error(f"[Comic] 解析 Data URL 参考图失败: {e}")
                return None

        # 2. 支持 base64:// 格式
        if image_ref.startswith("base64://"):
            try:
                return base64.b64decode(image_ref[9:]), "image/png"
            except Exception as e:
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

        # 4. 支持本地文件路径（插件数据目录、插件代码目录、AstrBot 根目录、或绝对路径）
        try:
            clean_rel = image_ref.lstrip("/\\")
            candidate_paths: list[Path] = []
            if hasattr(self, "plugin_data_dir") and self.plugin_data_dir:
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
                    return p.read_bytes(), guessed_type or "image/png"

            # 模糊查找纯文件名
            filename = Path(clean_rel).name
            search_roots: list[Path] = []
            if hasattr(self, "plugin_data_dir") and self.plugin_data_dir:
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
                            return match.read_bytes(), guessed_type or "image/png"

            logger.warning(f"[Comic] 找不到已选参考图: {image_ref}")
            return None
        except Exception as exc:
            logger.error(f"[Comic] 获取已选参考图失败 {image_ref}: {exc}")
            return None
