"""人格与特征映射模块

负责 MBTI / SBTI / ACGTI 人格映射数据、资源清单加载与头像推导。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...utils.logger import logger

# 默认人格特征映射表
DEFAULT_PROFILE_MAPPING = {
    "mbti": {
        "INTJ": {"code": "INTJ", "name_zh": "建筑师"},
        "INTP": {"code": "INTP", "name_zh": "逻辑学家"},
        "ENTJ": {"code": "ENTJ", "name_zh": "指挥官"},
        "ENTP": {"code": "ENTP", "name_zh": "辩论家"},
        "INFJ": {"code": "INFJ", "name_zh": "提倡者"},
        "INFP": {"code": "INFP", "name_zh": "调停者"},
        "ENFJ": {"code": "ENFJ", "name_zh": "主人公"},
        "ENFP": {"code": "ENFP", "name_zh": "竞选者"},
        "ISTJ": {"code": "ISTJ", "name_zh": "物流师"},
        "ISFJ": {"code": "ISFJ", "name_zh": "守卫者"},
        "ESTJ": {"code": "ESTJ", "name_zh": "总经理"},
        "ESTP": {"code": "ESTP", "name_zh": "企业家"},
        "ISTP": {"code": "ISTP", "name_zh": "鉴赏家"},
        "ISFP": {"code": "ISFP", "name_zh": "探险家"},
        "ESFJ": {"code": "ESFJ", "name_zh": "执政官"},
        "ESFP": {"code": "ESFP", "name_zh": "表演者"},
    },
    "sbti": {
        "INTJ": {"code": "CTRL", "name_zh": "拿捏者", "asset_code": "CTRL"},
        "INTP": {"code": "THIN-K", "name_zh": "思考者", "asset_code": "THIN-K"},
        "ENTJ": {"code": "BOSS", "name_zh": "领导者", "asset_code": "BOSS"},
        "ENTP": {"code": "JOKE-R", "name_zh": "小丑", "asset_code": "JOKE-R"},
        "INFJ": {"code": "LOVE-R", "name_zh": "多情者", "asset_code": "LOVE-R"},
        "INFP": {"code": "SOLO", "name_zh": "孤儿", "asset_code": "SOLO"},
        "ENFJ": {"code": "THAN-K", "name_zh": "感恩者", "asset_code": "THAN-K"},
        "ENFP": {"code": "GOGO", "name_zh": "行者", "asset_code": "GOGO"},
        "ISTJ": {"code": "OH-NO", "name_zh": "哦不人", "asset_code": "OH-NO"},
        "ISTP": {"code": "POOR", "name_zh": "贫困者", "asset_code": "POOR"},
        "ESTJ": {"code": "SHIT", "name_zh": "愤世者", "asset_code": "SHIT"},
        "ESTP": {"code": "WOC!", "name_zh": "握草人", "asset_code": "WOC"},
        "ISFJ": {"code": "MUM", "name_zh": "妈妈", "asset_code": "MUM"},
        "ISFP": {"code": "MALO", "name_zh": "吗喽", "asset_code": "MALO"},
        "ESFJ": {"code": "ATM-er", "name_zh": "送钱者", "asset_code": "ATM-er"},
        "ESFP": {"code": "SEXY", "name_zh": "尤物", "asset_code": "SEXY"},
    },
    "acgti": {
        "INTJ": {"code": "MRTS-X", "name_zh": "Mortis"},
        "INTP": {"code": "KNAN", "name_zh": "江户川柯南"},
        "ENTJ": {"code": "SAKI", "name_zh": "丰川祥子"},
        "ENTP": {"code": "CHKA", "name_zh": "藤原千花"},
        "INFJ": {"code": "DLRS", "name_zh": "三角初华"},
        "INFP": {"code": "BCHI", "name_zh": "后藤一里"},
        "ENFJ": {"code": "YCYO", "name_zh": "月见八千代"},
        "ENFP": {"code": "HTMK", "name_zh": "初音未来"},
        "ISTJ": {"code": "MRTS", "name_zh": "若叶睦"},
        "ISTP": {"code": "AYRE", "name_zh": "绫波丽"},
        "ESTJ": {"code": "MIKT", "name_zh": "御坂美琴"},
        "ESTP": {"code": "ASKA", "name_zh": "明日香"},
        "ISFJ": {"code": "SOYO", "name_zh": "长崎爽世"},
        "ISFP": {"code": "LTYI", "name_zh": "洛天依"},
        "ESFJ": {"code": "ANON", "name_zh": "千早爱音"},
        "ESFP": {"code": "FRNA", "name_zh": "芙宁娜"},
    },
}


def load_profile_asset_manifest() -> dict[str, dict]:
    """从磁盘加载人格静态资源清单文件。

    Returns:
        包含 'sbti' 和 'acgti' 的资源配置字典。
    """
    manifest_path = (
        Path(__file__).resolve().parents[3]
        / "assets"
        / "profile_assets"
        / "manifest.json"
    )
    if not manifest_path.exists():
        logger.warning(f"人格资源清单不存在: {manifest_path}")
        return {"sbti": {}, "acgti": {}}

    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except Exception as e:
        logger.warning(f"加载人格资源清单失败: {e}")
        return {"sbti": {}, "acgti": {}}

    manifest: dict[str, dict] = {"sbti": {}, "acgti": {}}
    for item in raw.get("sbti", []):
        code = str(item.get("code", "")).strip()
        if code:
            manifest["sbti"][code] = item
    for item in raw.get("acgti", []):
        code = str(item.get("code", "")).strip()
        if code:
            manifest["acgti"][code] = item
    return manifest


def build_profile_image_from_manifest_pattern(
    manifest: dict[str, dict], profile_mode: str, asset_code: str
) -> str:
    """当 manifest 缺少具体 code 时，根据已有资源路径模式推导图片地址。

    Args:
        manifest: 人格资源清单字典。
        profile_mode: 当前人格模式（如 sbti / acgti）。
        asset_code: 资产代码。

    Returns:
        推导出的图片地址；如果无法推导则返回空字符串。
    """
    system_manifest = manifest.get(profile_mode, {})
    for item in system_manifest.values():
        if not isinstance(item, dict):
            continue
        sample_code = str(item.get("code", "")).strip()
        sample_file = str(item.get("file", "")).strip()
        if not sample_code or not sample_file:
            continue
        code_token = f"/{sample_code}."
        if code_token not in sample_file:
            continue
        return sample_file.replace(code_token, f"/{asset_code}.", 1)
    return ""


def get_manifest_profile_item_by_mbti(
    manifest: dict[str, dict], profile_mode: str, mbti: str
) -> dict | None:
    """按 MBTI 从 manifest 中寻找可用的人格资源项。

    Args:
        manifest: 人格资源清单字典。
        profile_mode: 当前人格模式。
        mbti: MBTI 编码字符串。

    Returns:
        匹配到的资源条目字典，未找到返回 None。
    """
    normalized_mbti = str(mbti or "").strip().upper()
    system_manifest = manifest.get(profile_mode, {})
    for item in system_manifest.values():
        if not isinstance(item, dict):
            continue
        item_mbti = str(item.get("mbti", "")).strip().upper()
        if item_mbti == normalized_mbti:
            return item
    return None


def resolve_profile_info(
    mbti: str,
    profile_mode: str,
    overrides: dict[str, dict],
    manifest: dict[str, dict],
    config_manager: Any,
) -> dict[str, str | float]:
    """根据当前展示模式解析人格标签的展示信息。

    Args:
        mbti: 用户 MBTI 类型（如 INTJ）。
        profile_mode: 当前展示模式（如 mbti, sbti, acgti）。
        overrides: 用户自定义的人格映射覆盖配置。
        manifest: 静态人格资源清单。
        config_manager: 配置管理器实例。

    Returns:
        包含展示文本、图片地址、透明度等渲染参数的字典。
    """
    normalized_mbti = str(mbti or "").strip().upper()

    # 1. 基础信息获取：从默认映射或用户覆盖中获取核心属性
    profile_defaults = DEFAULT_PROFILE_MAPPING.get(profile_mode, {})
    base_info = dict(profile_defaults.get(normalized_mbti, {}))

    # 用户覆盖优先级最高
    user_override = overrides.get(profile_mode, {}).get(normalized_mbti, {})
    if isinstance(user_override, dict):
        base_info.update(user_override)

    code = str(base_info.get("code", normalized_mbti)).strip() or normalized_mbti
    name_zh = str(base_info.get("name_zh", "")).strip()
    asset_code = str(base_info.get("asset_code", code)).strip() or code
    image = str(base_info.get("image", "")).strip()

    # 2. 图片与属性补全 (基于 manifest.json 可信源)
    if not image:
        system_manifest = manifest.get(profile_mode, {})
        # A. 优先按 asset_code 索引
        asset_item = system_manifest.get(asset_code)
        if isinstance(asset_item, dict):
            image = str(asset_item.get("file", "")).strip()
            if not name_zh:
                name_zh = str(asset_item.get("name", "")).strip()

        # B. 按照 asset_code 的资源规律推导图片地址
        if not image:
            image = build_profile_image_from_manifest_pattern(
                manifest, profile_mode, asset_code
            )

        # C. 对于 acgti 模式，尝试通过 MBTI 反查可用资源作为兜底
        if not image and profile_mode == "acgti":
            fallback_item = get_manifest_profile_item_by_mbti(
                manifest, profile_mode, normalized_mbti
            )
            if isinstance(fallback_item, dict):
                image = str(fallback_item.get("file", "")).strip()
                if not name_zh:
                    name_zh = str(fallback_item.get("name", "")).strip()
                if not code or code == normalized_mbti:
                    code = str(fallback_item.get("code", code)).strip()

    # 3. 构造显示文本 (Code + 中文名)
    display = str(base_info.get("display", "")).strip()
    if not display:
        display = f"{code}（{name_zh}）" if name_zh else code

    opacity = (
        config_manager.get_profile_image_opacity()
        if hasattr(config_manager, "get_profile_image_opacity")
        else 0.8
    )
    size_mode = (
        config_manager.get_profile_image_size_mode()
        if hasattr(config_manager, "get_profile_image_size_mode")
        else "contain"
    )

    return {
        "profile_mode": profile_mode,
        "profile_code": code,
        "profile_name_zh": name_zh,
        "profile_display": display,
        "profile_image": image,
        "profile_image_opacity": opacity,
        "profile_image_size_mode": size_mode,
    }
