"""将完整词频转换为独立词云 HTML，并通过 AstrBot T2I 生成图片。"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Protocol
from urllib.parse import quote, urlsplit

from jinja2 import FileSystemLoader, select_autoescape
from jinja2.sandbox import SandboxedEnvironment

from ...domain.value_objects.wordcloud import WordCloudOptions
from .template_installer import template_dir_has_symlink_entries, validate_template_name
from .templates import HTMLTemplates

if TYPE_CHECKING:
    from ...domain.value_objects.wordcloud import WordCloudData
    from ..config.config_manager import ConfigManager


class WordCloudHtmlRender(Protocol):
    """AstrBot HTML 渲染入口的类型契约。"""

    async def __call__(
        self,
        tmpl: str,
        data: dict[str, object],
        return_url: bool = True,
        options: dict[str, object] | None = None,
        umo: str | None = None,
    ) -> str | bytes: ...


@dataclass(frozen=True)
class WordCloudTemplateInfo:
    """具备独立词云主模板的主题元信息。"""

    id: str
    label: str
    is_custom: bool = False
    has_wordcloud: bool = True


class WordCloudRenderer:
    """词云模板、CDN 与用户上传资源的 T2I 编排。

    Args:
        config_manager: 提供全局与群级设置的配置管理器。
        data_dir: 插件数据目录，包含用户上传字体。
        html_render_func: AstrBot 的 html_render 回调。
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        data_dir: Path,
        html_render_func: WordCloudHtmlRender | None = None,
    ) -> None:
        self.config_manager = config_manager
        self.data_dir = Path(data_dir)
        self.html_render_func = html_render_func
        self.template_root = Path(__file__).parent / "templates"
        self.plugin_root = Path(__file__).resolve().parents[3]
        self._assets: dict[Path, tuple[int, int, str]] = {}
        self._active_images: set[Path] = set()
        self._render_semaphore = asyncio.Semaphore(
            max(1, int(config_manager.get_t2i_max_concurrent() or 2))
        )

    def set_html_render(self, func: WordCloudHtmlRender) -> None:
        """注入框架渲染回调。"""
        self.html_render_func = func

    def discover_templates(self) -> list[WordCloudTemplateInfo]:
        """只发现拥有独立词云主模板的主题，禁止日报组件兜底。

        Returns:
            内置优先的可用词云主题列表。
        """
        found: dict[str, WordCloudTemplateInfo] = {}
        roots = [(self.template_root, False)]
        custom = self.config_manager.get_custom_report_template_dir("")
        if custom:
            roots.append((Path(custom), True))
        builtin_names = {
            entry.name for entry in self.template_root.iterdir() if entry.is_dir()
        }
        for root, is_custom in roots:
            if not root.is_dir():
                continue
            for entry in sorted(root.iterdir()):
                if (
                    not entry.is_dir()
                    or entry.is_symlink()
                    or entry.name.startswith(".")
                    or entry.name in found
                    or (is_custom and entry.name in builtin_names)
                    or template_dir_has_symlink_entries(entry)
                    or not (entry / "wordcloud_template.html").is_file()
                ):
                    continue
                meta = HTMLTemplates._read_template_meta(entry)
                found[entry.name] = WordCloudTemplateInfo(
                    id=entry.name,
                    label=meta.get("name")
                    or HTMLTemplates.KNOWN_TEMPLATE_NAMES.get(entry.name, entry.name),
                    is_custom=is_custom,
                )
        return list(found.values())

    def _asset_uri(self, path: Path) -> str:
        """校验本地资源并按文件版本缓存数据 URI。

        Args:
            path: 已由调用处限制在资源目录中的文件路径。

        Returns:
            可在远程 T2I 中独立使用的数据 URI。

        Raises:
            ValueError: 文件不存在、类型不支持或内容为空。
        """
        mimes = {
            ".webp": "image/webp",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".woff2": "font/woff2",
            ".woff": "font/woff",
            ".ttf": "font/ttf",
            ".otf": "font/otf",
        }
        if not path.is_file() or path.suffix.lower() not in mimes:
            raise ValueError(f"词云资源不存在或类型不支持：{path.name}")
        stat = path.stat()
        if stat.st_size == 0 or stat.st_size > 20 * 1024 * 1024:
            raise ValueError(f"词云资源为空或超过 20 MB：{path.name}")
        cached = self._assets.get(path)
        if cached and cached[:2] == (stat.st_mtime_ns, stat.st_size):
            return cached[2]
        uri = f"data:{mimes[path.suffix.lower()]};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
        self._assets[path] = (stat.st_mtime_ns, stat.st_size, uri)
        return uri

    def template_details(self, name: str) -> dict[str, object]:
        """读取模板自身默认值和已有缩略图，不混入用户配置。

        Args:
            name: 已发现的词云模板标识。

        Returns:
            完整默认配置及可选的本地缩略图数据地址。

        Raises:
            ValueError: 模板或其默认配置无效。
        """
        directory = self._template_directory(name)
        defaults_file = directory / "wordcloud_defaults.json"
        defaults: dict[str, object] = {}
        if defaults_file.is_file():
            raw: object = json.loads(defaults_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("词云模板默认设置必须是对象")
            defaults = raw
        result: dict[str, object] = {
            "defaults": WordCloudOptions.from_mapping(
                {**defaults, "template": name}
            ).to_dict()
        }
        for filename in (
            "wordcloud_preview.webp",
            "wordcloud_preview.png",
            "wordcloud_preview.jpg",
            "preview.webp",
            "preview.png",
            "preview.jpg",
        ):
            path = directory / filename
            if path.is_file():
                result["thumbnail"] = self._asset_uri(path)
                break
        return result

    def _template_directory(self, name: str) -> Path:
        """统一校验生产渲染和目录元数据使用的模板目录。"""
        name = validate_template_name(name)
        builtin = self.template_root / name
        custom = self.config_manager.get_custom_report_template_dir(name)
        directory = builtin if builtin.is_dir() else Path(custom) if custom else builtin
        if (
            not directory.is_dir()
            or directory.is_symlink()
            or template_dir_has_symlink_entries(directory)
            or not (directory / "wordcloud_template.html").is_file()
        ):
            raise ValueError(f"模板「{name}」不支持词云，请选择具备词云能力的模板")
        return directory

    def validate_config_resources(self, config: dict[str, object]) -> None:
        """用正式模板和字体解析规则验证待保存的全部作用域。

        Args:
            config: 尚未写入配置管理器的完整词云配置。

        Raises:
            ValueError: 全局或群级设置无效，或者引用的资源不可用。
        """
        overrides = config.get("group_overrides", {})
        if not isinstance(overrides, dict):
            raise ValueError("词云群级覆盖必须是对象")
        scopes: list[tuple[str, dict[str, object]]] = [("全局默认", config)]
        for umo, override in overrides.items():
            if (
                not isinstance(umo, str)
                or ":GroupMessage:" not in umo
                or not isinstance(override, dict)
            ):
                raise ValueError("词云群级覆盖必须使用完整群会话标识和配置对象")
            scopes.append(("群 " + umo, {**config, **override}))
        for scope, explicit in scopes:
            try:
                template = WordCloudOptions.from_mapping(
                    {"template": explicit.get("template", "ATRI")}
                ).template
                defaults = self.template_details(template)["defaults"]
                assert isinstance(defaults, dict)
                options = WordCloudOptions.from_mapping({**defaults, **explicit})
                self.font_uri(options.font)
            except ValueError as exc:
                raise ValueError(f"词云{scope}：{exc}") from exc

    def font_uri(self, font: str) -> str:
        """解析生产词云和字体样张共用的直链或用户上传字体。

        Args:
            font: 内置字体或上传字体标识。

        Returns:
            远端字体直链或上传字体数据地址，系统字体返回空字符串。

        Raises:
            ValueError: 字体标识、路径或文件无效。
        """
        if font == "wenkai":
            return self._cdn_asset_uri(
                "ATRI/file/1775130743963_1774880718993_LXGWWenKai-Regular.woff2"
            )
        if font.startswith("uploaded:"):
            filename = font.partition(":")[2]
            if not re.fullmatch(r"[a-f0-9]{64}\.(?:woff2?|ttf|otf)", filename):
                raise ValueError("上传字体标识无效")
            root = self.data_dir / "wordcloud_fonts"
            path = root / filename
            if (
                root.is_symlink()
                or path.is_symlink()
                or not path.resolve().is_relative_to(root.resolve())
            ):
                raise ValueError("上传字体路径无效")
            return self._asset_uri(path)
        if font not in {"sans", "serif"}:
            raise ValueError("词云字体设置无效")
        return ""

    def _cdn_asset_uri(self, relative: str) -> str:
        """按现有报告镜像配置解析仓库素材直链，不下载资源。

        Args:
            relative: 仓库 assets 下的主题目录和文件路径。

        Returns:
            可交给浏览器或 T2I 加载的 HTTP(S) 地址。

        Raises:
            ValueError: 素材路径或镜像地址格式无效。
        """
        path = PurePosixPath(relative)
        theme, separator, filename = relative.partition("/")
        if (
            not separator
            or not filename
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in relative.split("/"))
            or "\\" in relative
        ):
            raise ValueError("词云 CDN 素材路径无效")
        base = (
            self.config_manager.get_t2i_atri_font_mirror()
            if theme == "ATRI"
            else f"{self.config_manager.get_template_assets_base_url()}/{quote(theme, safe='')}"
        )
        parsed = urlsplit(base)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or any(char.isspace() or char in "\"'<>\\" for char in base)
        ):
            raise ValueError("词云模板 CDN 地址无效，请检查模板渲染设置")
        return f"{base.rstrip('/')}/{quote(filename, safe='/')}"

    def build_font_sample(self, font: str) -> str:
        """构建固定文字样张，字体加载失败时明确显示错误。"""
        uri = self.font_uri(font)
        family = (
            '"WordCloudSample", sans-serif'
            if uri
            else "serif"
            if font == "serif"
            else "sans-serif"
        )
        return (
            '<!doctype html><html lang="zh-CN" data-t2i-state="pending"><meta charset="utf-8">'
            '<meta name="color-scheme" content="light dark"><style>'
            + "body{margin:0;padding:12px 16px;box-sizing:border-box;background:transparent;"
            + f"font-family:{family};font-size:26px;line-height:1.55;overflow-wrap:anywhere}}"
            + "small{display:block;opacity:.65;font-size:15px}</style>"
            + "<body>亚托莉的今日群聊记忆<small>高性能 · ABC 0123456789</small>"
            + "<script>(async()=>{const root=document.documentElement;let finished=false;"
            + "const fail=()=>{if(finished)return;finished=true;root.dataset.t2iState='error';"
            + "document.body.replaceChildren(document.createTextNode('字体加载失败，请检查模板 CDN 或上传字体'));};"
            + "const timer=setTimeout(fail,4000);try{const uri="
            + json.dumps(uri).replace("<", "\\u003c")
            + ";if(uri){const font=new FontFace('WordCloudSample',`url(\"${uri}\")`);"
            + "await font.load();document.fonts.add(font);}await document.fonts.ready;"
            + "await new Promise(resolve=>requestAnimationFrame(resolve));if(finished)return;"
            + "finished=true;clearTimeout(timer);root.dataset.t2iState='ready';"
            + "}catch{clearTimeout(timer);fail();}})();</script></body></html>"
        )

    def build_html(
        self,
        data: WordCloudData,
        options: WordCloudOptions | None = None,
        umo: str = "",
    ) -> str:
        """生成供快速预览与正式渲染共同使用的固定尺寸 HTML。

        Args:
            data: 未按显示数量截断的完整统计。
            options: 已验证的草稿配置；为空时解析会话配置。
            umo: 完整平台群会话标识。

        Returns:
            包含资源直链、上传字体和内嵌排版脚本的 HTML。

        Raises:
            ValueError: 主题、资源或上传字体无效。
        """
        options = options or self.config_manager.get_wordcloud_options(umo)
        name = options.template
        builtin = self.template_root / name
        template_dir = self._template_directory(name)

        assets: dict[str, str] = {}
        manifest = template_dir / "wordcloud_assets.json"
        if manifest.is_file():
            raw: object = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("词云资源清单必须是对象")
            asset_root = (
                (self.plugin_root / "assets") if builtin.is_dir() else template_dir
            )
            asset_root = asset_root.resolve()
            for key, relative in raw.items():
                if not isinstance(key, str) or not isinstance(relative, str):
                    raise ValueError("词云资源清单的键和值必须是字符串")
                if relative.startswith("cdn:"):
                    assets[key] = self._cdn_asset_uri(relative.removeprefix("cdn:"))
                    continue
                path = (asset_root / relative).resolve()
                if not path.is_relative_to(asset_root):
                    raise ValueError("词云资源路径超出模板资源目录")
                assets[key] = self._asset_uri(path)

        payload = {
            "options": options.to_dict(),
            "words": [entry.to_dict() for entry in data.top_words(options)],
            "font_uri": self.font_uri(options.font),
        }
        env = SandboxedEnvironment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        # 统计文本只经 JSON 数据进入脚本，避免闭合 script 标签或解释 Jinja 表达式。
        return env.get_template("wordcloud_template.html").render(
            options=options,
            data=data,
            assets=assets,
            payload_json=json.dumps(payload, ensure_ascii=False)
            .replace("<", "\\u003c")
            .replace("&", "\\u0026"),
        )

    def _store_image(self, cache_file: Path, content: bytes) -> None:
        """原子保存图片，清理超过三十天或数量上限的旧缓存。

        Args:
            cache_file: 当前图片的最终缓存路径。
            content: 已校验的 PNG 内容。
        """
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=cache_file.parent, suffix=".tmp", delete=False
        ) as stream:
            pending = Path(stream.name)
            stream.write(content)
        try:
            pending.replace(cache_file)
        finally:
            pending.unlink(missing_ok=True)
        now = time.time()
        protected = self._active_images.copy() | {cache_file}
        entries: list[tuple[float, Path]] = []
        for path in cache_file.parent.glob("*.png"):
            try:
                entries.append((path.stat().st_mtime, path))
            except OSError:
                continue
        entries.sort(reverse=True)
        for index, (modified, path) in enumerate(entries):
            # 最近一小时的图可能正交由发送器读取；写入中的临时文件也不参与清理。
            if path in protected or now - modified < 3600:
                continue
            if index >= 256 or now - modified > 30 * 86400:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    continue

    async def render(
        self,
        data: WordCloudData,
        umo: str = "",
        options: WordCloudOptions | None = None,
    ) -> str | bytes:
        """调用框架生成图片，并独立缓存已完成的图片。

        Args:
            data: 完整词频快照。
            umo: 用于解析会话专属 T2I 端点的标识。
            options: 可选草稿设置。

        Returns:
            图片路径或图片字节。

        Raises:
            RuntimeError: 未注入渲染回调或返回内容为空。
        """
        if self.html_render_func is None:
            raise RuntimeError("词云 T2I 渲染器尚未初始化")
        options = options or self.config_manager.get_wordcloud_options(umo)
        source = await asyncio.to_thread(self.build_html, data, options, umo)
        # 对 HTML 与会话一同取摘要，避免外观变化或端点切换复用旧图。
        cache_key = hashlib.sha256((umo + "\0" + source).encode()).hexdigest()
        cache_file = self.data_dir / "wordcloud_images" / f"{cache_key}.png"
        async with self._render_semaphore:
            if cache_file.is_file():
                await asyncio.to_thread(cache_file.touch)
                return str(cache_file)
            image_options: dict[str, object] = {
                "type": "png",
                "full_page": True,
                "viewport_width": options.width,
                "viewport_height": options.height,
                "timeout": 30000,
            }
            # 用单个模板变量传入最终 HTML，词语中的花括号不会被二次当作模板执行。
            self._active_images.add(cache_file)
            try:
                result = await self.html_render_func(
                    "{{ wordcloud_html | safe }}",
                    {"wordcloud_html": source},
                    False,
                    image_options,
                    umo=umo or None,
                )
                if not result:
                    raise RuntimeError("词云 T2I 未返回图片")
                content: bytes | None = result if isinstance(result, bytes) else None
                if isinstance(result, str) and not result.startswith(
                    ("https://", "http://")
                ):
                    path = Path(result)
                    if path.is_file():
                        content = await asyncio.to_thread(path.read_bytes)
                if content:
                    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
                        raise RuntimeError("词云 T2I 返回内容不是 PNG 图片")
                    await asyncio.to_thread(self._store_image, cache_file, content)
                    return str(cache_file)
                return result
            finally:
                self._active_images.discard(cache_file)
