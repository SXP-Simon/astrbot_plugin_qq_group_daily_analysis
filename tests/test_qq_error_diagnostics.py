"""不同 SDK 异常契约、敏感信息脱敏和损坏对象的防腐回归。"""

import json
import logging
from types import SimpleNamespace
from urllib.parse import quote

import aiohttp
import pytest

from src.infrastructure.platform.template_preview.qq_error_diagnostics import (
    describe_preview_error,
)


class LegacyError(RuntimeError):
    def __init__(self, message):
        self.msgs = message

    def __str__(self):
        return self.msgs


def test_installed_botpy_error_keeps_reason_without_inventing_http_status():
    from botpy.errors import ServerError

    result = describe_preview_error(
        ServerError(msg="markdown image resource transfer failed")
    )
    assert "ServerError: QQ 接口返回错误" in result
    assert "markdown image resource transfer failed" in result
    assert "500" not in result and "http_status=" not in result


@pytest.mark.parametrize(
    "value",
    [
        "image transfer failed",
        b"image transfer failed",
        {
            "code": 304083,
            "message": "image transfer failed",
            "headers": {"Authorization": "secret-header"},
        },
        ["image transfer failed"],
    ],
)
def test_legacy_msgs_variants_and_invalid_str_are_supported(value):
    result = describe_preview_error(LegacyError(value))
    assert "image transfer failed" in result
    assert "secret-header" not in result
    if isinstance(value, dict):
        assert "code=304083" in result


def test_newer_message_and_numeric_fields_take_precedence_over_generic_args():
    error = RuntimeError("generic SDK error")
    error.message = "markdown image check failed"
    error.status_code = 400
    error.code = "304083"
    result = describe_preview_error(error)
    assert "markdown image check failed" in result
    assert "generic SDK error" not in result
    assert "http_status=400" in result and "code=304083" in result


@pytest.mark.parametrize(
    "value",
    [
        {"status": "400", "errcode": 304083, "message": "image transfer failed"},
        json.dumps(
            {
                "code": 304083,
                "message": "image transfer failed",
                "data": {"token": "hidden-data"},
            }
        ),
        {
            "error": {
                "code": 304083,
                "msg": "image transfer failed",
                "request": "hidden-request",
            }
        },
    ],
)
def test_structured_args_only_keep_message_and_actual_numeric_code(value):
    result = describe_preview_error(Exception(value))
    assert "image transfer failed" in result and "code=304083" in result
    assert "hidden-data" not in result and "hidden-request" not in result


def test_broken_optional_properties_and_str_do_not_hide_original_reason():
    class BrokenError(Exception):
        def __getattribute__(self, name):
            if name in {"msgs", "message", "status", "status_code", "code", "errcode"}:
                raise RuntimeError("property getter failed")
            return super().__getattribute__(name)

        def __str__(self):
            raise TypeError("invalid SDK stringification")

    result = describe_preview_error(
        BrokenError({"message": "actual error", "code": 304083})
    )
    assert "actual error" in result and "code=304083" in result


def test_response_and_request_objects_are_never_accessed():
    class ResponseError(Exception):
        @property
        def response(self):
            pytest.fail("不能读取 SDK response 对象")

        @property
        def request(self):
            pytest.fail("不能读取 SDK request 对象")

    assert "image check failed" in describe_preview_error(
        ResponseError("image check failed")
    )


@pytest.mark.parametrize(
    "secret",
    [
        "Authorization: Bearer secret-value",
        "Proxy-Authorization: QQBot secret-value",
        "Bearer secret-value",
        "QQBot secret-value",
        'token="secret-value"',
        "access_token=secret-value",
        "accessToken: secret-value",
        "refresh_token='secret-value'",
        "client_secret=secret-value",
        "appSecret: secret-value",
        "API-Key=secret-value",
        "password='secret-value with spaces'",
        "Cookie: session=secret-value; other=second-cookie-value",
        "Set-Cookie: session=secret-value; Path=/",
        "file_info=secret-value",
        r"api_key=\"secret-value\"",
        "Authorization: Bearer first-part\r\n secret-value",
        quote("access_token=secret-value"),
        quote(quote("access_token=secret-value")),
        "authorization&#58; Bearer secret-value",
    ],
)
def test_sensitive_authentication_values_are_removed(secret):
    result = describe_preview_error(RuntimeError("image transfer failed; " + secret))
    assert "image transfer failed" in result
    assert "secret-value" not in result and "second-cookie-value" not in result


@pytest.mark.parametrize(
    "url",
    [
        "https://user:pass@cdn.example.test/private-file?token=private-query#private-fragment",
        "http://cdn.example.test/private-file",
        "file:///home/private-user/private-file",
        r"https:\/\/cdn.example.test/private-file?token=private-query",
        quote("https://user:pass@cdn.example.test/private-file?token=private-query"),
    ],
)
def test_resource_addresses_are_hidden_without_losing_error_reason(url):
    result = describe_preview_error(RuntimeError("image transfer failed at " + url))
    assert "image transfer failed" in result
    assert "private-file" not in result and "user:pass" not in result
    assert "private-query" not in result and "private-fragment" not in result


def test_summary_is_single_line_bounded_and_redacted_before_truncation():
    raw = "image check failed\r\n" + "x" * 300 + " token=" + "secret-value" * 80
    result = describe_preview_error(LegacyError(raw + "\x1b\u202e"))
    assert len(result) <= 512
    assert "secret-value" not in result
    assert all(char not in result for char in ["\n", "\r", "\x1b", "\u202e"])


def test_aiohttp_error_preserves_real_http_status_but_not_request_headers():
    error = aiohttp.ClientResponseError(
        request_info=SimpleNamespace(real_url="https://example.test/private-url"),
        history=(),
        status=400,
        message="image check failed",
        headers={"Authorization": "private-header"},
    )
    result = describe_preview_error(error)
    assert "HTTP 400" in result and "image check failed" in result
    assert "private-header" not in result and "private-url" not in result


@pytest.mark.parametrize(
    "value", [True, "secret-code", -1, 999999999999999999999999999]
)
def test_invalid_http_status_is_not_reported(value):
    error = RuntimeError("image check failed")
    error.status = value
    assert "http_status=" not in describe_preview_error(error)


def test_cycles_missing_values_and_unknown_types_safely_fall_back():
    payload = {}
    payload["error"] = payload
    assert len(describe_preview_error(LegacyError(payload))) <= 512
    assert describe_preview_error(LegacyError(None)).startswith("LegacyError:")
    assert describe_preview_error(Exception()).startswith("Exception:")
    assert "private-path" not in describe_preview_error(
        FileNotFoundError("/private-path")
    )


def test_sdk_logging_configuration_is_unchanged():
    sdk_logger = logging.getLogger("botpy")
    state = (sdk_logger.level, sdk_logger.propagate, list(sdk_logger.handlers))
    describe_preview_error(LegacyError("image transfer failed"))
    assert (sdk_logger.level, sdk_logger.propagate, list(sdk_logger.handlers)) == state
