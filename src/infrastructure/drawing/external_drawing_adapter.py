"""外部绘图插件接入，隔离注册发现、动态 SDK 和响应校验。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...shared.type_guards import is_object_list
from ...utils.logger import logger

if TYPE_CHECKING:
    from astrbot.api.star import Context


class ExternalDrawingAdapter:
    """将外部绘图插件的成功结果统一为图片字节，失败返回 None。"""

    def __init__(self, context: Context | None) -> None:
        self.context = context

    async def generate_general(
        self,
        scene_prompt: str,
        images_data: list[tuple[bytes, str]] | None,
    ) -> bytes | None:
        """通过「通用生图」插件的公共 API 生成漫画。

        未安装、未激活、未配置 API 或调用失败时返回 None，由调用方回退内置 DrawingClient。

        Args:
            scene_prompt: 已生成的漫画场景提示词。
            images_data: 可选的参考图字节及 MIME 类型。

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

        paths: object = getattr(result, "paths", None)
        if (
            not is_object_list(paths)
            or not paths
            or not isinstance(paths[0], (str, Path))
        ):
            logger.warning(
                "[Comic] 通用生图后端未返回图片路径（可能参考图被忽略或结果为空，请检查通用生图插件配置与参考图大小限制）。"
            )
            return None
        try:
            return Path(paths[0]).read_bytes()
        except OSError as exc:
            logger.warning(f"[Comic] 读取通用生图后端结果失败: {exc}")
            return None

    async def generate_big_banana(
        self,
        scene_prompt: str,
        images_data: list[tuple[bytes, str]] | None,
    ) -> bytes | None:
        """通过「大香蕉」插件的绘图管线生成漫画。

        大香蕉支持 Gemini、SiliconFlow、OpenAI 等多家提供商。

        Args:
            scene_prompt: 已生成的漫画场景提示词。
            images_data: 可选的参考图字节及 MIME 类型。

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
        from_bytes = getattr(ImageResource, "from_bytes", None)
        if not callable(from_bytes):
            logger.warning("[Comic] 无法导入「大香蕉」图片资源类型，回退内置绘图后端。")
            return None

        image_list: list[object] | None = None
        if images_data:
            image_list = []
            for img_bytes, _mime in images_data:
                resource: object = from_bytes(img_bytes)
                if resource:
                    image_list.append(resource)
            if not image_list:
                logger.warning(
                    "[Comic] 参考图无法解析为「大香蕉」图片资源，将不带参考图生成。"
                )

        params: dict[str, object] = {
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

        images: object = getattr(result, "images", None)
        if not is_object_list(images):
            images = []
        if not images:
            logger.warning("[Comic] 「大香蕉」未返回图片。")
            return None
        try:
            image_bytes: object = getattr(images[0], "bytes", None)
        except Exception as exc:
            logger.warning(f"[Comic] 读取「大香蕉」生成结果失败: {exc}")
            return None
        if not isinstance(image_bytes, bytes) or not image_bytes:
            logger.warning("[Comic] 「大香蕉」返回的图片为空。")
            return None
        return image_bytes

    @staticmethod
    def _import_big_banana_image_resource(plugin: object) -> object | None:
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
        candidate_modules: list[str] = []
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
