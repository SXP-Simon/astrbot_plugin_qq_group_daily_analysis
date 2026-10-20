"""漫画模板查看命令的目录、参数与示例图片安全边界。"""

from __future__ import annotations

import ast
import inspect
import os
import re
import types
import typing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from astrbot.api.message_components import Image, Plain
from astrbot.core.star.filter.command import GreedyStr

from src.application.services.template_command_service import TemplateCommandService
from src.shared.comic_prompts import COMIC_PROMPT_PREVIEWS, COMIC_TEMPLATE_NAMES

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def command_service(tmp_path: Path) -> TemplateCommandService:
    """建立没有外部配置与报告模板目录的服务。"""
    return TemplateCommandService(str(tmp_path))


def test_comic_catalog_uses_shared_order_and_contains_no_thumbnail_entries(
    command_service: TemplateCommandService,
):
    """目录顺序与 WebUI 共用清单一致，每个风格只出现一次。"""
    template_ids = command_service.list_comic_templates()

    assert template_ids == list(COMIC_TEMPLATE_NAMES)
    assert len(template_ids) == 14
    assert len(set(template_ids)) == len(template_ids)
    assert "custom" not in template_ids
    assert not any("thumb" in template_id for template_id in template_ids)


@pytest.mark.parametrize("template_id", list(COMIC_TEMPLATE_NAMES))
def test_comic_input_accepts_number_id_and_full_name(
    command_service: TemplateCommandService, template_id: str
):
    """序号、内部 ID 和完整中文名指向同一个模板。"""
    ordinal = list(COMIC_TEMPLATE_NAMES).index(template_id) + 1
    for value in (
        str(ordinal),
        template_id,
        COMIC_TEMPLATE_NAMES[template_id],
        f"  {template_id}  ",
    ):
        assert command_service.parse_comic_template_input(value) == (template_id, None)


@pytest.mark.parametrize(
    "value", ["0", "15", "999", "-1", "unknown", "../classic", "²", "1" * 5000]
)
def test_comic_input_rejects_unknown_or_out_of_range_values(
    command_service: TemplateCommandService, value: str
):
    """无效输入不能静默选择其他模板。"""
    selected, error = command_service.parse_comic_template_input(value)

    assert selected is None
    assert error


@pytest.mark.parametrize("value", ["custom", "自定义"])
def test_comic_custom_input_explains_missing_builtin_preview(
    command_service: TemplateCommandService, value: str
):
    """自定义模板得到专门说明，不会伪装成内置风格。"""
    selected, error = command_service.parse_comic_template_input(value)

    assert selected is None
    assert error and "自定义" in error and ("预览" in error or "示例" in error)


def test_comic_directory_text_lists_ids_names_and_single_preview_command(
    command_service: TemplateCommandService,
):
    """普通平台可通过文字目录找到合法的单张预览参数。"""
    text = command_service.build_comic_template_list_text()

    for template_id, name in COMIC_TEMPLATE_NAMES.items():
        assert template_id in text
        assert name in text
    assert "/查看漫画模板" in text
    assert "/设置模板" not in text


@pytest.mark.parametrize("template_id", list(COMIC_TEMPLATE_NAMES))
def test_comic_preview_resolves_only_full_catalog_image(template_id: str):
    """发给群聊的是完整示例图，缩略图只供 WebUI 使用。"""
    service = TemplateCommandService(str(PLUGIN_ROOT))

    resolved = service.resolve_comic_template_preview_path(template_id)

    assert resolved is not None
    assert (
        Path(resolved).resolve()
        == (
            PLUGIN_ROOT
            / "assets"
            / "comic_previews"
            / COMIC_PROMPT_PREVIEWS[template_id]
        ).resolve()
    )
    assert not Path(resolved).stem.endswith("-thumb")


@pytest.mark.parametrize(
    "value", ["custom", "../classic", "classic.webp", "classic-thumb", "unknown"]
)
def test_comic_preview_rejects_paths_and_non_catalog_names(
    command_service: TemplateCommandService, value: str
):
    """调用者无法把任意文件名作为模板名读取。"""
    assert command_service.resolve_comic_template_preview_path(value) is None


