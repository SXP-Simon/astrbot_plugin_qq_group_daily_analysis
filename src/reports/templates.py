"""
HTML模板模块
使用Jinja2加载外部HTML模板文件
"""

import os
from astrbot.api import logger
from jinja2 import Environment, FileSystemLoader, select_autoescape


class HTMLTemplates:
    """HTML模板管理类"""

    def __init__(self):
        """初始化Jinja2环境"""
        # 设置模板目录
        template_dir = os.path.join(os.path.dirname(__file__), "templates")

        # 创建Jinja2环境
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def get_image_template(self) -> str:
        """获取图片报告的HTML模板（返回原始模板字符串）"""
        try:
            # 获取模板对象
            template = self.jinja_env.get_template("image_template.html")
            # 读取原始模板文件内容，而不是渲染它
            with open(template.filename, encoding="utf-8") as f:
                return f.read()
        except Exception:
            # 如果加载失败，返回空字符串让调用者处理
            logger.error("加载图片模板失败")
            return ""

    def get_pdf_template(self) -> str:
        """获取PDF报告的HTML模板（返回原始模板字符串）"""
        try:
            # 获取模板对象
            template = self.jinja_env.get_template("pdf_template.html")
            # 读取原始模板文件内容，而不是渲染它
            with open(template.filename, encoding="utf-8") as f:
                return f.read()
        except Exception:
            # 如果加载失败，返回空字符串让调用者处理
            logger.error("加载PDF模板失败")
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
            template = self.jinja_env.get_template(template_name)
            return template.render(**kwargs)
        except Exception:
            logger.error(f"渲染模板 {template_name} 失败")
            return ""
