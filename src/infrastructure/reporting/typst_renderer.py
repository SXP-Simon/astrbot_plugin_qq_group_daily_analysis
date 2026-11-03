"""与 AstrBot/custom 并列的独立 Typst 渲染入口。"""

from __future__ import annotations

import asyncio
import json
import shutil
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import aiohttp
from PIL import Image

from ...shared.trace_context import TraceContext
from ...utils.logger import logger
from .render_trace import render_span as _span
from .template_asset_catalog import THEME_DECORATION_OPACITIES, THEME_DECORATIONS
from .template_installer import is_path_within, validate_template_name
from .template_resources import TemplateResourceStore
from .typst_data import TypstDataPreparer, TypstIdentityOptions
from .typst_process import run_typst_worker
from .typst_resources import TypstAssets
from .typst_worker import CUSTOM_TEMPLATE_MARKER, REPORT_PPI, REPORT_WIDTH

if TYPE_CHECKING:
    from ...domain.value_objects import AnalysisResultPayload
    from ..config.config_manager import ConfigManager
    from ..config.rendering_config import RenderingStrategyOptions
    from .avatar_service import AvatarService
    from .typst_data import TypstReportData


REPORT_TEMPLATES = Path(__file__).parent / "templates"


async def render_typst_probe(
    data_dir: Path, options: RenderingStrategyOptions
) -> bytes:
    """使用同一独立编译进程测试受管理字体和 PNG 输出。

    Args:
        data_dir: 插件数据根目录。
        options: 当前未保存的 Typst 方案。

    Returns:
        固定测试图片，不读取群聊、不调用模型也不发送消息。
    """
    jobs = data_dir / "typst" / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="probe-", dir=jobs) as directory:
        job_dir = Path(directory)
        (job_dir / "main.typ").write_text(
            f"""#let u = {72 / REPORT_PPI}pt
#set page(width:{REPORT_WIDTH}*u,height:180*u,margin:28*u,fill:rgb("f0fafa"))
#set text(font:"Noto Sans SC",size:18*u,fill:rgb("2c3e50"))
#text(weight:"bold",fill:rgb("2a9d95"))[Typst 独立排版测试]
#v(12*u)
中文、English、日本語 · 0123456789
#v(8*u)
受管理字体 → 原生 PNG
#metadata((height:180*u/1pt))<report-size>
""",
            encoding="utf-8",
        )
        await run_typst_worker(
            job_dir, data_dir / "typst" / "fonts", options.get("timeout", 30000) / 1000
        )
        return await asyncio.to_thread((job_dir / "report.png").read_bytes)