def test_comic_preview_missing_file_returns_none(
    command_service: TemplateCommandService,
):
    """资源缺失由消息层提供提示，不拼接不存在的本地图。"""
    assert command_service.resolve_comic_template_preview_path("classic") is None


def test_comic_preview_rejects_escaped_catalog_filename(
    command_service: TemplateCommandService,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """即使目录数据损坏，也不能从漫画图片目录外读取资源。"""
    previews = tmp_path / "assets" / "comic_previews"
    previews.mkdir(parents=True)
    (previews.parent / "outside.webp").write_bytes(b"outside-preview")
    monkeypatch.setitem(COMIC_PROMPT_PREVIEWS, "classic", "../outside.webp")

    assert command_service.resolve_comic_template_preview_path("classic") is None


def test_comic_preview_rejects_symlink_assets_root(
    command_service: TemplateCommandService, tmp_path: Path
):
    """资源根目录本身也不得通过符号链接指向外部。"""
    outside = tmp_path.parent / f"{tmp_path.name}-outside-assets"
    previews = outside / "comic_previews"
    previews.mkdir(parents=True)
    (previews / COMIC_PROMPT_PREVIEWS["classic"]).write_bytes(b"external-preview")
    try:
        os.symlink(outside, tmp_path / "assets", target_is_directory=True)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"当前测试环境不能创建符号链接: {error}")

    assert command_service.resolve_comic_template_preview_path("classic") is None


@pytest.mark.parametrize("link_directory", [False, True])
def test_comic_preview_rejects_symlink_file_and_directory_escape(
    command_service: TemplateCommandService, tmp_path: Path, link_directory: bool
):
    """目录或文件链接均不能使漫画预览读取根目录外的文件。"""
    root = Path(command_service.plugin_root)
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    filename = COMIC_PROMPT_PREVIEWS["classic"]
    (outside / filename).write_bytes(b"external-preview")
    assets = root / "assets"
    assets.mkdir()
    previews = assets / "comic_previews"
    try:
        if link_directory:
            os.symlink(outside, previews, target_is_directory=True)
        else:
            previews.mkdir()
            os.symlink(outside / filename, previews / filename)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"当前测试环境不能创建符号链接: {error}")

    assert command_service.resolve_comic_template_preview_path("classic") is None


def test_comic_nodes_contain_one_full_image_per_template_and_keep_global_numbers(
    command_service: TemplateCommandService, tmp_path: Path
):
    """即便只展示末项，其编号也与完整目录保持一致。"""
    template_ids = command_service.list_comic_templates()
    selected = template_ids[-1]
    previews = tmp_path / "assets" / "comic_previews"
    previews.mkdir(parents=True)
    image_path = previews / COMIC_PROMPT_PREVIEWS[selected]
    image_path.write_bytes(b"preview")

    with patch.object(Image, "fromFileSystem", return_value=Image()) as image_factory:
        nodes = command_service.build_comic_template_preview_nodes([selected], "10000")

    assert len(nodes.nodes) == 2
    assert all(str(node.uin) == "10000" for node in nodes.nodes)
    content = nodes.nodes[1].content
    text = "\n".join(part.text for part in content if isinstance(part, Plain))
    assert COMIC_TEMPLATE_NAMES[selected] in text
    assert selected in text
    assert command_service._format_index_label(len(template_ids) - 1) in text
    assert len([part for part in content if isinstance(part, Image)]) == 1
    image_factory.assert_called_once()
    assert Path(image_factory.call_args.args[0]).resolve() == image_path.resolve()


def test_comic_nodes_missing_preview_retain_template_name_and_explanation(
    command_service: TemplateCommandService,
):
    """缺少一张资源不会导致整个模板列表发送失败。"""
    with patch.object(Image, "fromFileSystem") as image_factory:
        nodes = command_service.build_comic_template_preview_nodes(["classic"], "10000")

    assert len(nodes.nodes) == 2
    text = "\n".join(
        part.text for part in nodes.nodes[1].content if isinstance(part, Plain)
    )
    assert COMIC_TEMPLATE_NAMES["classic"] in text
    assert "预览" in text or "示例" in text
    image_factory.assert_not_called()


