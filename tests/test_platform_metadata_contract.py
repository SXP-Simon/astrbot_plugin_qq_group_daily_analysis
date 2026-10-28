"""WebUI 平台选项契约与实际后端返回的字段一致。"""

from src.infrastructure.webui.openapi_spec import generate_openapi_spec
from src.infrastructure.webui.routes.trace_routes import PlatformMetadataDTO


def test_platform_openapi_matches_route_dto():
    schema = generate_openapi_spec()["components"]["schemas"]["ConnectedPlatform"]
    assert set(schema["required"]) == PlatformMetadataDTO.__required_keys__
    assert set(schema["properties"]) == PlatformMetadataDTO.__required_keys__
