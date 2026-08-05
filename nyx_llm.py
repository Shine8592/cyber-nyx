#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""Nyx LLM 适配器 — OpenAI 兼容 API 接入（可配置端点/密钥/模型）。

若未配置任何 API，则退回"本地小夜"规则回复（演示模式，零外部依赖）。
环境变量：
    NYX_API_BASE    e.g. https://api.openai.com/v1
    NYX_API_KEY     e.g. sk-xxx
    NYX_MODEL       e.g. gpt-4o-mini / deepseek-chat
"""
import os
import urllib.request
import json


def _resolve_cfg():
    return {
        "base": os.environ.get("NYX_API_BASE", "").rstrip("/"),
        "key": os.environ.get("NYX_API_KEY", ""),
        "model": os.environ.get("NYX_MODEL", "gpt-4o-mini"),
    }


def available() -> bool:
    cfg = _resolve_cfg()
    return bool(cfg["base"] and cfg["key"])


def chat(system_prompt: str, user_message: str, temperature: float = 0.8) -> str:
    """调用 OpenAI 兼容 chat/completions。失败抛异常由上层兜底。"""
    cfg = _resolve_cfg()
    url = f"{cfg['base']}/chat/completions"
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['key']}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


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
    idx = int(hashlib.md5(user_message.encode("utf-8")).hexdigest(), 16) % len(_LOCAL_REPLIES)
    return _LOCAL_REPLIES[idx]