def test_comic_command_signature_keeps_greedy_marker_without_default():
    """框架对有默认值的参数忽略类型，因此贪婪标记必须没有默认值。"""
    from astrbot_plugin_qq_group_daily_analysis.main import GroupDailyAnalysis

    signature = inspect.signature(
        GroupDailyAnalysis.view_comic_templates, eval_str=True
    )
    parameter = signature.parameters["template_input"]

    assert parameter.annotation is GreedyStr
    assert parameter.default is inspect.Parameter.empty


@pytest.fixture
def host_command_filter():
    """载入真实宿主解析器，避免用测试内复制的算法验证自己。

    Returns:
        真实宿主源码的 CommandFilter 类；未安装宿主时跳过集成用例。
    """
    roots = list(PLUGIN_ROOT.parents)
    configured_root = os.environ.get("ASTRBOT_TEST_ROOT")
    if configured_root:
        roots.insert(0, Path(configured_root))
    command_path = next(
        (
            path
            for root in roots
            if (path := root / "astrbot/core/star/filter/command.py").is_file()
        ),
        None,
    )
    if command_path is None:
        pytest.skip(
            "未发现真实 AstrBot 宿主；可设置 ASTRBOT_TEST_ROOT 运行解析集成测试"
        )

    # 只隔离框架初始化依赖，解析与签名提取方法完整来自未改动的宿主源码。
    parsed = ast.parse(command_path.read_text(encoding="utf-8"))
    definitions = [
        node
        for node in parsed.body
        if isinstance(node, ast.ClassDef | ast.FunctionDef)
        and node.name in {"CommandFilter", "unwrap_optional"}
    ]
    assert {node.name for node in definitions} == {
        "CommandFilter",
        "unwrap_optional",
    }
    isolated_module = ast.Module(
        body=[
            ast.parse("from __future__ import annotations").body[0],
            *definitions,
        ],
        type_ignores=[],
    )
    namespace = {
        "inspect": inspect,
        "re": re,
        "types": types,
        "typing": typing,
        "GreedyStr": GreedyStr,
        "HandlerFilter": object,
    }
    exec(compile(isolated_module, str(command_path), "exec"), namespace)
    return namespace["CommandFilter"]


@pytest.mark.parametrize("command_name", ["查看漫画模板", "view_comic_templates"])
@pytest.mark.parametrize(
    ("input_value", "expected_template"),
    [
        ("", None),
        ("3", "noir_detective"),
        (COMIC_TEMPLATE_NAMES["pixel_rpg"], "pixel_rpg"),
        (COMIC_TEMPLATE_NAMES["scp_dossier"], "scp_dossier"),
    ],
)
def test_real_host_command_parser_preserves_spaced_names_and_empty_parameter(
    host_command_filter,
    command_service: TemplateCommandService,
    command_name: str,
    input_value: str,
    expected_template: str | None,
):
    """经过真实签名提取、分词、转换流程，空参数与完整中文名都可用。"""
    from astrbot_plugin_qq_group_daily_analysis.main import GroupDailyAnalysis

    command_filter = host_command_filter(
        "查看漫画模板",
        alias={"view_comic_templates"},
        handler_md=SimpleNamespace(handler=GroupDailyAnalysis.view_comic_templates),
    )
    extra: dict[str, object] = {}
    event = SimpleNamespace(
        is_at_or_wake_command=True,
        get_message_str=lambda: f"{command_name} {input_value}",
        set_extra=lambda key, value: extra.__setitem__(key, value),
    )

    assert command_filter.filter(event, {}) is True
    assert extra["parsed_params"] == {"template_input": input_value}
    if expected_template is not None:
        assert command_service.parse_comic_template_input(input_value) == (
            expected_template,
            None,
        )
