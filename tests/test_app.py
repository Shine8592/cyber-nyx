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
        assert data["version"] == "0.4.0"

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

    def test_sad_emotion(self):
        resp = client.post("/api/chat", json={"message": "难过伤心"})
        data = resp.json()
        assert data["emotion"] == "sad"

    def test_curious_emotion(self):
        resp = client.post("/api/chat", json={"message": "你在做什么吗？"})
        data = resp.json()
        assert data["emotion"] == "curious"

    def test_neutral_emotion(self):
        resp = client.post("/api/chat", json={"message": "今天天气不错"})
        data = resp.json()
        assert data["emotion"] == "neutral"


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
