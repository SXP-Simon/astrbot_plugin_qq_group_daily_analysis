"""端到端集成测试：使用轻量级 Satori Mock 服务（WebSocket + HTTP REST API）全流程验证。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import aiohttp
import pytest
from aiohttp import web
from src.application.services.message_processing_service import MessageProcessingService
from src.infrastructure.persistence.platform_group_registry import PlatformGroupRegistry
from src.infrastructure.platform.adapters.satori_adapter import SatoriAdapter
from src.infrastructure.platform.factory import PlatformAdapterFactory


class MockSatoriServer:
    """轻量级内存 Satori v1 协议服务端（实现 WebSocket 与 HTTP REST API）。"""

    def __init__(self) -> None:
        self.app = web.Application()
        self.app.router.add_get("/satori/v1/events", self._handle_ws_events)
        self.app.router.add_post("/satori/v1/message.create", self._handle_message_create)
        self.app.router.add_post("/satori/v1/guild.get", self._handle_guild_get)
        self.app.router.add_post("/satori/v1/guild.member.list", self._handle_member_list)
        self.app.router.add_post("/satori/v1/user.get", self._handle_user_get)

        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None
        self.active_ws: list[web.WebSocketResponse] = []
        self.received_messages: list[dict[str, Any]] = []
        self.port: int = 0

    async def start(self) -> str:
        """在本地可用端口启动 Mock 服务端。"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        # 获取实际分配的动态端口
        server = self.site._server
        assert server is not None
        sockets = getattr(server, "sockets", None)
        assert sockets
        self.port = sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{self.port}/satori/v1"

    async def stop(self) -> None:
        """停止服务并清理所有连接。"""
        for ws in list(self.active_ws):
            if not ws.closed:
                await ws.close()
        if self.runner:
            await self.runner.cleanup()

    async def _handle_ws_events(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.active_ws.append(ws)

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    op = data.get("op")
                    if op == 3:  # IDENTIFY 鉴权/登录
                        ready_payload = {
                            "op": 4,  # READY 就绪响应
                            "body": {
                                "logins": [
                                    {
                                        "platform": "satori",
                                        "user": {
                                            "id": "bot_self_999",
                                            "name": "SatoriTestBot",
                                            "avatar": "https://mock.satori/bot.png",
                                        },
                                        "status": 1,
                                        "features": ["guild.get", "guild.member.list", "message.create"],
                                    }
                                ],
                                "sn": 1,
                            },
                        }
                        await ws.send_str(json.dumps(ready_payload))
                    elif op == 1:  # PING 心跳
                        pong_payload = {"op": 2, "body": {}}
                        await ws.send_str(json.dumps(pong_payload))
        finally:
            if ws in self.active_ws:
                self.active_ws.remove(ws)

        return ws

    async def _handle_message_create(self, request: web.Request) -> web.Response:
        data = await request.json()
        self.received_messages.append(data)
        return web.json_response([{"id": f"msg_ack_{len(self.received_messages)}", "content": data.get("content")}])

    async def _handle_guild_get(self, request: web.Request) -> web.Response:
        data = await request.json()
        guild_id = data.get("guild_id", "guild_default")
        return web.json_response(
            {
                "id": guild_id,
                "name": f"Guild {guild_id} Name",
                "avatar": "https://mock.cdn/guild_avatar.png",
                "member_count": 128,
            }
        )

    async def _handle_member_list(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": [
                    {
                        "user": {"id": "user_alice", "name": "Alice", "avatar": "https://mock.cdn/alice.png"},
                        "nick": "Alice in Guild",
                    },
                    {
                        "user": {"id": "user_bob", "name": "Bob"},
                        "nick": "Bob the Builder",
                    },
                ],
                "next": None,
            }
        )

    async def _handle_user_get(self, request: web.Request) -> web.Response:
        data = await request.json()
        user_id = data.get("user_id", "user_unknown")
        return web.json_response(
            {
                "id": user_id,
                "name": f"User {user_id}",
                "avatar": f"https://mock.cdn/{user_id}.png",
            }
        )

    async def broadcast_event(self, event_type: str, body: dict[str, Any]) -> None:
        """向所有活跃的 WebSocket 客户端广播 Satori 事件。"""
        payload = {
            "op": 0,  # EVENT 事件
            "body": {
                "type": event_type,
                **body,
            },
        }
        raw = json.dumps(payload)
        for ws in list(self.active_ws):
            if not ws.closed:
                await ws.send_str(raw)


