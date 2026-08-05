"""Unit tests for nyx_llm — retry, streaming, config resolution."""
import json
import os
from unittest.mock import patch, MagicMock

import pytest

import nyx_llm


class TestResolveCfg:
    def test_empty_when_no_env(self):
        cfg = nyx_llm._resolve_cfg()
        assert cfg["base"] == ""
        assert cfg["key"] == ""
        assert cfg["model"] == "gpt-4o-mini"

    def test_reads_env_vars(self):
        with patch.dict(os.environ, {
            "NYX_API_BASE": "https://api.openai.com/v1",
            "NYX_API_KEY": "sk-test123",
            "NYX_MODEL": "gpt-4",
        }):
            cfg = nyx_llm._resolve_cfg()
        assert cfg["base"] == "https://api.openai.com/v1"
        assert cfg["key"] == "sk-test123"
        assert cfg["model"] == "gpt-4"

    def test_strips_trailing_slash(self):
        with patch.dict(os.environ, {"NYX_API_BASE": "https://api.openai.com/v1/"}):
            cfg = nyx_llm._resolve_cfg()
        assert cfg["base"] == "https://api.openai.com/v1"


class TestAvailable:
    def test_false_when_no_base(self):
        with patch.dict(os.environ, {"NYX_API_KEY": "sk-test"}):
            assert nyx_llm.available() is False

    def test_false_when_no_key(self):
        with patch.dict(os.environ, {"NYX_API_BASE": "https://api.openai.com/v1"}):
            assert nyx_llm.available() is False

    def test_true_when_both_set(self):
        with patch.dict(os.environ, {
            "NYX_API_BASE": "https://api.openai.com/v1",
            "NYX_API_KEY": "sk-test",
        }):
            assert nyx_llm.available() is True


class TestRetry:
    @patch("nyx_llm._request")
    def test_retries_on_failure(self, mock_request):
        mock_request.side_effect = Exception("network error")
        with pytest.raises(Exception, match="network error"):
            nyx_llm.chat("system", "hello")
        assert mock_request.call_count == nyx_llm.MAX_RETRIES

    @patch("nyx_llm._request")
    def test_succeeds_on_second_attempt(self, mock_request):
        mock_request.side_effect = [
            Exception("network error"),
            MagicMock(read=lambda: json.dumps({
                "choices": [{"message": {"content": "ok"}}]
            }).encode()),
        ]
        result = nyx_llm.chat("system", "hello")
        assert result == "ok"
        assert mock_request.call_count == 2

    @patch("nyx_llm.time.sleep")
    @patch("nyx_llm._request")
    def test_exponential_backoff(self, mock_request, mock_sleep):
        mock_request.side_effect = Exception("fail")
        with pytest.raises(Exception):
            nyx_llm.chat("system", "hello")
        # First retry waits RETRY_BASE * 2^0 = 1.0s, second waits RETRY_BASE * 2^1 = 2.0s
        assert mock_sleep.call_count == nyx_llm.MAX_RETRIES - 1
        assert mock_sleep.call_args_list[0][0][0] == 1.0  # RETRY_BASE * 1
        assert mock_sleep.call_args_list[1][0][0] == 2.0  # RETRY_BASE * 2


class TestStreaming:
    @patch("nyx_llm._request")
    def test_stream_yields_chunks(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.__iter__ = lambda self: iter([
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n',
            b'data: {"choices":[{"delta":{"content":" world"}}]}\n',
            b'data: [DONE]\n',
        ])
        mock_request.return_value = mock_resp

        chunks = list(nyx_llm.chat_stream("system", "hello"))
        assert chunks == ["Hello", " world"]

    @patch("nyx_llm._request")
    def test_stream_retries_on_failure(self, mock_request):
        mock_request.side_effect = Exception("stream error")
        with pytest.raises(Exception, match="stream error"):
            list(nyx_llm.chat_stream("system", "hello"))
        assert mock_request.call_count == nyx_llm.MAX_RETRIES


class TestLocalReply:
    def test_returns_string(self):
        result = nyx_llm.local_reply("hello")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_deterministic(self):
        r1 = nyx_llm.local_reply("same message")
        r2 = nyx_llm.local_reply("same message")
        assert r1 == r2

    def test_different_messages(self):
        r1 = nyx_llm.local_reply("message one")
        r2 = nyx_llm.local_reply("message two")
        # May collide but should not crash
        assert isinstance(r1, str)
        assert isinstance(r2, str)