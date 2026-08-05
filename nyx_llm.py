#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""Nyx LLM 适配器 — OpenAI 兼容 API 接入（可配置端点/密钥/模型）。

若未配置任何 API，则退回"本地小夜"规则回复（演示模式，零外部依赖）。
支持自动重试（指数退避）和 SSE 流式输出。

环境变量：
    NYX_API_BASE    e.g. https://api.openai.com/v1
    NYX_API_KEY     e.g. sk-xxx
    NYX_MODEL       e.g. gpt-4o-mini / deepseek-chat
    NYX_RETRY_MAX   重试次数 (默认 3)
    NYX_RETRY_BASE  重试基础秒数 (默认 1.0)
    NYX_STREAM      设为 "1" 启用 SSE 流式输出
"""

import json
import os
import time
import urllib.request
from collections.abc import Generator

MAX_RETRIES = int(os.environ.get("NYX_RETRY_MAX", "3"))
RETRY_BASE = float(os.environ.get("NYX_RETRY_BASE", "1.0"))
STREAM_ENABLED = os.environ.get("NYX_STREAM", "0") == "1"


def _resolve_cfg():
    return {
        "base": os.environ.get("NYX_API_BASE", "").rstrip("/"),
        "key": os.environ.get("NYX_API_KEY", ""),
        "model": os.environ.get("NYX_MODEL", "gpt-4o-mini"),
    }


def available() -> bool:
    cfg = _resolve_cfg()
    return bool(cfg["base"] and cfg["key"])


def _request(payload: dict, stream: bool = False) -> urllib.request.urlopen:
    """发送请求，返回响应对象。供 chat 和 stream 共享。"""
    cfg = _resolve_cfg()
    url = f"{cfg['base']}/chat/completions"
    payload["stream"] = stream
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['key']}",
        },
    )
    return urllib.request.urlopen(req, timeout=60)


def chat(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.8,
    history: list[dict] | None = None,
) -> str:
    """调用 OpenAI 兼容 chat/completions。失败自动重试，最终抛异常由上层兜底。

    history 参数：可传入多轮上下文列表 [{"role": ..., "content": ...}, ...]，
    放在 system 与当前 user 消息之间。
    """
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history[-20:])  # 最多携带 20 条历史
    messages.append({"role": "user", "content": user_message})
    payload = {
        "model": _resolve_cfg()["model"],
        "messages": messages,
        "temperature": temperature,
    }
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = _request(payload)
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                wait = RETRY_BASE * (2 ** (attempt - 1))
                time.sleep(wait)
    raise last_err


def chat_stream(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.8,
    history: list[dict] | None = None,
) -> Generator[str, None, None]:
    """SSE 流式输出，逐块 yield 文本片段。失败自动重试。"""
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history[-20:])
    messages.append({"role": "user", "content": user_message})
    payload = {
        "model": _resolve_cfg()["model"],
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = _request(payload, stream=True)
            for line in resp:
                line = line.decode("utf-8").strip()
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                chunk = json.loads(line[6:])
                delta = (
                    chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                )
                if delta:
                    yield delta
            return
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                wait = RETRY_BASE * (2 ** (attempt - 1))
                time.sleep(wait)
    raise last_err


# ---- 演示模式：无 API 时的本地小夜 ----
_LOCAL_REPLIES = [
    "嗯哼~ 我在听呢，主人再说说看？",
    "这个夜晚很安静，你愿意告诉我更多吗？",
    "我记下了~ 下次一定不会忘。",
    "夜风很温柔，像你说话的声音。",
    "交给我吧，我会好好守护这份心意呀。",
]


def local_reply(user_message: str) -> str:
    """本地演示回复：带一点拟人味道，绝不假装是真实智能。"""
    import hashlib

    idx = int(hashlib.md5(user_message.encode("utf-8")).hexdigest(), 16) % len(
        _LOCAL_REPLIES
    )
    return _LOCAL_REPLIES[idx]
