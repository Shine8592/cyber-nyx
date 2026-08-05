#!/usr/bin/env python3
"""Cyber Nyx — FastAPI 拟人助手服务（v0.3：流式输出 + 多格式兼容）

启动：
    python app.py                                  # 演示模式
    NYX_HERMES_MODEL=... python app.py             # 启用 Hermes 内核
    NYX_STREAM=1 python app.py                     # 启用流式输出

访问： http://127.0.0.1:8000
"""
import json
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

import nyx_llm
from nyx import NyxAgent
from bridges.agent_core import NoCore
from bridges.hermes_adapter import HermesCore
from bridges.memory_bridge import MCPMemoryStore, NullMemoryStore

BASE = Path(__file__).resolve().parent
app = FastAPI(title="Cyber Nyx", version="0.3.0")

nyx = NyxAgent(str(BASE / "personas" / "nyx.json"))
LLM_ON = nyx_llm.available()

# --- 内核桥接（Hermes） ---
CORE_ENABLED = True
try:
    core = HermesCore()
    if not core.health():
        core = NoCore()
except Exception:
    core = NoCore()

# --- 记忆系统（universal-agent-memory MCP） ---
MEM_ENABLED = True
try:
    memory = MCPMemoryStore()
    memory.status()          # 探活，失败则降级
except Exception:
    memory = NullMemoryStore()
    MEM_ENABLED = False

SYSTEM_PROMPT = (
    f"你叫{nyx.display}（{nyx.title}），现在是深夜陪伴时刻。"
    f"你的人设：{'、'.join(nyx.persona.get('personality', []))}。"
    "说话温柔神秘，称呼对方为主人，句尾常用'呀/呢/~'。"
    "如果主人要求执行任务（查资料/写代码/改文件等），先简单确认，"
    "说明你会交给 Hermes 内核处理，再用你的语气回应。保持人设一致。"
)


class ChatIn(BaseModel):
    message: str
    format: Optional[str] = "text"  # text | json | sse


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE / "web" / "index.html").read_text(encoding="utf-8")


@app.post("/api/chat")
def chat(body: ChatIn):
    msg = body.message.strip()
    if not msg:
        return JSONResponse({"reply": "嗯？主人没有说话呢~", "emotion": "neutral"})

    # 1) 记忆召回
    recalled = []
    if MEM_ENABLED:
        try:
            recalled = memory.recall(msg)
        except Exception:
            recalled = []

    # 2) 判断是否为任务请求
    is_task = _looks_like_task(msg)

    if is_task and CORE_ENABLED and isinstance(core, HermesCore):
        ctx = ""
        if recalled:
            ctx = "（主人过去提及：" + "；".join(r["content"][:40] for r in recalled[:2]) + "）"
        persona_inject = (
            f"你是赛博助手Nyx(夜之女神/小夜)，性格" + "、".join(nyx.persona.get('personality', []))
            + "。请以稳定人设语气、称呼主人为'主人'，完成任务后简洁回答。"
            + f"\n主人过去的上下文：{ctx}" if ctx else f"你是赛博助手Nyx(夜之女神/小夜)，性格" + "、".join(nyx.persona.get('personality', [])) + "。请以稳定人设语气、称呼主人为'主人'，完成任务后简洁回答。"
        )
        result = core.submit(f"{msg}", persona_inject=persona_inject)
        raw = result.output if result.ok else f"唔，任务没跑成（{result.error}），我再看看~"
    else:
        mem_note = ""
        if recalled:
            mem_note = f"（我记得你之前提过:{recalled[0]['content'][:30]}…）"
        if LLM_ON:
            try:
                raw = nyx_llm.chat(SYSTEM_PROMPT, mem_note + msg)
            except Exception as e:
                raw = f"唔，我这边网络打了个盹呢（{type(e).__name__}）。稍后再试试好不好？"
        else:
            raw = nyx_llm.local_reply(msg) + mem_note

    reply = nyx.wrap(raw)
    emotion = _infer_emotion(msg)

    # 3) 记忆保存
    if _looks_important(msg) and MEM_ENABLED:
        try:
            memory.remember(f"主人说：{msg}", "from-chat")
        except Exception:
            pass

    fmt = body.format or "text"
    if fmt == "json":
        return JSONResponse({
            "reply": reply, "emotion": emotion,
            "recalled": len(recalled), "format": "json",
        })
    return JSONResponse({"reply": reply, "emotion": emotion, "recalled": len(recalled)})


