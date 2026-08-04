#!/usr/bin/env python3
"""记忆层桥接 — universal-agent-memory MCP（自研记忆系统）

把咱自己研发的 universal-agent-memory（BM25+向量+RRF 混合检索）
接入 cyber-nyx 拟人壳，实现跨会话记忆。

通过 MCP JSON-RPC over stdio 与 mcp_server.py 通信。
"""
import json
import os
import subprocess
import time
from abc import ABC, abstractmethod


class MemoryStore(ABC):
    """记忆系统统一接口（与具体实现解耦）。"""

    @abstractmethod
    def recall(self, query: str, top_k: int = 5) -> list:
        """语义检索记忆，返回 [{content, score, tags?, updated?}]"""

    @abstractmethod
    def remember(self, content: str, tags: str = "") -> bool:
        """保存一条记忆（自动分类 + Git 版本管理）。"""

    @abstractmethod
    def status(self) -> dict:
        """记忆系统状态。"""


class MCPMemoryStore(MemoryStore):
    """基于 universal-agent-memory MCP server 的实现。

    环境变量：
        MEMORY_STORE=/root/.hermes/memory
        MEMORY_PROJECT_ROOT=/root/.hermes
        MEMORY_GLOBAL_DIR=/root/.hermes
        NYX_MCP_SCRIPT=...   # mcp_server.py 路径（可选，默认自动探测）
    """

    def __init__(self, script: str = ""):
        self.script = script or os.environ.get(
            "NYX_MCP_SCRIPT", "/root/.hermes/scripts/mcp_server.py"
        )
        self._env = {
            **os.environ,
            "MEMORY_STORE": os.environ.get("MEMORY_STORE", "/root/.hermes/memory"),
            "MEMORY_PROJECT_ROOT": os.environ.get("MEMORY_PROJECT_ROOT", "/root/.hermes"),
            "MEMORY_GLOBAL_DIR": os.environ.get("MEMORY_GLOBAL_DIR", "/root/.hermes"),
        }

    def _call(self, tool: str, args: dict, timeout: int = 120) -> str:
        """与 MCP server 做一次 JSON-RPC 调用（initialize → tools/call）。"""
        payload = (
            json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "cyber-nyx", "version": "0.2"}},
            }) + "\n" +
            json.dumps({
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": tool, "arguments": args},
            }) + "\n"
        )
        proc = subprocess.run(
            ["python3", self.script],
            input=payload, capture_output=True, text=True,
            timeout=timeout, env=self._env, cwd=os.path.dirname(self.script),
        )
        # 解析最后一行 JSON-RPC 响应
        for line in reversed(proc.stdout.strip().splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == 2:
                return msg.get("result", {}).get("content", [{}])[0].get("text", "")
        raise RuntimeError(f"MCP {tool} 无响应: {proc.stderr[:200]}")

    def recall(self, query: str, top_k: int = 5) -> list:
        raw = self._call("memory_recall", {"query": query, "top_k": top_k})
        items = []
        # 响应形如 "1. 内容 (score=0.62)"
        import re
        for line in raw.splitlines():
            m = re.match(r"^\s*\d+\.\s+(.+?)\s*\(score=([\d.]+)\)", line)
            if m:
                items.append({"content": m.group(1).strip(), "score": float(m.group(2))})
        return items

    def remember(self, content: str, tags: str = "") -> bool:
        raw = self._call("memory_remember", {"content": content, "tags": tags})
        return "✅" in raw or "成功" in raw or "saved" in raw.lower()

    def status(self) -> dict:
        raw = self._call("memory_status", {})
        return {"raw": raw[:300]}


class NullMemoryStore(MemoryStore):
    """演示兜底：无记忆。"""

    def recall(self, query: str, top_k: int = 5) -> list:
        return []

    def remember(self, content: str, tags: str = "") -> bool:
        return True

    def status(self) -> dict:
        return {"mode": "none"}