class SatoriTestClient:
    """实现 SatoriClientProtocol 并与 MockSatoriServer 通信的客户端。"""

    def __init__(self, api_base_url: str, token: str = "") -> None:
        self.api_base_url = api_base_url
        self.token = token
        self.session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self.session:
            await self.session.close()

    async def send_http_request(
        self,
        method: str,
        path: str,
        data: dict | None = None,
        platform: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        if not self.session:
            raise RuntimeError("Client session not started")

        url = f"{self.api_base_url.rstrip('/')}{path}"
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with self.session.request(method, url, json=data, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            return {}


class InMemoryHistoryManager:
    """模拟 AstrBot 的 message_history_manager 内存存储。"""

    def __init__(self) -> None:
        self.records: list[SimpleNamespace] = []

    async def insert(
        self,
        platform_id: str,
        user_id: str,
        content: dict,
        sender_id: str,
        sender_name: str,
        max_messages: int = 10000,
    ) -> None:
        rec_id = len(self.records) + 1
        rec = SimpleNamespace(
            id=rec_id,
            platform_id=platform_id,
            user_id=user_id,
            sender_id=sender_id,
            sender_name=sender_name,
            created_at=datetime.now(timezone.utc),
            content=content,
        )
        self.records.append(rec)

    async def get(
        self,
        platform_id: str,
        user_id: str,
        page: int = 1,
        page_size: int = 500,
    ) -> list[SimpleNamespace]:
        matched = [r for r in self.records if r.platform_id == platform_id and str(r.user_id) == str(user_id)]
        start = (page - 1) * page_size
        return matched[start : start + page_size]


class FakeSatoriMessageEvent:
    """模拟从 Satori 适配器接收到的 AstrMessageEvent 事件对象。"""

    def __init__(
        self,
        platform_id: str,
        group_id: str,
        sender_id: str,
        sender_name: str,
        message_id: str,
        plain_text: str,
    ) -> None:
        self._platform_id = platform_id
        self._group_id = group_id
        self._sender_id = sender_id
        self._sender_name = sender_name
        self.message_str = plain_text
        self.message_obj = SimpleNamespace(
            message_id=message_id,
            timestamp=int(datetime.now(timezone.utc).timestamp()),
            message=[SimpleNamespace(type="plain", text=plain_text)],
            sender=SimpleNamespace(user_id=sender_id, nickname=sender_name),
            raw_message={"message_id": message_id},
        )
        self.platform_meta = SimpleNamespace(id=platform_id, name="satori")

    def get_platform_id(self) -> str:
        return self._platform_id

    def get_platform_name(self) -> str:
        return "satori"

    def get_group_id(self) -> str:
        return self._group_id

    def get_sender_id(self) -> str:
        return self._sender_id

    def get_sender_name(self) -> str:
        return self._sender_name


class FakePlugin:
    """模拟插件实例，为 PlatformGroupRegistry 提供 KV 存储接口。"""

    def __init__(self) -> None:
        self._kv: dict[str, Any] = {}

    async def get_kv_data(self, key: str, default: Any = None) -> Any:
        return self._kv.get(key, default)

    async def put_kv_data(self, key: str, value: Any) -> None:
        self._kv[key] = value


@pytest.mark.asyncio
async def test_satori_mock_server_full_flow(tmp_path: Path):
    """测试完整 Satori 生命周期：Mock 服务端 -> 事件接收 -> 历史落库 -> 适配器查询与分析报告发送。"""
    server = MockSatoriServer()
    base_url = await server.start()
    ws_endpoint = f"ws://127.0.0.1:{server.port}/satori/v1/events"

    # 1. 启动连接到 Mock 服务端的 HTTP/WS 客户端
    satori_client = SatoriTestClient(api_base_url=base_url, token="secret_token_123")
    await satori_client.start()

    # 验证与 Mock 服务端的 WebSocket 握手协议流程
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_endpoint) as ws:
            # 发送 IDENTIFY
            await ws.send_str(json.dumps({"op": 3, "body": {"token": "secret_token_123"}}))
            ready_msg = await ws.receive_str()
            ready_data = json.loads(ready_msg)
            assert ready_data["op"] == 4
            assert ready_data["body"]["logins"][0]["user"]["id"] == "bot_self_999"

    # 2. 初始化群聊日常分析插件的上下文与服务
    history_mgr = InMemoryHistoryManager()
    context = SimpleNamespace(
        message_history_manager=history_mgr,
    )
    fake_plugin = FakePlugin()
    group_registry = PlatformGroupRegistry(plugin_instance=fake_plugin)  # type: ignore[arg-type]
    msg_processing_service = MessageProcessingService(context, group_registry)  # type: ignore[arg-type]

    # 3. 模拟来自 Satori 平台的群消息事件到达
    event = FakeSatoriMessageEvent(
        platform_id="satori_platform_test",
        group_id="guild_888",
        sender_id="user_101",
        sender_name="Chuck",
        message_id="satori_msg_1",
        plain_text="Hello everyone in Satori guild!",
    )

    # 4. 消息处理与历史记录落库
    stored = await msg_processing_service.process_message(event)  # type: ignore[arg-type]
    assert stored is True
    assert len(history_mgr.records) == 1

    # 验证群组已成功登记在群组注册表
    seen_groups = await group_registry.get_all_group_ids("satori_platform_test")
    assert "guild_888" in seen_groups

    # 5. 创建插件的 SatoriAdapter 实例并验证各项数据查询操作
    satori_adapter = PlatformAdapterFactory.create(
        "satori",
        satori_client,
        {
            "platform_id": "satori_platform_test",
            "bot_self_ids": ["bot_self_999"],
            "plugin_instance": SimpleNamespace(platform_group_registry=group_registry),
        },
    )
    assert isinstance(satori_adapter, SatoriAdapter)
    satori_adapter.set_context(context)  # type: ignore[arg-type]

    # 读取历史消息
    messages = await satori_adapter.fetch_messages("guild_888", days=1)
    assert len(messages) == 1
    assert messages[0].sender_name == "Chuck"
    assert messages[0].text_content == "Hello everyone in Satori guild!"

    # 通过 Satori HTTP API 向服务端查询群信息与成员列表
    guild_info = await satori_adapter.get_group_info("guild_888")
    assert guild_info is not None
    assert guild_info.group_name == "Guild guild_888 Name"
    assert guild_info.member_count == 128

    members = await satori_adapter.get_group_members("guild_888")
    assert len(members) == 2
    assert members[0].user_id == "user_alice"
    assert members[0].nickname == "Alice in Guild"

    # 查询用户头像 URL
    avatar_url = await satori_adapter.get_user_avatar_url("user_alice")
    assert avatar_url == "https://mock.cdn/alice.png"

    # 6. 通过 SatoriAdapter 发送生成的每日分析报告图片
    report_image = tmp_path / "daily_analysis_report.png"
    report_image.write_bytes(b"\x89PNG\r\n\x1a\nMockReportImageBytes")
    send_res = await satori_adapter.send_image_message(
        group_id="guild_888",
        image_url=str(report_image),
        text="📊 今日群聊总结已生成！",
    )
    assert send_res is True

    # 验证 Mock 服务端已准确接收到带有 <img /> XML 标签与文本的内容
    assert len(server.received_messages) == 1
    received = server.received_messages[0]
    assert received["channel_id"] == "guild_888"
    assert '<img src="data:image/png;base64,' in received["content"]
    assert "今日群聊总结已生成！" in received["content"]

    # 7. 清理资源
    await satori_client.close()
    await server.stop()

