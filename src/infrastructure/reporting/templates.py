"""
HTML模板模块
使用Jinja2加载外部HTML模板文件
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, TypedDict

from jinja2 import ChoiceLoader, FileSystemLoader, select_autoescape
from jinja2.sandbox import SandboxedEnvironment

from ...shared.type_guards import is_string_mapping
from ...utils.logger import logger
from .template_installer import (
    template_dir_has_symlink_entries,
    validate_template_name,
)

if TYPE_CHECKING:
    from ..config.config_manager import ConfigManager


class ReportTemplateInfo(TypedDict):
    """模板可用入口与展示元信息，不把 HTML 图片和原生图片混为一谈。"""

    id: str
    label: str
    is_custom: bool
    has_image: bool
    has_html: bool
    has_typst: bool
    display_name: str
    desc: str
    tag: str
    tag_color: str
    can_uninstall: bool


class HTMLTemplates:
    """HTML模板管理类"""

    KNOWN_TEMPLATE_NAMES: ClassVar[dict[str, str]] = {
        "HatsuneMiku": "初音未来 (HatsuneMiku / 默认)",
        "scrapbook": "手账风格 (Scrapbook)",
        "ATRI": "亚托莉 (ATRI)",
        "spring_festival": "新春佳节 (Spring Festival)",
        "retro_futurism": "复古未来 (Retro Futurism)",
        "hack": "黑客赛博 (Hack)",
        "BlueArchive": "蔚蓝档案 (BlueArchive)",
        "simple": "极简黑白 (Simple)",
        "art_nouveau": "新艺术运动 (Art Nouveau)",
        "deepseek_maid": "DeepSeek 鲸鱼女仆娘",
        "maria": "圣母在上 (Maria)",
    }

    config_manager: ConfigManager
    base_dir: str
    platform_base_dir: str
    _envs: dict[str, SandboxedEnvironment]
    _env_lock: threading.Lock

    def __init__(self, config_manager: ConfigManager) -> None:
        """初始化Jinja2环境"""
        self.config_manager = config_manager
        # 设置模板根目录
        self.base_dir = os.path.join(os.path.dirname(__file__), "templates")
        self.platform_base_dir = os.path.join(
            os.path.dirname(__file__), "platform_templates"
        )
        # 缓存不同模板的Jinja2环境（多线程安全）
        self._envs = {}
        self._env_lock = threading.Lock()

    def _get_env_sync(self, template_theme: str | None = None) -> SandboxedEnvironment:
        """获取当前配置或指定主题的模板环境（同步版本，供 asyncio.to_thread 调用）"""
        template_name = template_theme or self.config_manager.get_report_template()

        # 如果环境已缓存且配置未变（使用锁保证多线程安全）
        with self._env_lock:
            env = self._envs.get(template_name)
            if env is not None:
                return env

        # 模板名安全校验：拒绝路径分隔符/穿越（渲染入口的最终防线）
        clean_name = validate_template_name(template_name)

        template_dir = os.path.join(self.base_dir, clean_name)
        custom_template_res = self.config_manager.get_custom_report_template_dir(
            clean_name
        )
        custom_template_dir = (
            Path(str(custom_template_res)) if custom_template_res else None
        )

        loaders: list[FileSystemLoader] = []
        # 1. 官方内置模板：优先加载官方内置模板目录，绝不加载任何自定义覆盖，保持官方模板的纯净与最新
        if os.path.exists(template_dir):
            loaders.append(FileSystemLoader(template_dir))
        # 2. 用户自定义模板：如果不是官方内置模板，从用户自定义模板目录加载
        elif (
            custom_template_dir
            and custom_template_dir.exists()
            and not custom_template_dir.is_symlink()
            and not template_dir_has_symlink_entries(custom_template_dir)
        ):
            loaders.append(FileSystemLoader(str(custom_template_dir)))

        # 若目标模板既不在内置目录也不在自定义目录，明确抛出未找到异常
        if not loaders:
            raise FileNotFoundError(f"未找到指定的报告主题模板「{clean_name}」")

        source = (
            Path(template_dir) if Path(template_dir).is_dir() else custom_template_dir
        )
        if source and not any(
            (source / name).is_file()
            for name in ("image_template.html", "html_template.html")
        ):
            raise ValueError(
                f"主题「{clean_name}」仅支持 Typst 图片，不能用于 HTML 渲染或网页输出"
            )

        # 将默认的 scrapbook 目录追加为最底层 Fallback，避免自定义模板缺少局部组件时渲染失败
        default_dir = os.path.join(self.base_dir, "scrapbook")
        if default_dir != template_dir and not any(
            ld.searchpath == [default_dir] for ld in loaders
        ):
            loaders.append(FileSystemLoader(default_dir))

        env = SandboxedEnvironment(
            loader=ChoiceLoader(loaders),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
            # 沙箱模式：禁止模板访问 dunder 属性/敏感对象（防第三方模板 SSTI→RCE）
        )

        # 使用双重检查锁定，避免在高并发下重复创建相同 template_name 的 env
        with self._env_lock:
            existing = self._envs.get(template_name)
            if existing is not None:
                return existing
            self._envs[template_name] = env

        return env

    def get_available_templates(self) -> list[ReportTemplateInfo]:
        """扫描模板的真实入口，内置目录优先于同名的用户目录。

        Returns:
            带 HTML 图片、HTML 网页和 Typst 能力标记的模板列表。
        """
        found: dict[str, ReportTemplateInfo] = {}
        builtin = Path(self.base_dir)
        custom = self.config_manager.get_custom_report_template_dir("")
        roots = [(builtin, False)]
        if custom:
            custom = Path(custom)
            roots.append((custom if custom.is_dir() else custom.parent, True))
        builtin_names: set[str] = (
            {path.name for path in builtin.iterdir() if path.is_dir()}
            if builtin.is_dir()
            else set()
        )
        for root, is_custom in roots:
            if not root.is_dir() or root.is_symlink():
                continue
            for directory in sorted(root.iterdir()):
                name = directory.name
                if (
                    not directory.is_dir()
                    or directory.is_symlink()
                    or name.startswith(".")
                    or template_dir_has_symlink_entries(directory)
                    or (is_custom and name in builtin_names)
                ):
                    continue
                has_image = (directory / "image_template.html").is_file()
                has_html = (directory / "html_template.html").is_file()
                has_typst = (directory / "report.typ").is_file()
                if not (has_image or has_html or has_typst):
                    continue
                meta = self._read_template_meta(directory)
                display_name = meta.get("name") or name
                label = (
                    (
                        f"{display_name} ({name})"
                        if meta.get("name")
                        else f"{name} (自定义主题)"
                    )
                    if is_custom
                    else self.KNOWN_TEMPLATE_NAMES.get(
                        name, f"{display_name} (内置模板)"
                    )
                )
                found[name] = {
                    "id": name,
                    "label": label,
                    "is_custom": is_custom,
                    "has_image": has_image,
                    "has_html": has_html,
                    "has_typst": has_typst,
                    "display_name": display_name,
                    "desc": meta.get("desc", ""),
                    "tag": meta.get("tag", ""),
                    "tag_color": meta.get("tag_color", ""),
                    "can_uninstall": is_custom,
                }
        return sorted(
            found.values(), key=lambda item: (item["id"] != "HatsuneMiku", item["id"])
        )

    @staticmethod
    def _read_template_meta(template_dir: str | Path) -> dict[str, str]:
        """读取模板目录中可选 template.json 的展示元信息（name/desc/tag/tag_color）。"""
        meta_path = os.path.join(template_dir, "template.json")
        if not os.path.isfile(meta_path):
            return {}
        try:
            with open(meta_path, encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            return {}
        meta: dict[str, str] = {}
        if not is_string_mapping(raw):
            return meta
        for key in ("name", "desc", "tag", "tag_color"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                meta[key] = value.strip()[:100]
        return meta

    def invalidate_env(self, template_name: str) -> None:
        """使指定主题的 Jinja2 环境缓存失效（模板卸载后调用）。"""
        with self._env_lock:
            self._envs.pop(template_name, None)

    async def _get_env_async(
        self, template_theme: str | None = None
    ) -> SandboxedEnvironment:
        """获取当前配置或指定主题的模板环境（异步版本）"""
        return await asyncio.to_thread(self._get_env_sync, template_theme)

    def _get_env(self, template_theme: str | None = None) -> SandboxedEnvironment:
        """获取当前配置或指定主题的模板环境（同步版本，向后兼容）"""
        return self._get_env_sync(template_theme=template_theme)

    def _read_template_file_sync(self, filename: str) -> str:
        """同步读取模板文件内容"""
        with open(filename, encoding="utf-8") as f:
            return f.read()

    async def get_image_template_async(self) -> str:
        """获取图片报告的HTML模板（异步版本，返回原始模板字符串）"""
        try:
            env = await self._get_env_async()
            template = env.get_template("image_template.html")
            if template.filename is None:
                logger.error("图片模板路径为空")
                return ""
            return await asyncio.to_thread(
                self._read_template_file_sync, template.filename
            )
        except Exception as e:
            logger.error(f"加载图片模板失败: {e}")
            return ""

    def get_image_template(self) -> str:
        """获取图片报告的HTML模板（同步版本，向后兼容）"""
        try:
            env = self._get_env()
            template = env.get_template("image_template.html")
            if template.filename is None:
                logger.error("图片模板路径为空")
                return ""
            with open(template.filename, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"加载图片模板失败: {e}")
            return ""

    def render_template(
        self, template_name: str, template_theme: str | None = None, **kwargs: object
    ) -> str:
        """渲染指定的模板文件

        Args:
            template_name: 模板文件名
            template_theme: 可选指定的主题模板名称
            **kwargs: 传递给模板的变量

        Returns:
            渲染后的HTML字符串
        """
        try:
            env = self._get_env(template_theme=template_theme)
            template = env.get_template(template_name)
            return template.render(**kwargs)
        except Exception as e:
            logger.error(
                f"渲染模板 {template_name} (theme: {template_theme}) 失败: {e}"
            )
            return ""

    def render_platform_template(
        self, platform_name: str, template_name: str, **kwargs: object
    ) -> str:
        """渲染与报告主题解耦的平台专用模板。"""
        try:
            template_dir = os.path.join(self.platform_base_dir, platform_name)
            env = SandboxedEnvironment(
                loader=FileSystemLoader(template_dir),
                autoescape=select_autoescape(["html", "xml"]),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            return env.get_template(template_name).render(**kwargs)
        except Exception as e:
            logger.error(f"渲染平台模板 {platform_name}/{template_name} 失败: {e}")
            return ""
