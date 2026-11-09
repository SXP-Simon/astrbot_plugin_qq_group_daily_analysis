import copy
import json
from pathlib import Path

import pytest

from src.infrastructure.config.config_validation import validate_config_for_save

CASES = json.loads(
    (Path(__file__).parent / "fixtures/config_validation_cases.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_shared_frontend_backend_validation_cases(case):
    config = copy.deepcopy(case["config"])
    before = copy.deepcopy(config)
    if case["valid"]:
        validate_config_for_save(config)
    else:
        with pytest.raises(ValueError, match=r"（.+）"):
            validate_config_for_save(config)
    assert config == before


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_nonfinite_numbers_are_rejected(value):
    with pytest.raises(ValueError):
        validate_config_for_save({"basic": {"profile_image_opacity": value}})


@pytest.mark.parametrize(
    ("list_key", "prompt_key"),
    [("comic_styles", "prompt_override"), ("comic_characters", "storyboard_prompt")],
)
def test_only_preserves_existing_formatted_storyboards(list_key, prompt_key):
    legacy = {prompt_key: "{chat_content} 共 {topic_count:02d} 格。", "name": "旧正文"}
    ordinary = {prompt_key: "{chat_content} 共 {topic_count} 格。", "name": "普通正文"}
    previous = {"daily_comic": {list_key: [legacy, ordinary]}}
    reordered = {"daily_comic": {list_key: [ordinary, legacy]}, "basic": {"analysis_days": 2}}
    validate_config_for_save(reordered, previous)
    for changed in (
        {**legacy, "name": "编辑后", prompt_key: "{chat_content} 共 {topic_count:03d} 格。"},
        {**legacy, "name": "新副本"},
    ):
        with pytest.raises(ValueError, match="不带格式修饰"):
            validate_config_for_save({"daily_comic": {list_key: [legacy, changed]}}, previous)
