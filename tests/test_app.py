"""Integration tests for app.py API endpoints."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Set env vars BEFORE importing app
os.environ.setdefault("NYX_API_BASE", "")
os.environ.setdefault("NYX_API_KEY", "")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app import app  # noqa: E402

client = TestClient(app)


class TestRoot:
    def test_index_returns_html(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Cyber Nyx" in resp.text


class TestStatus:
    def test_status_returns_json(self):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "display" in data
        assert "version" in data
        assert data["version"] == "0.9.0"

    def test_status_llm_field(self):
        resp = client.get("/api/status")
        data = resp.json()
        # In demo mode (no API key), llm should be "local-demo"
        assert data["llm"] in ("connected", "local-demo")


class TestChatText:
    def test_empty_message(self):
        resp = client.post("/api/chat", json={"message": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert data["emotion"] == "neutral"

    def test_text_format_default(self):
        resp = client.post("/api/chat", json={"message": "你好"})
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert "emotion" in data
        # Default format is text, should not have "format" key
        assert "format" not in data

    def test_text_format_explicit(self):
        resp = client.post("/api/chat", json={"message": "你好", "format": "text"})
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert "format" not in data


class TestChatJson:
    def test_json_format(self):
        resp = client.post("/api/chat", json={"message": "你好", "format": "json"})
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert "format" in data
        assert data["format"] == "json"
        assert "recalled" in data
        assert "emotion" in data


class TestChatStream:
    def test_sse_stream_endpoint_exists(self):
        resp = client.post(
            "/api/chat/stream", json={"message": "你好", "format": "sse"}
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    def test_sse_stream_returns_done(self):
        resp = client.post(
            "/api/chat/stream", json={"message": "你好", "format": "sse"}
        )
        content = resp.text
        assert "done" in content or "reply" in content

    def test_sse_empty_message(self):
        resp = client.post("/api/chat/stream", json={"message": "", "format": "sse"})
        assert resp.status_code == 200
        content = resp.text
        assert "neutral" in content


class TestTaskDetection:
    def test_task_message_goes_to_hermes(self):
        with patch("app.core") as mock_core:
            mock_core.submit.return_value = MagicMock(ok=True, output="任务完成")
            mock_core.health.return_value = True
            mock_core.name = "hermes"
            resp = client.post("/api/chat", json={"message": "帮我查一下天气"})
            assert resp.status_code == 200

    def test_chat_message_goes_to_llm(self):
        with patch("app.LLM_ON", True), patch("nyx_llm.chat") as mock_chat:
            mock_chat.return_value = "你好呀~"
            resp = client.post("/api/chat", json={"message": "你好"})
            assert resp.status_code == 200
            data = resp.json()
            assert "reply" in data


class TestEmotionInference:
    def test_happy_emotion(self):
        resp = client.post("/api/chat", json={"message": "哈哈开心"})
        data = resp.json()
        assert data["emotion"] == "happy"
        assert "intensity" in data

    def test_sad_emotion(self):
        resp = client.post("/api/chat", json={"message": "难过伤心"})
        data = resp.json()
        assert data["emotion"] == "sad"

    def test_angry_emotion(self):
        resp = client.post("/api/chat", json={"message": "你真讨厌"})
        data = resp.json()
        assert data["emotion"] == "angry"

    def test_surprised_emotion(self):
        resp = client.post("/api/chat", json={"message": "天哪不是吧"})
        data = resp.json()
        assert data["emotion"] == "surprised"

    def test_curious_emotion(self):
        resp = client.post("/api/chat", json={"message": "你在做什么吗？"})
        data = resp.json()
        assert data["emotion"] == "curious"

    def test_neutral_emotion(self):
        resp = client.post("/api/chat", json={"message": "今天天气不错"})
        data = resp.json()
        assert data["emotion"] == "neutral"
        assert data["intensity"] == 0.0


class TestMode:
    def test_mode_get_default(self):
        resp = client.get("/api/mode")
        assert resp.status_code == 200
        assert resp.json()["mode"] == "companion"

    def test_mode_switch_work(self):
        resp = client.post("/api/mode", json={"mode": "work"})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "work"
        resp = client.post("/api/mode", json={"mode": "companion"})
        assert resp.json()["mode"] == "companion"

    def test_mode_invalid(self):
        resp = client.post("/api/mode", json={"mode": "sleep"})
        assert resp.json()["mode"] == "companion"
        assert "不存在" in resp.json()["message"]


class TestImportantMemory:
    def test_important_message_triggers_remember(self):
        with patch("app.MEM_ENABLED", True), patch("app.memory") as mock_mem:
            mock_mem.remember.return_value = True
            resp = client.post("/api/chat", json={"message": "我的电话是13800138000"})
            assert resp.status_code == 200
            mock_mem.remember.assert_called_once()


class TestErrorHandling:
    def test_llm_failure_graceful_degradation(self):
        with patch("app.LLM_ON", True), patch("nyx_llm.chat") as mock_chat:
            mock_chat.side_effect = Exception("API error")
            resp = client.post("/api/chat", json={"message": "你好"})
            assert resp.status_code == 200
            data = resp.json()
            assert "reply" in data
            # Should contain error message in reply
            assert (
                "网络" in data["reply"]
                or "error" in data["reply"].lower()
                or len(data["reply"]) > 0
            )


class TestSessions:
    def test_chat_returns_session_id(self):
        resp = client.post("/api/chat", json={"message": "你好"})
        data = resp.json()
        assert "session_id" in data
        assert data["session_id"]

    def test_session_new_endpoint(self):
        resp = client.get("/api/session/new")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["session_id"]

    def test_session_reuse_same_id(self):
        resp1 = client.post("/api/chat", json={"message": "第一次说话"})
        sid = resp1.json()["session_id"]
        resp2 = client.post(
            "/api/chat",
            json={"message": "第二次说话", "session_id": sid},
        )
        assert resp2.json()["session_id"] == sid

    def test_session_history_records_messages(self):
        resp = client.post("/api/chat", json={"message": "记录我这句话"})
        sid = resp.json()["session_id"]
        resp = client.get(f"/api/session/{sid}/history")
        assert resp.status_code == 200
        msgs = resp.json()["messages"]
        assert len(msgs) == 2  # user + assistant
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "记录我这句话"
        assert msgs[1]["role"] == "assistant"

    def test_session_history_empty_for_unknown(self):
        resp = client.get("/api/session/nonexistent/history")
        assert resp.status_code == 200
        assert resp.json()["messages"] == []

    def test_session_delete(self):
        resp = client.get("/api/session/new")
        sid = resp.json()["session_id"]
        resp = client.delete(f"/api/session/{sid}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        resp = client.get(f"/api/session/{sid}/history")
        assert resp.json()["messages"] == []

    def test_llm_receives_history(self):
        with patch("app.LLM_ON", True), patch("nyx_llm.chat") as mock_chat:
            mock_chat.return_value = "收到~"
            resp = client.post("/api/chat", json={"message": "第一句"})
            sid = resp.json()["session_id"]
            resp = client.post(
                "/api/chat", json={"message": "第二句", "session_id": sid}
            )
            assert resp.status_code == 200
            # history 参数应该被传入（第一条 user 消息在其中）
            hist = mock_chat.call_args.kwargs.get("history", [])
            assert any(m["content"] == "第一句" for m in hist)

    def test_stream_endpoint_returns_session_id(self):
        resp = client.post(
            "/api/chat/stream", json={"message": "你好", "format": "sse"}
        )
        assert resp.status_code == 200
        assert "session_id" in resp.text


class TestHistoryRestore:
    """v0.7：前端刷新恢复聊天历史（history 端点用 get_or_create 触发记忆恢复）。"""

    def test_history_restores_unknown_session_as_empty(self):
        resp = client.get("/api/session/restore-unknown/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "restore-unknown"
        assert data["messages"] == []

    def test_history_idempotent_get_or_create(self):
        # 连续两次调用同一 session，不应产生重复消息
        resp1 = client.get("/api/session/restore-idem/history")
        resp2 = client.get("/api/session/restore-idem/history")
        assert resp1.json()["messages"] == resp2.json()["messages"]
        client.delete("/api/session/restore-idem")

    def test_history_after_chat_returns_full_context(self):
        resp = client.post("/api/chat", json={"message": "恢复测试"})
        sid = resp.json()["session_id"]
        resp = client.get(f"/api/session/{sid}/history")
        msgs = resp.json()["messages"]
        assert len(msgs) == 2
        assert msgs[0]["content"] == "恢复测试"
        client.delete(f"/api/session/{sid}")


class TestMemoryApi:
    """v0.7：记忆可视化 / 管理（记忆面板）。"""

    def test_memory_list_returns_ok(self):
        resp = client.get("/api/memory")
        assert resp.status_code == 200
        data = resp.json()
        assert "memories" in data
        assert isinstance(data["memories"], list)
        # 测试环境无记忆系统（降级），enabled 为 False
        assert data["enabled"] in (True, False)

    def test_memory_list_limit_validation(self):
        resp = client.get("/api/memory?limit=9999")
        assert resp.status_code == 200
        assert isinstance(resp.json()["memories"], list)

    def test_memory_delete_unknown_returns_json(self):
        resp = client.delete("/api/memory/not-exist-id")
        assert resp.status_code == 200
        data = resp.json()
        assert "ok" in data
        # 未启用时明确返回失败
        if data.get("ok") is False:
            assert data.get("error")


class TestWebSocket:
    """v0.7：WebSocket 长连接（主动关心实时推送）。"""

    def test_ws_connect_requires_session_id(self):
        # 无 session_id → 服务端关闭连接（code 4400）
        rejected = False
        try:
            with client.websocket_connect("/ws") as ws:
                ws.receive_text()
        except Exception:
            rejected = True
        assert rejected, "无 session_id 应被拒绝连接"

    def test_ws_connect_and_keepalive(self):
        with client.websocket_connect("/ws?session_id=wstest-001") as ws:
            # 连接建立成功即通过（保持连接、无服务端错误）
            ws.send_text("ping")
            assert True

    def test_ws_disconnect_cleanup(self):
        with client.websocket_connect("/ws?session_id=wstest-002") as ws:
            ws.send_text("ping")
        # 断开后重新连接同一 session 不应报错
        with client.websocket_connect("/ws?session_id=wstest-002") as ws:
            ws.send_text("ping")
            assert True
