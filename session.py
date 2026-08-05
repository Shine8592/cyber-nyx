#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""多会话上下文管理 — 为每个用户维护独立对话历史。

功能：
  1. session_id 标识会话（自动生成或复用）
  2. 记录对话消息（user / assistant 轮次）
  3. 提供最近 N 轮上下文，用于 LLM 多轮对话
  4. 过期自动清理（TTL），防止内存膨胀

用法：
    from session import SessionManager
    sm = SessionManager()
    session = sm.get_or_create("abc123")
    session.add("user", "你好")
    ctx = session.context(max_turns=5)
"""

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Message:
    """单条对话消息。"""

    role: str  # "user" | "assistant"
    content: str
    emotion: str = "neutral"
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    """一个对话会话。"""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    messages: list[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def add(self, role: str, content: str, emotion: str = "neutral"):
        """追加一条消息并更新时间。"""
        self.messages.append(Message(role=role, content=content, emotion=emotion))
        self.last_active = time.time()

    def context(self, max_turns: int = 10) -> list[dict]:
        """返回最近 N 轮对话，用于 LLM 多轮上下文。

        每轮 = 1 条 user + 1 条 assistant，所以取最近 max_turns*2 条。
        返回格式：[{"role": ..., "content": ...}, ...]
        """
        recent = self.messages[-(max_turns * 2) :]
        return [{"role": m.role, "content": m.content} for m in recent]

    def last_emotion(self) -> str:
        """最后一条用户消息的情绪（用于主动关心）。"""
        for m in reversed(self.messages):
            if m.role == "user":
                return m.emotion
        return "neutral"


class SessionManager:
    """内存会话管理器：创建、复用、过期清理。"""

    def __init__(self, max_sessions: int = 100, ttl: int = 3600):
        self.sessions: dict[str, Session] = {}
        self.max_sessions = max_sessions
        self.ttl = ttl  # 会话空闲过期时间（秒）

    def get_or_create(self, session_id: str | None = None) -> Session:
        """获取已有会话或创建新会话（幂等：传入的 id 不存在则用它创建）。"""
        self._cleanup()
        if session_id:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.last_active = time.time()
                return session
            session = Session(id=session_id)  # 客户端持有该 id，直接复用
        else:
            session = Session()
        self.sessions[session.id] = session
        self._evict_if_needed()
        return session

    def get(self, session_id: str) -> Session | None:
        """只获取不创建。"""
        return self.sessions.get(session_id)

    def delete(self, session_id: str):
        """删除一个会话（前端"新对话"按钮使用）。"""
        self.sessions.pop(session_id, None)

    def count(self) -> int:
        return len(self.sessions)

    def _cleanup(self):
        """清理超过 TTL 未活跃的会话。"""
        now = time.time()
        expired = [
            sid for sid, s in self.sessions.items() if now - s.last_active > self.ttl
        ]
        for sid in expired:
            del self.sessions[sid]

    def _evict_if_needed(self):
        """超过上限时，淘汰最久未活跃的会话。"""
        if len(self.sessions) <= self.max_sessions:
            return
        oldest_id = min(self.sessions, key=lambda sid: self.sessions[sid].last_active)
        del self.sessions[oldest_id]
