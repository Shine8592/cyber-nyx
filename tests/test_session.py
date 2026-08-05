#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""会话管理模块单元测试。"""

import time

from session import Message, Session, SessionManager

# --- Message ---


class TestMessage:
    def test_default_emotion(self):
        m = Message(role="user", content="你好")
        assert m.emotion == "neutral"
        assert m.role == "user"
        assert m.content == "你好"

    def test_timestamp_auto(self):
        before = time.time()
        m = Message(role="user", content="x")
        after = time.time()
        assert before <= m.timestamp <= after


# --- Session ---


class TestSession:
    def test_auto_id(self):
        s1, s2 = Session(), Session()
        assert s1.id
        assert s1.id != s2.id

    def test_add_and_context(self):
        s = Session()
        s.add("user", "你好")
        s.add("assistant", "你好呀~")
        s.add("user", "今天天气如何？")
        s.add("assistant", "今晚月色很美呢~")
        ctx = s.context(max_turns=10)
        assert len(ctx) == 4
        assert ctx[0] == {"role": "user", "content": "你好"}
        assert ctx[-1] == {"role": "assistant", "content": "今晚月色很美呢~"}

    def test_context_limits_turns(self):
        s = Session()
        for i in range(10):
            s.add("user", f"q{i}")
            s.add("assistant", f"a{i}")
        ctx = s.context(max_turns=3)  # 只取最近 3 轮 = 6 条
        assert len(ctx) == 6
        assert ctx[0]["content"] == "q7"
        assert ctx[-1]["content"] == "a9"

    def test_context_empty(self):
        assert Session().context() == []

    def test_last_emotion(self):
        s = Session()
        s.add("user", "好难过", emotion="sad")
        s.add("assistant", "抱抱你~")
        assert s.last_emotion() == "sad"

    def test_last_emotion_default(self):
        s = Session()
        s.add("assistant", "你好呀~")
        assert s.last_emotion() == "neutral"
        assert Session().last_emotion() == "neutral"

    def test_last_active_updates(self):
        s = Session()
        t0 = s.last_active
        time.sleep(0.01)
        s.add("user", "hi")
        assert s.last_active > t0


# --- SessionManager ---


class TestSessionManager:
    def test_get_or_create_new(self):
        sm = SessionManager()
        s = sm.get_or_create()
        assert s.id
        assert sm.count() == 1

    def test_get_or_create_reuse(self):
        sm = SessionManager()
        s1 = sm.get_or_create("abc")
        s2 = sm.get_or_create("abc")
        assert s1 is s2
        assert sm.count() == 1

    def test_get_or_create_unknown_id_creates_with_that_id(self):
        sm = SessionManager()
        s = sm.get_or_create("client-fixed-id")
        assert s.id == "client-fixed-id"

    def test_get(self):
        sm = SessionManager()
        s = sm.get_or_create("abc")
        assert sm.get("abc") is s
        assert sm.get("nope") is None

    def test_delete(self):
        sm = SessionManager()
        sm.get_or_create("abc")
        sm.delete("abc")
        assert sm.get("abc") is None
        assert sm.count() == 0

    def test_delete_missing_no_error(self):
        sm = SessionManager()
        sm.delete("不存在")  # 不报错

    def test_ttl_cleanup(self):
        sm = SessionManager(ttl=10)
        sm.get_or_create("abc")
        sm.get("abc").last_active = time.time() - 100  # 模拟 100 秒前活跃
        sm.get_or_create("other")  # 触发清理
        assert sm.get("abc") is None
        assert sm.count() == 1

    def test_ttl_keeps_fresh(self):
        sm = SessionManager(ttl=1000)
        sm.get_or_create("abc")
        assert sm.count() == 1

    def test_max_sessions_evict(self):
        sm = SessionManager(max_sessions=2)
        sm.get_or_create("a")
        sm.get_or_create("b")
        sm.get_or_create("c")  # 应淘汰最旧的 a
        assert sm.count() == 2
        assert sm.get("a") is None
        assert sm.get("b") is not None
        assert sm.get("c") is not None
