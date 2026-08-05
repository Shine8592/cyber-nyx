#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""对话历史持久化测试（fake memory store + 真实 MCP 集成）。"""

import json

from session import SessionManager


class FakeMemoryStore:
    """内存版记忆系统，模拟 save/load/forget。"""

    def __init__(self):
        self.store = {}

    def save_chat_history(self, session_id: str, messages: list[dict]) -> bool:
        key = f"[chat-session:{session_id}]"
        self.store[session_id] = key + json.dumps(messages, ensure_ascii=False)
        return True

    def load_chat_history(self, session_id: str) -> list[dict]:
        raw = self.store.get(session_id)
        if not raw:
            return []
        key = f"[chat-session:{session_id}]"
        if raw.startswith(key):
            return json.loads(raw[len(key) :])
        return []

    def forget_chat_history(self, session_id: str) -> bool:
        self.store.pop(session_id, None)
        return True


class TestPersist:
    def test_persist_roundtrip(self):
        fake = FakeMemoryStore()
        sm = SessionManager(memory_store=fake)
        s = sm.get_or_create("abc")
        s.add("user", "你好", emotion="happy")
        s.add("assistant", "你好呀~")
        assert sm.persist(s) is True
        assert "abc" in fake.store

    def test_restore_from_memory(self):
        fake = FakeMemoryStore()
        sm1 = SessionManager(memory_store=fake)
        s = sm1.get_or_create("abc")
        s.add("user", "记住这句话", emotion="neutral")
        s.add("assistant", "好的呢")
        sm1.persist(s)

        # 全新管理器（模拟服务重启），同一 session_id 应恢复历史
        sm2 = SessionManager(memory_store=fake)
        s2 = sm2.get_or_create("abc")
        assert len(s2.messages) == 2
        assert s2.messages[0].content == "记住这句话"
        assert s2.messages[0].role == "user"
        assert s2.messages[1].role == "assistant"

    def test_restore_preserves_emotion_and_timestamp(self):
        fake = FakeMemoryStore()
        sm1 = SessionManager(memory_store=fake)
        s = sm1.get_or_create("abc")
        s.add("user", "好难过", emotion="sad")
        sm1.persist(s)

        sm2 = SessionManager(memory_store=fake)
        s2 = sm2.get_or_create("abc")
        assert s2.messages[0].emotion == "sad"
        assert s2.messages[0].timestamp > 0

    def test_no_memory_no_persist(self):
        sm = SessionManager()  # 无 memory_store
        s = sm.get_or_create("abc")
        s.add("user", "hi")
        assert sm.persist(s) is False

    def test_empty_session_not_persisted(self):
        fake = FakeMemoryStore()
        sm = SessionManager(memory_store=fake)
        s = sm.get_or_create("abc")
        assert sm.persist(s) is False
        assert "abc" not in fake.store

    def test_delete_forgets_persisted(self):
        fake = FakeMemoryStore()
        sm = SessionManager(memory_store=fake)
        s = sm.get_or_create("abc")
        s.add("user", "hi")
        sm.persist(s)
        sm.delete("abc")
        assert fake.store == {}
        # 重新创建不应恢复
        s2 = sm.get_or_create("abc")
        assert len(s2.messages) == 0


class TestPersistenceUpdate:
    def test_second_save_overwrites(self):
        fake = FakeMemoryStore()
        sm = SessionManager(memory_store=fake)
        s = sm.get_or_create("abc")
        s.add("user", "第一条")
        sm.persist(s)
        s.add("user", "第二条")
        sm.persist(s)

        sm2 = SessionManager(memory_store=fake)
        s2 = sm2.get_or_create("abc")
        assert len(s2.messages) == 2  # 不是 1 条
        assert s2.messages[-1].content == "第二条"

    def test_restore_then_persist_no_duplicate(self):
        fake = FakeMemoryStore()
        sm = SessionManager(memory_store=fake)
        s = sm.get_or_create("abc")
        s.add("user", "原始")
        sm.persist(s)

        sm2 = SessionManager(memory_store=fake)
        s2 = sm2.get_or_create("abc")  # 恢复 1 条
        s2.add("user", "追加")
        sm2.persist(s2)

        sm3 = SessionManager(memory_store=fake)
        s3 = sm3.get_or_create("abc")
        assert len(s3.messages) == 2
        assert s3.messages[0].content == "原始"
        assert s3.messages[1].content == "追加"


class TestCorruptedMemory:
    def test_bad_json_returns_empty(self):
        class BadStore(FakeMemoryStore):
            def load_chat_history(self, session_id):
                return [{"role": "user"}]  # 缺 content 也能容错

        sm = SessionManager(memory_store=BadStore())
        s = sm.get_or_create("abc")
        assert len(s.messages) == 1
        assert s.messages[0].content == ""

    def test_store_exception_safe(self):
        class BoomStore(FakeMemoryStore):
            def load_chat_history(self, session_id):
                raise RuntimeError("boom")

        sm = SessionManager(memory_store=BoomStore())
        s = sm.get_or_create("abc")
        assert len(s.messages) == 0  # 异常静默降级
