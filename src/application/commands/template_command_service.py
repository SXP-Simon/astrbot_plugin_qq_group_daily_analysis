"""模板管理相关命令服务。"""

from __future__ import annotations

import asyncio
import os

from astrbot.api.message_components import (
    BaseMessageComponent,
    Image,
    Node,
    Nodes,
    Plain,
)


class TemplateCommandService:
    """封装模板命令的文件系统与消息构建逻辑。"""

    _CIRCLE_NUMBERS = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]

    def __init__(self, plugin_root: str):
        self.plugin_root = plugin_root

    def resolve_template_base_dir(self) -> str:
        """解析报告模板目录（兼容新旧目录结构）。"""
        candidate_dirs = [
            os.path.join(
                self.plugin_root, "src", "infrastructure", "reporting", "templates"
            ),
            os.path.join(self.plugin_root, "src", "reports", "templates"),
        ]
        for candidate in candidate_dirs:
            if os.path.isdir(candidate):
                return candidate
        return candidate_dirs[0]

    def resolve_template_preview_path(self, template_name: str) -> str | None:
        """解析模板预览图路径。

        优先级：
        1. 自定义模板目录内随模板打包的预览图
           （custom_t2i_templates/reporting_templates/<模板名>/ 下的
           preview.jpg/png 或 demo.jpg/png）；
        2. 插件仓库 assets/<模板名>-demo.jpg（本地）；
        3. 无本地文件时返回 None，由调用方回退仓库图库链接。
        """
        from ...infrastructure.reporting.template_installer import (
            default_template_store_dir,
        )

        custom_dir = default_template_store_dir() / template_name
        for candidate_name in ("preview.jpg", "preview.png", "demo.jpg", "demo.png"):
            candidate = custom_dir / candidate_name
            if candidate.is_file():
                return str(candidate)

        candidate_paths = [
            os.path.join(self.plugin_root, "assets", f"{template_name}-demo.jpg"),
        ]
        for candidate in candidate_paths:
            if os.path.exists(candidate):
                return candidate
        return None

    def list_available_templates(self) -> list[str]:
        """获取本地所有可用模板名称列表（内置 + 用户自定义）。"""
        from ...infrastructure.reporting.template_installer import (
            default_template_store_dir,
        )

        templates: set[str] = set()

        base_dir = self.resolve_template_base_dir()
        if os.path.isdir(base_dir):
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                if not os.path.isdir(item_path):
                    continue
                if item.startswith("__") or item.startswith(".") or item == "format":
                    continue
                if (
                    os.path.isfile(os.path.join(item_path, "html_template.html"))
                    or os.path.isfile(os.path.join(item_path, "image_template.html"))
                    or os.path.isfile(os.path.join(item_path, "template.html"))
                ):
                    templates.add(item)

        custom_dir = default_template_store_dir()
        if custom_dir.is_dir():
            for item in os.listdir(custom_dir):
                item_path = custom_dir / item
                if not item_path.is_dir() or item.startswith("."):
                    continue
                if (
                    (item_path / "html_template.html").is_file()
                    or (item_path / "image_template.html").is_file()
                ):
                    templates.add(item)

        return sorted(templates)

    async def template_exists(self, template_name: str) -> bool:
        """检查模板目录是否存在且包含有效模板文件。"""
        template_dir = os.path.join(self.resolve_template_base_dir(), template_name)
        if not await asyncio.to_thread(os.path.isdir, template_dir):
            return False
        return await asyncio.to_thread(
            lambda: (
                os.path.isfile(os.path.join(template_dir, "html_template.html"))
                or os.path.isfile(os.path.join(template_dir, "image_template.html"))
                or os.path.isfile(os.path.join(template_dir, "template.html"))
            )
        )

    def parse_template_input(
        self, template_input: str, available_templates: list[str]
    ) -> tuple[str | None, str | None]:
        """解析模板输入（支持模板名或序号）。"""
        if not template_input:
            return None, "❌ 模板参数不能为空"

        if template_input.isdigit():
            index = int(template_input)
            if 1 <= index <= len(available_templates):
                return available_templates[index - 1], None
            return (
                None,
                f"❌ 无效的序号 '{template_input}'，有效范围: 1-{len(available_templates)}",
            )

        return template_input, None

    def build_template_preview_nodes(
        self,
        available_templates: list[str],
        current_template: str,
        bot_id: str,
    ) -> Nodes:
        """构建模板预览的合并消息节点。"""
        node_list: list[Node] = []

        header_content: list[BaseMessageComponent] = [
            Plain(
                f"🎨 可用报告模板列表\n📌 当前使用: {current_template}\n💡 使用 /设置模板 [序号] 切换"
            )
        ]
        node_list.append(Node(uin=bot_id, name="模板预览", content=header_content))

        for index, template_name in enumerate(available_templates):
            current_mark = " ✅" if template_name == current_template else ""
            num_label = (
                self._CIRCLE_NUMBERS[index]
                if index < len(self._CIRCLE_NUMBERS)
                else f"({index + 1})"
            )

            node_content: list[BaseMessageComponent] = [
                Plain(f"{num_label} {template_name}{current_mark}")
            ]
            preview_image_path = self.resolve_template_preview_path(template_name)
            if preview_image_path:
                node_content.append(Image.fromFileSystem(preview_image_path))
            else:
                cdn_url = f"https://fastly.jsdelivr.net/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/{template_name}-demo.jpg"
                node_content.append(Image.fromURL(cdn_url))

            node_list.append(Node(uin=bot_id, name=template_name, content=node_content))

        return Nodes(node_list)

    build_preview_nodes = build_template_preview_nodes
