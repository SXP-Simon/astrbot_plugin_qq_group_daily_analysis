"""漫画参考图规范化只应修改所属配置节点。"""

from src.infrastructure.webui.routes.config_routes import _normalize_comic_references_for_save


def test_reference_normalization_preserves_unrelated_dynamic_config(tmp_path):
    unrelated = ["data:image/png;base64,invalid", {"reference_images": [" untouched "]}]
    nested = {"reference_images": [" nested "]}
    character = {
        "name": "角色",
        "reference_images": [" https://example.com/ref.png ", "", None],
        "extension": nested,
    }
    config = {
        "extension": unrelated,
        "daily_comic": {"comic_characters": [character, "保留旧节点"]},
    }
    _normalize_comic_references_for_save(config, tmp_path)
    assert character["__template_key"] == "character"
    assert character["reference_images"] == ["https://example.com/ref.png", None]
    assert config["extension"] == unrelated
    assert character["extension"] == nested
    assert config["daily_comic"]["comic_characters"][1] == "保留旧节点"


def test_reference_normalization_preserves_explicit_template_and_non_list_value(tmp_path):
    character = {"__template_key": "custom", "reference_images": "legacy-path"}
    config = {"daily_comic": {"comic_characters": [character]}}
    _normalize_comic_references_for_save(config, tmp_path)
    assert character == {"__template_key": "custom", "reference_images": "legacy-path"}
