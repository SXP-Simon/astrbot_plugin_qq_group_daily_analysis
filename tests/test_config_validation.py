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
