#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""记忆层桥接 — universal-agent-memory MCP（自研记忆系统）

把咱自己研发的 universal-agent-memory（BM25+向量+RRF 混合检索）
接入 cyber-nyx 拟人壳，实现跨会话记忆。

通过 MCP JSON-RPC over stdio 与 mcp_server.py 通信。
使用长连接复用，避免每次操作启动子进程的开销。
"""

import json
import os
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from queue import Empty, Queue


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


class _MCPConnection:
    """单例 MCP 连接管理器，复用子进程避免重复启动开销。"""

    _instance = None
    _lock = threading.Lock()

    def __init__(self, script: str):
        self.script = script
        self._env = {
            **os.environ,
            "MEMORY_STORE": os.environ.get("MEMORY_STORE", "/root/.hermes/memory"),
            "MEMORY_PROJECT_ROOT": os.environ.get(
                "MEMORY_PROJECT_ROOT", "/root/.hermes"
            ),
            "MEMORY_GLOBAL_DIR": os.environ.get("MEMORY_GLOBAL_DIR", "/root/.hermes"),
        }
        self._proc = None
        self._stdout_queue = Queue()
        self._started = False

    def _ensure_started(self):
        if self._started and self._proc and self._proc.poll() is None:
            return
        self._proc = subprocess.Popen(
            ["python3", self.script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=self._env,
            cwd=os.path.dirname(self.script) or None,
        )

        # 后台线程持续读取 stdout
        def _read_stdout():
            for line in iter(self._proc.stdout.readline, ""):
                self._stdout_queue.put(line.rstrip("\n"))

        self._reader_thread = threading.Thread(target=_read_stdout, daemon=True)
        self._reader_thread.start()
        self._started = True

    def _call(self, tool: str, args: dict, timeout: int = 120) -> str:
        self._ensure_started()
        payload = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "cyber-nyx", "version": "0.2"},
                    },
                }
            )
            + "\n"
            + json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": args},
                }
            )
            + "\n"
        )
        self._proc.stdin.write(payload)
        self._proc.stdin.flush()

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = self._stdout_queue.get(timeout=min(1.0, deadline - time.time()))
            except Empty:
                if self._proc.poll() is not None:
                    raise RuntimeError(
                        f"MCP server 进程已退出 (rc={self._proc.returncode})"
                    )
                continue
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == 2:
                return msg.get("result", {}).get("content", [{}])[0].get("text", "")
        raise RuntimeError(f"MCP {tool} 响应超时 ({timeout}s)")

    def close(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.stdin.close()
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()


class MCPMemoryStore(MemoryStore):
    """基于 universal-agent-memory MCP server 的实现（长连接复用）。

    环境变量：
        MEMORY_STORE=/root/.hermes/memory
        MEMORY_PROJECT_ROOT=/root/.hermes
        MEMORY_GLOBAL_DIR=/root/.hermes
        NYX_MCP_SCRIPT=...   # mcp_server.py 路径（可选，默认自动探测）
    """

    _conn: _MCPConnection = None
    _conn_lock = threading.Lock()

    def __init__(self, script: str = ""):
        self.script = script or os.environ.get(
            "NYX_MCP_SCRIPT", "/root/.hermes/scripts/mcp_server.py"
        )

    @classmethod
    def _get_conn(cls) -> _MCPConnection:
        with cls._conn_lock:
            if cls._conn is None:
                cls._conn = _MCPConnection(cls.script)
            return cls._conn

    def _call(self, tool: str, args: dict, timeout: int = 120) -> str:
        conn = self._get_conn()
        return conn._call(tool, args, timeout)

    def recall(self, query: str, top_k: int = 5) -> list:
        raw = self._call("memory_recall", {"query": query, "top_k": top_k})
        items = []
        # 响应形如 "1. 内容 (score=0.62)"
        import re

        for line in raw.splitlines():
            m = re.match(r"^\s*\d+\.\s+(.+?)\s*\(score=([\d.]+)\)", line)
            if m:
                items.append(
                    {"content": m.group(1).strip(), "score": float(m.group(2))}
                )
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
