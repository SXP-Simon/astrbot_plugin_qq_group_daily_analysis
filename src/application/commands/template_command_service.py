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
        """解析模板预览图路径。"""
        candidate_paths = [
            os.path.join(self.plugin_root, "assets", f"{template_name}-demo.jpg"),
        ]
        for candidate in candidate_paths:
            if os.path.exists(candidate):
                return candidate
        return None

    async def list_available_templates(self) -> list[str]:
        """列出所有可用模板。"""
        template_base_dir = self.resolve_template_base_dir()

        def _list_templates_sync() -> list[str]:
            if os.path.exists(template_base_dir):
                return sorted(
                    [
                        d
                        for d in os.listdir(template_base_dir)
                        if os.path.isdir(os.path.join(template_base_dir, d))
                        and not d.startswith("__")
                    ]
                )
            return []

        return await asyncio.to_thread(_list_templates_sync)

    async def template_exists(self, template_name: str) -> bool:
        """检查模板目录是否存在。"""
        template_dir = os.path.join(self.resolve_template_base_dir(), template_name)
        return await asyncio.to_thread(os.path.exists, template_dir)

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
        node_list = []

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
                node_content.append(
                    Image(
                        file=f"file:///{os.path.abspath(preview_image_path)}",
                        path=preview_image_path,
                    )
                )

            node_list.append(Node(uin=bot_id, name=template_name, content=node_content))

        return Nodes(node_list)
