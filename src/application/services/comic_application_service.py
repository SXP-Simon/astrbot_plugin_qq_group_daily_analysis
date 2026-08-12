import mimetypes
from pathlib import Path

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
    ):
        self.llm_analyzer = llm_analyzer
        self.drawing_client = drawing_client
        self.config_manager = config_manager
        self.plugin_data_dir = plugin_data_dir

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

        # 1. 提取分镜和金句
        storyboards, _ = await self.llm_analyzer.analyze_comic_storyboards(
            topics,
            umo,
            persona_id=persona_id or None,
            prompt_template=prompt_template or None,
        )

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

        # 4. 调用绘图 API，捕获"有 URL 但下载失败"的情况
        fallback_url: str | None = None
        try:
            final_comic_bytes, last_error = await self.drawing_client.generate_image(
                scene_prompt, images_data=images_data or None
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
                        new_prompt, images_data=images_data or None, disable_retry=True
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
