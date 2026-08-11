import mimetypes
from pathlib import Path

from astrbot.api.star import Context

from ...infrastructure.analysis.llm_analyzer import LLMAnalyzer
from ...infrastructure.config.config_manager import ConfigManager
from ...infrastructure.drawing.drawing_client import (
    DrawingClient,
    ImageDownloadFailedError,
)
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

        logger.info(f"[Comic] 开始为群 {group_id} 生成每日漫画...")

        # 1. 提取分镜和金句
        storyboards, _ = await self.llm_analyzer.analyze_comic_storyboards(topics, umo)

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

        # 3. 处理参考图
        images_data = None
        reference_image_path = self.config_manager.get_drawing_reference_image()
        if reference_image_path:
            reference_image = await self._fetch_reference_image(reference_image_path)
            if reference_image:
                images_data = [reference_image]
                logger.info(
                    f"[Comic] 成功加载 WebUI 参考图: {Path(reference_image_path).name}"
                )
            else:
                logger.warning(
                    f"[Comic] 无法加载 WebUI 参考图: {Path(reference_image_path).name}，将不使用参考图。"
                )

        # 4. 若配置为通用生图后端，优先走「通用生图」插件公共 API（流式/异步，避免网关超时）
        if self.config_manager.get_drawing_backend() == "general_plugin":
            general_comic_bytes = await self._generate_via_general_plugin(
                scene_prompt, images_data
            )
            if general_comic_bytes:
                logger.info(
                    f"[Comic] 漫画生成成功（通用生图后端），大小: {len(general_comic_bytes)} bytes"
                )
                return general_comic_bytes, None
            logger.warning("[Comic] 通用生图后端未产出结果，回退内置绘图后端。")

        # 5. 调用内置绘图 API，捕获"有 URL 但下载失败"的情况
        fallback_url: str | None = None
        try:
            final_comic_bytes, last_error = await self.drawing_client.generate_image(
                scene_prompt, images_data=images_data
            )
        except ImageDownloadFailedError as exc:
            logger.warning(
                f"[Comic] 图片下载失败，保留 fallback URL: {exc.fallback_url}"
            )
            return None, exc.fallback_url

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
                try:
                    final_comic_bytes, _ = await self.drawing_client.generate_image(
                        new_prompt, images_data=images_data, disable_retry=True
                    )
                except ImageDownloadFailedError as exc:
                    logger.warning(
                        f"[Comic] 重写 Prompt 后图片下载仍失败，保留 fallback URL: {exc.fallback_url}"
                    )
                    return None, exc.fallback_url

        if final_comic_bytes:
            logger.info(f"[Comic] 漫画生成成功，大小: {len(final_comic_bytes)} bytes")
        else:
            logger.error("[Comic] 漫画生成最终失败。")

        return final_comic_bytes, fallback_url

    async def _generate_via_general_plugin(
        self,
        scene_prompt: str,
        images_data: list[tuple[bytes, str]] | None,
    ) -> bytes | None:
        """通过「通用生图」插件的公共 API 生成漫画。

        通用生图插件内部使用流式/异步轮询，可规避非流式请求撞上游网关超时 (HTTP 504)。
        未安装、未激活、未配置 API 或调用失败时返回 None，由调用方回退内置 DrawingClient。

        Returns:
            生成图片的二进制数据；失败时返回 None。
        """
        if self.context is None:
            logger.debug("[Comic] 未注入插件 Context，跳过通用生图后端。")
            return None
        try:
            meta = self.context.get_registered_star(
                "astrbot_plugin_image_generation"
            )
        except Exception as exc:
            logger.debug(f"[Comic] 获取通用生图插件注册信息失败: {exc}")
            return None
        image_plugin = meta.star_cls if meta and meta.activated else None
        if image_plugin is None:
            logger.warning("[Comic] 未检测到已激活的「通用生图」插件，回退内置绘图后端。")
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
                aspect_ratio=self.config_manager.get_drawing_aspect_ratio(),
                reference_image_data=images_data,
                timeout_seconds=self.config_manager.get_drawing_timeout(),
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

    async def _fetch_reference_image(
        self, relative_path: str
    ) -> tuple[bytes, str] | None:
        """从插件上传目录获取已选参考图。

        Args:
            relative_path: WebUI 保存的插件数据目录相对路径。

        Returns:
            图片字节和 MIME 类型；加载失败时返回 None。
        """
        try:
            plugin_data_dir = self.plugin_data_dir.resolve()
            image_path = (plugin_data_dir / relative_path).resolve()
            image_path.relative_to(plugin_data_dir)
            if not image_path.is_file():
                logger.warning(f"[Comic] 找不到已选参考图: {relative_path}")
                return None

            guessed_type, _ = mimetypes.guess_type(image_path.name)
            if not guessed_type or not guessed_type.startswith("image/"):
                logger.warning(f"[Comic] 已选参考图不是支持的图片文件: {relative_path}")
                return None
            return image_path.read_bytes(), guessed_type
        except (OSError, ValueError) as exc:
            logger.error(f"[Comic] 获取已选参考图失败 {relative_path}: {exc}")
            return None
