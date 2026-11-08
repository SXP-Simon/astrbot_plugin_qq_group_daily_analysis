from pathlib import Path

from src.domain.entities.incremental_state import IncrementalBatch


def test_webui_incremental_fixture_uses_domain_serialization():
    import json
    path = Path(__file__).parents[1] / "dashboard/src/pages/plugin-data/model/__tests__/fixtures/incrementalBatch.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert IncrementalBatch.from_dict(payload).to_dict() == payload
    assert set(payload["topics"][0]) == {"topic", "detail", "contributors", "contributor_ids"}
    assert set(payload["golden_quotes"][0]) == {"content", "sender", "reason", "user_id"}
