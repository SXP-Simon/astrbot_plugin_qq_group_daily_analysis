import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.reporting.profile_mappings import (
    load_profile_asset_manifest,
    resolve_profile_info,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
LEGACY_MAPPING = json.loads(
    SCHEMA["basic"]["items"]["profile_mapping_config"]["default"]
)


@pytest.fixture
def config_manager():
    config = object.__new__(ConfigManager)
    config.config = {"t2i_rendering": {"t2i_rendering_strategies": [{"cdn_base_url": "https://fastly.jsdelivr.net/"}]}}
    return config


@pytest.mark.parametrize("mode", ["sbti", "acgti"])
@pytest.mark.parametrize("legacy_defaults", [False, True])
def test_builtin_profiles_follow_cdn_including_saved_defaults(
    config_manager, mode, legacy_defaults
):
    manifest = load_profile_asset_manifest()
    overrides = LEGACY_MAPPING if legacy_defaults else {}
    for mbti in LEGACY_MAPPING[mode]:
        profile = resolve_profile_info(mbti, mode, overrides, manifest, config_manager)
        assert profile["profile_image"].startswith(
            f"https://fastly.jsdelivr.net/gh/SXP-Simon/profile_assets@main/{mode}/"
        )
    config_manager.config["t2i_rendering"]["t2i_rendering_strategies"][0]["cdn_base_url"] = "https://other.example/"
    profile = resolve_profile_info("INTJ", mode, overrides, manifest, config_manager)
    assert profile["profile_image"].startswith("https://other.example/gh/")


@pytest.mark.parametrize("mode", ["sbti", "acgti"])
@pytest.mark.parametrize(
    "image",
    [
        "https://images.example/my-character.png?version=2#preview",
        "https://cdn.jsdmirror.com/gh/another/repo@main/custom.png",
        "https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/sbti/BOSS.png",
        "https://cdn.jsdmirror.com/gh/SXP-Simon/profile_assets@main/sbti/CTRL.png?v=1",
        "data:image/png;base64,custom",
    ],
)
def test_explicit_custom_profile_image_is_preserved(config_manager, mode, image):
    with patch.object(config_manager, "get_t2i_cdn_base_url") as cdn:
        profile = resolve_profile_info(
            "INTJ", mode, {mode: {"INTJ": {"image": image}}},
            load_profile_asset_manifest(), config_manager,
        )
    assert profile["profile_image"] == image
    cdn.assert_not_called()


def test_missing_manifest_code_pattern_uses_selected_cdn(config_manager):
    profile = resolve_profile_info(
        "INTJ", "sbti", {"sbti": {"INTJ": {"asset_code": "NEW"}}},
        load_profile_asset_manifest(), config_manager,
    )
    assert profile["profile_image"] == (
        "https://fastly.jsdelivr.net/gh/SXP-Simon/profile_assets@main/sbti/NEW.png"
    )


def test_non_repository_manifest_image_is_preserved(config_manager):
    image = "https://assets.example/CTRL.png"
    profile = resolve_profile_info(
        "INTJ", "sbti", {}, {"sbti": {"CTRL": {"file": image}}}, config_manager,
    )
    assert profile["profile_image"] == image


@pytest.mark.parametrize("name", ["image_template.html", "html_template.html"])
def test_miku_has_no_unusable_upload_references(name):
    source = (ROOT / "src/infrastructure/reporting/templates/HatsuneMiku" / name).read_text(
        encoding="utf-8"
    )
    assert "uploaded:" not in source
    assert "deco-image" not in source
