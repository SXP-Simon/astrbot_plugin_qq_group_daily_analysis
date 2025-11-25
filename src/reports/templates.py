"""
HTML模板模块
使用Jinja2加载外部HTML模板文件
"""

import os

from jinja2 import Environment, FileSystemLoader, select_autoescape

from astrbot.api import logger


class HTMLTemplates:
    """HTML模板管理类"""

    def __init__(self, config_manager):
        """初始化Jinja2环境"""
        self.config_manager = config_manager
        # 设置模板根目录
        self.base_dir = os.path.join(os.path.dirname(__file__), "templates")
        # 缓存不同模板的Jinja2环境
        self._envs = {}

    def _get_env(self) -> Environment:
        """获取当前配置的模板环境"""
        template_name = self.config_manager.get_report_template()

        # 如果环境已缓存且配置未变（这里简单假设配置变了会重新获取，或者我们可以每次都检查）
        # 为了响应配置热更，我们每次都检查一下或者简单地按需创建
        if template_name in self._envs:
            return self._envs[template_name]

        template_dir = os.path.join(self.base_dir, template_name)
        if not os.path.exists(template_dir):
            logger.warning(f"模板目录不存在: {template_dir}，回退到 scrapbook")
            template_dir = os.path.join(self.base_dir, "scrapbook")
            # 如果 scrapbook 也不存在，那就有大问题了，不过这里假设 scrapbook 一定存在

        env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._envs[template_name] = env
        return env

    def get_image_template(self) -> str:
        """获取图片报告的HTML模板（返回原始模板字符串）"""
        try:
            env = self._get_env()
            # 获取模板对象
            template = env.get_template("image_template.html")
            # 读取原始模板文件内容，而不是渲染它
            with open(template.filename, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            # 如果加载失败，返回空字符串让调用者处理
            logger.error(f"加载图片模板失败: {e}")
            return ""

    def get_pdf_template(self) -> str:
        """获取PDF报告的HTML模板（返回原始模板字符串）"""
        try:
            env = self._get_env()
            # 获取模板对象
            template = env.get_template("pdf_template.html")
            # 读取原始模板文件内容，而不是渲染它
            with open(template.filename, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            # 如果加载失败，返回空字符串让调用者处理
            logger.error(f"加载PDF模板失败: {e}")
            return ""

    def render_template(self, template_name: str, **kwargs) -> str:
        """渲染指定的模板文件

        Args:
            template_name: 模板文件名
            **kwargs: 传递给模板的变量

        Returns:
            渲染后的HTML字符串
        """
        try:
            env = self._get_env()
            template = env.get_template(template_name)
            return template.render(**kwargs)
        except Exception as e:
            logger.error(f"渲染模板 {template_name} 失败: {e}")
            return ""
