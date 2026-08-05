#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""记忆层桥接 — universal-agent-memory 记忆系统（自研，已内置 memory/）

把自研 universal-agent-memory（BM25+向量+RRF 混合检索）
接入 cyber-nyx 拟人壳，实现跨会话记忆。
记忆系统源码随项目 vendor 在 memory/ 目录，随仓库发布。

通过 MCP JSON-RPC over stdio 与 memory/scripts/mcp_server.py 通信。
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
        hermes = os.path.expanduser("~/.hermes")
        self._env = {
            **os.environ,
            "MEMORY_STORE": os.environ.get(
                "MEMORY_STORE", os.path.join(hermes, "memory")
            ),
            "MEMORY_PROJECT_ROOT": os.environ.get("MEMORY_PROJECT_ROOT", hermes),
            "MEMORY_GLOBAL_DIR": os.environ.get("MEMORY_GLOBAL_DIR", hermes),
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


def _default_script() -> str:
    """自动探测记忆系统的 mcp_server.py（优先项目内置 memory/ vendor）。"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.environ.get("NYX_MCP_SCRIPT", ""),
        os.path.join(project_root, "memory", "scripts", "mcp_server.py"),
        "/home/yaner/universal-agent-memory/scripts/mcp_server.py",
        "/root/.hermes/scripts/mcp_server.py",
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return "/root/.hermes/scripts/mcp_server.py"


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
        self.script = script or _default_script()

    @classmethod
    def _get_conn(cls, script: str) -> _MCPConnection:
        with cls._conn_lock:
            if cls._conn is None:
                cls._conn = _MCPConnection(script)
            return cls._conn

    def _call(self, tool: str, args: dict, timeout: int = 120) -> str:
        conn = self._get_conn(self.script)
        return conn._call(tool, args, timeout)

    def recall(
        self, query: str, top_k: int = 5, include_snapshots: bool = False
    ) -> list:
        """混合检索记忆。

        兼容两种输出格式：
          v1: "1. 内容 (score=0.62)"
          v2+: "#1 (relv 0.95) [stm/xxx][event] 内容"

        include_snapshots=False（默认）时过滤内部会话快照
        （[chat-session:xxx] 前缀），避免原始 JSON 泄漏给业务层。
        """
        raw = self._call("memory_recall", {"query": query, "top_k": top_k})
        items = []
        import re

        for line in raw.splitlines():
            m = re.match(
                r"^\s*#\d+\s*\(relv\s*([\d.]+)\)\s*\[[^\]]+\](\[[^\]]*\])?\s*(.*)$",
                line,
            )
            if m:
                content = m.group(3).strip()
                if not include_snapshots and content.startswith("[chat-session:"):
                    continue
                items.append({"content": content, "score": float(m.group(1))})
                continue
            m = re.match(r"^\s*\d+\.\s+(.+?)\s*\(score=([\d.]+)\)", line)
            if m:
                items.append(
                    {"content": m.group(1).strip(), "score": float(m.group(2))}
                )
        return items

    def remember(self, content: str, tags: str = "") -> bool:
        raw = self._call("memory_remember", {"content": content, "tags": tags})
        if not raw.strip():
            return False
        return not any(bad in raw for bad in ("❌", "失败", "错误", "Error"))

    def status(self) -> dict:
        raw = self._call("memory_status", {})
        return {"raw": raw[:300]}

    # --- 会话历史持久化（融合 universal-agent-memory） ---

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"[chat-session:{session_id}]"

    def save_chat_history(self, session_id: str, messages: list[dict]) -> bool:
        """保存会话历史（一条记忆 = 一个会话快照，JSON 序列化）。

        每次保存前先删除旧快照（关键词匹配），再写入新快照，
        type=event、tags 含 chat-history，便于分类检索。
        超长历史做滚动压缩：最多保留最近 50 条、单条消息截 400 字符，
        避免超过记忆系统单条 recall 输出上限导致无法恢复。
        """
        snap = messages[-50:]
        snap = [
            {
                "role": m.get("role", "user"),
                "content": str(m.get("content", ""))[:400],
                "emotion": m.get("emotion", "neutral"),
                "timestamp": m.get("timestamp", time.time()),
            }
            for m in snap
        ]
        key = self._session_key(session_id)
        try:
            self._call("memory_forget", {"keyword": key})
        except Exception:
            pass
        content = key + json.dumps(snap, ensure_ascii=False)
        return self.remember(
            content, tags=f"chat-history, session:{session_id}, type:event"
        )

    def load_chat_history(self, session_id: str) -> list[dict]:
        """从记忆系统恢复会话历史；无则返回空列表。"""
        key = self._session_key(session_id)
        try:
            results = self.recall(query=key, top_k=20, include_snapshots=True)
        except Exception:
            return []

        def _parse(content: str):
            """解析会话快照，非本会话/非法 JSON 返回 None。"""
            if not content.startswith(key):
                return None
            try:
                data = json.loads(content[len(key) :])
            except Exception:
                return None
            return data if isinstance(data, list) else None

        for item in results:
            data = _parse(item.get("content", ""))
            if data is not None:
                return data
        return []

    def forget_chat_history(self, session_id: str) -> bool:
        """删除会话历史记忆（"新对话"时调用）。"""
        key = self._session_key(session_id)
        try:
            self._call("memory_forget", {"keyword": key})
            return True
        except Exception:
            return False

    # --- 记忆可视化 / 管理（记忆面板） ---

    @staticmethod
    def _memory_dir():
        """短期记忆目录（stm/*.json，每条记忆一个文件）。"""
        from pathlib import Path as _P

        store = os.environ.get("MEMORY_STORE", _P.home() / ".hermes" / "memory")
        return _P(store) / "stm"

    def list_recent(self, limit: int = 30) -> list:
        """列出最近记忆（不依赖检索，直接读 STM 目录，按时间倒序）。"""
        import contextlib

        stm = self._memory_dir()
        items = []
        if stm.exists():
            for f in stm.glob("*.json"):
                with contextlib.suppress(Exception):
                    d = json.loads(f.read_text(encoding="utf-8"))
                    content = d.get("content", "")
                    # 内部会话快照（[chat-session:xxx]）不进入用户记忆面板
                    if content.startswith("[chat-session:"):
                        continue
                    items.append(
                        {
                            "id": d.get("id", f.stem),
                            "content": content,
                            "timestamp": d.get("timestamp", ""),
                            "mem_type": d.get("mem_type", ""),
                            "tags": (d.get("metadata") or {}).get("tags", []),
                        }
                    )
        items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return items[:limit]

    def forget(self, keyword: str) -> bool:
        """按关键词删除记忆（MCP memory_forget，内容包含匹配）。"""
        try:
            raw = self._call("memory_forget", {"keyword": keyword})
            return "0 条" not in raw
        except Exception:
            return False


class NullMemoryStore(MemoryStore):
    """演示兜底：无记忆。"""

    def recall(self, query: str, top_k: int = 5) -> list:
        return []

    def remember(self, content: str, tags: str = "") -> bool:
        return True

    def status(self) -> dict:
        return {"mode": "none"}

    def save_chat_history(self, session_id: str, messages: list[dict]) -> bool:
        return True

    def load_chat_history(self, session_id: str) -> list[dict]:
        return []

    def forget_chat_history(self, session_id: str) -> bool:
        return True

    def list_recent(self, limit: int = 30) -> list:
        return []

    def forget(self, keyword: str) -> bool:
        return False
