"""
HTML模板模块
使用Jinja2加载外部HTML模板文件
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import threading
from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape

from ...utils.logger import logger


class HTMLTemplates:
    """HTML模板管理类"""

    def __init__(self, config_manager):
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

    KNOWN_TEMPLATE_NAMES: dict[str, str] = {
        "scrapbook": "手账风格 (Scrapbook / 默认)",
        "ATRI": "亚托莉 (ATRI)",
        "HatsuneMiku": "初音未来 (HatsuneMiku)",
        "spring_festival": "新春佳节 (Spring Festival)",
        "retro_futurism": "复古未来 (Retro Futurism)",
        "hack": "黑客赛博 (Hack)",
        "BlueArchive": "蔚蓝档案 (BlueArchive)",
        "simple": "极简黑白 (Simple)",
    }

    def _get_env_sync(self, template_theme: str | None = None) -> Environment:
        """获取当前配置或指定主题的模板环境（同步版本，供 asyncio.to_thread 调用）"""
        template_name = template_theme or self.config_manager.get_report_template()

        # 如果环境已缓存且配置未变（使用锁保证多线程安全）
        with self._env_lock:
            env = self._envs.get(template_name)
            if env is not None:
                return env

        template_dir = os.path.join(self.base_dir, template_name)
        get_custom_template_dir = getattr(
            self.config_manager, "get_custom_report_template_dir", None
        )
        custom_template_res = (
            get_custom_template_dir(template_name)
            if callable(get_custom_template_dir)
            else None
        )
        custom_template_dir = (
            Path(str(custom_template_res)) if custom_template_res else None
        )

        loaders = []
        if custom_template_dir and custom_template_dir.exists():
            loaders.append(FileSystemLoader(str(custom_template_dir)))
        if os.path.exists(template_dir):
            loaders.append(FileSystemLoader(template_dir))

        # 若目标模板既不在自定义目录也不在内置目录，回退到默认的 scrapbook
        if not loaders:
            logger.warning(f"模板目录不存在: {template_dir}，回退到 scrapbook")
            template_name = "scrapbook"
            template_dir = os.path.join(self.base_dir, template_name)
            loaders.append(FileSystemLoader(template_dir))
        else:
            # 无论何种情况，将默认的 scrapbook 目录追加为最底层 Fallback，避免自定义模板缺少局部组件时渲染失败
            default_dir = os.path.join(self.base_dir, "scrapbook")
            if default_dir != template_dir and not any(
                isinstance(ld, FileSystemLoader) and ld.searchpath == [default_dir]
                for ld in loaders
            ):
                loaders.append(FileSystemLoader(default_dir))

        env = Environment(
            loader=ChoiceLoader(loaders),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # 使用双重检查锁定，避免在高并发下重复创建相同 template_name 的 env
        with self._env_lock:
            existing = self._envs.get(template_name)
            if existing is not None:
                return existing
            self._envs[template_name] = env

        return env

    def get_available_templates(self) -> list[dict[str, Any]]:
        """动态扫描内置与自定义数据目录，返回所有可用的视觉主题模板列表"""
        found_themes: dict[str, dict[str, Any]] = {}

        # 1. 扫描内置模板目录
        if os.path.isdir(self.base_dir):
            for entry in sorted(os.listdir(self.base_dir)):
                if entry.startswith(".") or entry == "format":
                    continue
                p = os.path.join(self.base_dir, entry)
                if os.path.isdir(p):
                    has_image = os.path.exists(os.path.join(p, "image_template.html"))
                    has_html = os.path.exists(os.path.join(p, "html_template.html"))
                    if has_image or has_html:
                        label = self.KNOWN_TEMPLATE_NAMES.get(
                            entry, f"{entry} (内置模板)"
                        )
                        found_themes[entry] = {
                            "id": entry,
                            "label": label,
                            "is_custom": False,
                            "has_image": has_image,
                            "has_html": has_html,
                        }

        # 2. 扫描用户自定义模板目录
        get_custom_dir = getattr(
            self.config_manager, "get_custom_report_template_dir", None
        )
        custom_base: Path | None = None
        if callable(get_custom_dir):
            sample_res = get_custom_dir("")
            if sample_res:
                p_sample = Path(str(sample_res))
                custom_base = p_sample if p_sample.is_dir() else p_sample.parent

        if custom_base and custom_base.is_dir():
            for p in sorted(custom_base.iterdir()):
                if p.is_dir() and not p.name.startswith("."):
                    entry = p.name
                    has_image = (p / "image_template.html").exists()
                    has_html = (p / "html_template.html").exists()
                    if has_image or has_html:
                        builtin_label = self.KNOWN_TEMPLATE_NAMES.get(entry)
                        builtin_dir = os.path.join(self.base_dir, entry)

                        is_custom = True
                        if builtin_label and os.path.isdir(builtin_dir):
                            # 对比自定义目录与内置目录中的所有 HTML 文件哈希，避免未修改时误判
                            is_truly_modified = False
                            for ch_file in p.glob("*.html"):
                                bh_file = Path(builtin_dir) / ch_file.name
                                if not bh_file.exists():
                                    is_truly_modified = True
                                    break
                                try:
                                    if (
                                        hashlib.sha256(ch_file.read_bytes()).digest()
                                        != hashlib.sha256(bh_file.read_bytes()).digest()
                                    ):
                                        is_truly_modified = True
                                        break
                                except Exception:
                                    is_truly_modified = True
                                    break

                            if not is_truly_modified:
                                is_custom = False
                                custom_label = builtin_label
                            else:
                                custom_label = f"{builtin_label} (自定义修改版)"
                        else:
                            custom_label = f"{entry} (自定义本地模板)"

                        found_themes[entry] = {
                            "id": entry,
                            "label": custom_label,
                            "is_custom": is_custom,
                            "has_image": has_image,
                            "has_html": has_html,
                        }

        # 确保默认的 scrapbook 始终位于第一个
        result = []
        if "scrapbook" in found_themes:
            result.append(found_themes.pop("scrapbook"))
        result.extend(found_themes.values())
        return result

    async def _get_env_async(self, template_theme: str | None = None) -> Environment:
        """获取当前配置或指定主题的模板环境（异步版本）"""
        return await asyncio.to_thread(self._get_env_sync, template_theme)

    def _get_env(self, template_theme: str | None = None) -> Environment:
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
        self, template_name: str, template_theme: str | None = None, **kwargs
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
        self, platform_name: str, template_name: str, **kwargs
    ) -> str:
        """渲染与报告主题解耦的平台专用模板。"""
        try:
            template_dir = os.path.join(self.platform_base_dir, platform_name)
            env = Environment(
                loader=FileSystemLoader(template_dir),
                autoescape=select_autoescape(["html", "xml"]),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            return env.get_template(template_name).render(**kwargs)
        except Exception as e:
            logger.error(f"渲染平台模板 {platform_name}/{template_name} 失败: {e}")
            return ""