@app.post("/api/chat/stream")
def chat_stream(body: ChatIn):
    """SSE 流式输出，逐字推送。"""
    msg = body.message.strip()
    if not msg:
        async def empty():
            yield f"data: {json.dumps({'reply': '嗯？主人没有说话呢~', 'emotion': 'neutral'})}\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    async def generate():
        recalled = []
        if MEM_ENABLED:
            try:
                recalled = memory.recall(msg)
            except Exception:
                recalled = []

        is_task = _looks_like_task(msg)
        raw = ""

        if is_task and CORE_ENABLED and isinstance(core, HermesCore):
            ctx = ""
            if recalled:
                ctx = "（主人过去提及：" + "；".join(r["content"][:40] for r in recalled[:2]) + "）"
            persona_inject = (
                f"你是赛博助手Nyx(夜之女神/小夜)，性格" + "、".join(nyx.persona.get('personality', []))
                + "。请以稳定人设语气、称呼主人为'主人'，完成任务后简洁回答。"
                + f"\n主人过去的上下文：{ctx}" if ctx else f"你是赛博助手Nyx(夜之女神/小夜)，性格" + "、".join(nyx.persona.get('personality', [])) + "。请以稳定人设语气、称呼主人为'主人'，完成任务后简洁回答。"
            )
            result = core.submit(f"{msg}", persona_inject=persona_inject)
            raw = result.output if result.ok else f"唔，任务没跑成（{result.error}），我再看看~"
        else:
            mem_note = ""
            if recalled:
                mem_note = f"（我记得你之前提过:{recalled[0]['content'][:30]}…）"
            if LLM_ON:
                try:
                    for chunk in nyx_llm.chat_stream(SYSTEM_PROMPT, mem_note + msg):
                        yield f"data: {json.dumps({'chunk': chunk, 'emotion': _infer_emotion(msg)})}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    return
                except Exception as e:
                    raw = f"唔，我这边网络打了个盹呢（{type(e).__name__}）。稍后再试试好不好？"
            else:
                raw = nyx_llm.local_reply(msg) + mem_note

        reply = nyx.wrap(raw)
        emotion = _infer_emotion(msg)
        yield f"data: {json.dumps({'reply': reply, 'emotion': emotion, 'recalled': len(recalled), 'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/status")
def status():
    return {
        "name": nyx.name, "display": nyx.display, "title": nyx.title,
        "llm": "connected" if LLM_ON else "local-demo",
        "core": core.name, "core_health": core.health(),
        "memory": "universal-agent-memory" if MEM_ENABLED else "none",
        "persona": nyx.persona["name"],
        "version": "0.3.0",
    }


def _infer_emotion(msg: str) -> str:
    if any(k in msg for k in ["哈哈", "开心", "太好了", "😄", "❤"]):
        return "happy"
    if any(k in msg for k in ["难过", "伤心", "哭", "累", "😢", "烦"]):
        return "sad"
    if msg.endswith("?") or msg.endswith("？") or "吗" in msg or "呢" in msg:
        return "curious"
    return "neutral"


def _looks_like_task(msg: str) -> bool:
    task_kw = ["帮我", "查", "算", "写", "改", "列出", "搜索", "打开",
               "整理", "生成", "下载", "运行", "建", "做", "翻译", "总结"]
    return any(k in msg for k in task_kw)


def _looks_important(msg: str) -> bool:
    kw = ["我的电话", "记得", "生日", "喜欢", "讨厌", "重要", "约定", "地址"]
    return any(k in msg for k in kw)


if __name__ == "__main__":
    import uvicorn
    print(f"🌙 Cyber Nyx v0.3 · llm={'在线' if LLM_ON else '本地演示'} · core={core.name} · memory={'universal-agent-memory' if MEM_ENABLED else 'none'}")
    print("   访问 http://127.0.0.1:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)