class TypstReportRenderer:
    """独立报告适配器，分离任务输入、编译恢复与输出编码。

    Args:
        config: 插件配置，布局尺寸不从配置读取。
        data_dir: 插件受管理数据目录。
        avatars: 平台隔离的头像服务。
        profile_manifest: 人格装饰清单。
    """

    def __init__(
        self,
        config: ConfigManager,
        data_dir: Path,
        avatars: AvatarService,
        profile_manifest: dict[str, dict],
    ) -> None:
        self.config = config
        self.data_dir = data_dir
        self.avatars = avatars
        self.profile_manifest = profile_manifest

    def _resolve_template(self, theme: str) -> Path:
        """解析真实模板入口，内置目录优先并拒绝自定义符号链接。

        Args:
            theme: 已校验的主题名。

        Returns:
            内置或用户安装的 report.typ 路径。

        Raises:
            ValueError: 模板不存在、不支持 Typst 或目录包含符号链接。
        """
        directory = REPORT_TEMPLATES / theme
        if not directory.is_dir():
            custom = self.config.get_custom_report_template_dir(theme)
            if (
                not custom
                or custom.is_symlink()
                or not is_path_within(custom, custom.parent)
            ):
                raise ValueError(
                    f"未找到 Typst 主题「{theme}」，请重新安装或选择其他模板"
                )
            if any(path.is_symlink() for path in custom.rglob("*")):
                raise ValueError("Typst 自定义模板包含符号链接，请重新上传独立文件")
            directory = custom
        template = directory / "report.typ"
        if not template.is_file():
            raise ValueError(
                f"主题「{theme}」没有 Typst 模板，请选择支持 Typst 的主题或切换渲染方案"
            )
        return template

    async def render(
        self,
        result: AnalysisResultPayload,
        theme: str,
        options: RenderingStrategyOptions,
        identity: TypstIdentityOptions | None = None,
    ) -> bytes:
        """在统一预算内准备、编译并导出静态报告。

        Args:
            result: 完整领域分析结果。
            theme: 内置或已安装的主题名。
            options: 本轮输出和网络方案，不含动态版心参数。
            identity: 身份展示与平台回调，均不进入模板代码。

        Returns:
            PNG 或 JPEG 字节。

        Raises:
            ValueError: 缺少主题入口或受管理字体。
            RuntimeError: 主题和基础恢复均编译失败。
            TimeoutError: 准备或编译超过本轮预算。
        """
        async with _span("TYPST_VALIDATE", {"template": theme, "width": REPORT_WIDTH}):
            template = self._resolve_template(validate_template_name(theme))
            font_dir = self.data_dir / "typst/fonts"
            if not font_dir.is_dir() or not any(
                p.suffix.lower() in (".ttf", ".otf", ".ttc") for p in font_dir.iterdir()
            ):
                raise ValueError(
                    "请先在 WebUI 下载 Typst 字体，字体保存在插件数据目录 typst/fonts"
                )
        jobs = self.data_dir / "typst/jobs"
        jobs.mkdir(parents=True, exist_ok=True)
        deadline = (
            asyncio.get_running_loop().time() + options.get("timeout", 30000) / 1000
        )
        async with asyncio.timeout_at(deadline):
            with TemporaryDirectory(prefix="report-", dir=jobs) as directory:
                job = Path(directory)
                await self._prepare(
                    result,
                    template,
                    job,
                    options,
                    identity or TypstIdentityOptions(),
                    deadline,
                )
                await self._compile(job, deadline, template.parent.name)
                async with _span(
                    "TYPST_ENCODE", {"format": options.get("type", "png")}
                ) as span:
                    image = await asyncio.to_thread((job / "report.png").read_bytes)
                    if options.get("type", "png") == "jpeg":
                        image = await asyncio.to_thread(
                            _encode_jpeg, image, options.get("quality", 90)
                        )
                    if span:
                        span["payload"]["image_bytes"] = len(image)
                return image

    async def _prepare(
        self,
        result: AnalysisResultPayload,
        template: Path,
        job: Path,
        options: RenderingStrategyOptions,
        identity: TypstIdentityOptions,
        deadline: float,
    ) -> None:
        """组装隔离任务输入：结构化数据、资源和主模板。

        Args:
            result: 原始领域分析结果。
            template: 已解析的真实入口。
            job: 本次专用编译目录。
            options: 已固定的资源方案。
            identity: 平台身份与匿名选项。
            deadline: 整条渲染链路的截止时间。
        """
        theme = template.parent.name
        resources = options.get("resource_urls")
        cdn = (
            resources["cdn_base_url"]
            if resources
            else self.config.get_t2i_cdn_base_url()
        )
        base = self.config.get_template_assets_base_url(
            options.get("resource_environment"), cdn_base_url=cdn
        )
        network_deadline = deadline - min(10.0, options.get("timeout", 30000) / 2000)
        store = TemplateResourceStore(
            self.data_dir, base, network_deadline=network_deadline
        )
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15), trust_env=True
        ) as session:
            assets = TypstAssets(self.data_dir, job, session, resource_store=store)
            preparer = TypstDataPreparer(
                self.config, self.avatars, assets, result, identity
            )
            async with _span("TYPST_DATA") as span:
                data = await preparer.prepare(self.profile_manifest, cdn, theme)
                if span:
                    span["payload"].update(
                        topics=len(data["topics"]),
                        portraits=len(data["portraits"]),
                        quotes=len(data["quotes"]),
                    )
                    if assets.network_budget_exhausted:
                        span["payload"]["warning"] = (
                            "头像或昵称查询超时，保留正文继续生成"
                        )
            await self._prepare_resources(template, job, data, assets, store)

    async def _prepare_resources(
        self,
        template: Path,
        job: Path,
        data: TypstReportData,
        assets: TypstAssets,
        store: TemplateResourceStore,
    ) -> None:
        """本地化主题资源并写入隔离编译输入，缺图按现有占位规则继续。

        Args:
            template: 已解析的主题入口。
            job: 本轮隔离目录。
            data: 已净化的结构化报告内容。
            assets: 本轮图片缓存与解码器。
            store: 固定素材清单的本地优先存储。
        """
        theme = template.parent.name
        builtin = template.parent.parent == REPORT_TEMPLATES
        base = store.base_url
        async with _span("TYPST_RESOURCES", {"template": theme}) as span:
            opacities = THEME_DECORATION_OPACITIES.get(theme, {})
            data["decorations"] = await asyncio.gather(
                *(
                    assets.localize(f"{base}/{name}", opacity=opacities.get(index, 1.0))
                    for index, name in enumerate(THEME_DECORATIONS.get(theme, ()))
                )
            )
            shutil.copyfile(REPORT_TEMPLATES / "common.typ", job / "common.typ")
            if builtin:
                for resource in template.parent.iterdir():
                    if resource.suffix in (".svg", ".typ") and resource != template:
                        shutil.copyfile(resource, job / resource.name)
                await store.stage_vectors(theme, job)
            else:
                # 保留相对导入，上传包不能覆盖运行时生成的数据和入口。
                shutil.copytree(template.parent, job, dirs_exist_ok=True)
                (job / CUSTOM_TEMPLATE_MARKER).touch()
            shutil.copyfile(template, job / "main.typ")
            (job / "data.json").write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
            if span:
                span["payload"].update(
                    local_resources=store.local_hits,
                    downloaded_resources=store.downloads,
                    missing_resources=len(store.failed),
                    missing_images=len(assets.failed),
                    image_cache_hits=assets.cache_hits,
                    network_budget_exhausted=assets.network_budget_exhausted
                    or store.network_budget_exhausted,
                )
                if store.failed or assets.failed:
                    span["payload"]["warning"] = (
                        "部分图片或图标缺失，已使用占位；可在配置中心下载主题素材或切换 CDN"
                    )
        if assets.network_budget_exhausted or store.network_budget_exhausted:
            logger.warning(
                "Typst 部分可选网络资源超时，保留正文并继续排版；可检查网络或在 WebUI 补齐主题素材"
            )
            trace = TraceContext.current()
            if trace:
                trace.metadata["has_warnings"] = True
                trace.metadata["typst_network_budget_exhausted"] = True

    async def _compile(self, job: Path, deadline: float, theme: str) -> None:
        """主题失败后在剩余预算内使用独立基础排版，取消不触发恢复。

        Args:
            job: 本次隔离编译目录。
            deadline: 整条渲染链路的单调时钟截止时间。
            theme: 本轮主题，用于诊断记录。

        Raises:
            RuntimeError: 基础恢复也失败。
            TimeoutError: 剩余预算耗尽。
        """
        loop = asyncio.get_running_loop()
        remaining = max(0.0, deadline - loop.time())
        fonts = self.data_dir / "typst/fonts"
        compile_span = None
        try:
            async with _span(
                "TYPST_COMPILE", {"template": theme, "width": REPORT_WIDTH}
            ) as compile_span:
                metrics = await run_typst_worker(
                    job, fonts, remaining - min(2.0, remaining / 5)
                )
                if compile_span and metrics:
                    compile_span["payload"].update(metrics)
        except (RuntimeError, TimeoutError) as error:
            logger.warning(
                f"Typst 主题 {theme} 渲染失败，自动改用基础排版保留报告内容：{error}"
            )
            trace = TraceContext.current()
            if trace:
                trace.metadata["typst_recovery"] = {
                    "theme": theme,
                    "reason": str(error)[:1800] or type(error).__name__,
                    "mode": "basic",
                }
                trace.metadata["has_warnings"] = True
            async with _span(
                "TYPST_RECOVERY",
                {"mode": "basic", "reason": str(error)[:1800] or type(error).__name__},
            ) as recovery_span:
                # 恢复入口不导入主题、组件或图片，原始结构化文字保持完整。
                shutil.copyfile(REPORT_TEMPLATES / "recovery.typ", job / "main.typ")
                (job / "report.png").unlink(missing_ok=True)
                (job / CUSTOM_TEMPLATE_MARKER).unlink(missing_ok=True)
                metrics = await run_typst_worker(
                    job, fonts, max(0.0, deadline - loop.time())
                )
                if recovery_span and metrics:
                    recovery_span["payload"].update(metrics)
            if compile_span:
                compile_span["status"] = "warning"
                compile_span["payload"]["failure_reason"] = compile_span["payload"].pop(
                    "error", str(error)
                )
                compile_span["payload"]["warning"] = (
                    "主题编译失败，基础排版已恢复完整报告"
                )


def _encode_jpeg(payload: bytes, quality: int) -> bytes:
    """在工作线程中将编译结果转为 JPEG，避免压缩阻塞事件循环。

    Args:
        payload: 已校验的 PNG。
        quality: JPEG 质量。

    Returns:
        JPEG 文件字节。
    """
    with Image.open(BytesIO(payload)) as image:
        output = BytesIO()
        image.convert("RGB").save(output, format="JPEG", quality=quality)
        return output.getvalue()
