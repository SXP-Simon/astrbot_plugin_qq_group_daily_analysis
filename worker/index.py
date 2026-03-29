"""
Cloudflare Python Worker: 存储结构化日报 JSON，并按模板渲染网页。
"""

from __future__ import annotations

import json
import re
import secrets
from urllib.parse import parse_qs, urlparse

from js import Object
from pyodide.ffi import to_js as _to_js
from workers import Response, WorkerEntrypoint

from src.shared.web_report_renderer import normalize_template_name, render_report_html

from worker.template_loader import AssetTemplateLoader

_REPORT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{10,64}$")
_DEFAULT_TEMPLATE = "scrapbook"


def to_js(obj):
    return _to_js(obj, dict_converter=Object.fromEntries)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        parsed_url = urlparse(request.url)
        path = parsed_url.path or "/"

        if path == "/healthz":
            return Response("ok", headers={"content-type": "text/plain; charset=utf-8"})

        if path == "/api/internal/reports" and request.method.upper() == "POST":
            return await self._handle_report_upload(request)

        if path.startswith("/r/") and request.method.upper() == "GET":
            report_id = path.removeprefix("/r/").strip("/")
            return await self._handle_report_view(request, report_id)

        return Response("not found", status=404)

    async def _handle_report_upload(self, request):
        if not self._is_authorized(request):
            return self._json_response(
                {"ok": False, "error": "unauthorized"}, status=401
            )

        try:
            body = json.loads(await request.text())
        except json.JSONDecodeError:
            return self._json_response(
                {"ok": False, "error": "invalid_json"}, status=400
            )

        report = body.get("report")
        if not isinstance(report, dict):
            return self._json_response(
                {"ok": False, "error": "missing_report"}, status=400
            )

        ttl_seconds = max(60, int(body.get("ttl_seconds", 7 * 86400) or 7 * 86400))
        report_id = secrets.token_urlsafe(16)

        stored_report = dict(report)
        stored_report["report_id"] = report_id

        await self.env.REPORTS.put(
            f"report:{report_id}",
            json.dumps(stored_report, ensure_ascii=False),
            to_js({"expirationTtl": ttl_seconds}),
        )

        return self._json_response(
            {
                "ok": True,
                "report_id": report_id,
                "url": f"{self._origin_for(request)}/r/{report_id}",
            }
        )

    async def _handle_report_view(self, request, report_id: str):
        if not _REPORT_ID_PATTERN.fullmatch(report_id or ""):
            return Response("not found", status=404)

        stored = await self.env.REPORTS.get(f"report:{report_id}")
        if not stored:
            return Response("not found", status=404)

        try:
            report_payload = json.loads(str(stored))
        except json.JSONDecodeError:
            return Response("invalid report payload", status=500)

        template_loader = AssetTemplateLoader(self.env.ASSETS)
        template_name = await self._resolve_template_name(
            request, report_payload, template_loader
        )

        try:
            env = await template_loader.get_environment(template_name)
            rendered_html = render_report_html(env, report_payload)
        except Exception as exc:
            if template_name != _DEFAULT_TEMPLATE:
                try:
                    env = await template_loader.get_environment(_DEFAULT_TEMPLATE)
                    rendered_html = render_report_html(env, report_payload)
                except Exception as fallback_exc:
                    return Response(f"render error: {fallback_exc}", status=500)
            else:
                return Response(f"render error: {exc}", status=500)

        headers = {
            "content-type": "text/html; charset=utf-8",
            "cache-control": "no-store",
            "x-robots-tag": "noindex, nofollow, noarchive",
            "referrer-policy": "no-referrer",
            "x-content-type-options": "nosniff",
        }
        return Response(rendered_html, headers=headers)

    async def _resolve_template_name(
        self, request, report_payload: dict, template_loader
    ):
        query = parse_qs(urlparse(request.url).query or "")
        requested = normalize_template_name(
            (query.get("t") or query.get("template") or [None])[0]
        )
        payload_default = normalize_template_name(report_payload.get("template"))

        if requested and await template_loader.has_template(requested):
            return requested
        if payload_default and await template_loader.has_template(payload_default):
            return payload_default
        return _DEFAULT_TEMPLATE

    def _is_authorized(self, request) -> bool:
        expected = str(self.env.UPLOAD_TOKEN or "").strip()
        if not expected:
            return False
        authorization = request.headers.get("Authorization", "")
        return authorization == f"Bearer {expected}"

    @staticmethod
    def _origin_for(request) -> str:
        parsed = urlparse(request.url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _json_response(payload: dict, status: int = 200) -> Response:
        return Response(
            json.dumps(payload, ensure_ascii=False),
            status=status,
            headers={"content-type": "application/json; charset=utf-8"},
        )
