"""Tests for proactive.py — 主动关心模块."""

import time
from unittest.mock import MagicMock

from proactive import ProactiveCare, _in_time_range


class TestTimeRange:
    def test_normal_range(self):
        assert _in_time_range(7, 6, 9) is True
        assert _in_time_range(5, 6, 9) is False
        assert _in_time_range(9, 6, 9) is False

    def test_cross_midnight(self):
        assert _in_time_range(23, 23, 2) is True
        assert _in_time_range(0, 23, 2) is True
        assert _in_time_range(1, 23, 2) is True
        assert _in_time_range(2, 23, 2) is False
        assert _in_time_range(22, 23, 2) is False


class TestShouldCare:
    def test_first_meet(self):
        care = ProactiveCare()
        should, kind = care.should_care("s1")
        assert should is True
        assert kind == "first_meet"

    def test_after_touch_no_care(self):
        """刚说完话，不该触发关心。"""
        care = ProactiveCare(idle_seconds=1800)
        care.touch("s1")
        should, kind = care.should_care("s1")
        # 可能触发时段问候，但不会触发 idle_reminder
        if should:
            assert kind != "idle_reminder"

    def test_idle_reminder(self):
        """模拟长时间未活动。"""
        care = ProactiveCare(idle_seconds=1)  # 1 秒算 idle
        care.touch("s1")
        time.sleep(1.1)
        should, kind = care.should_care("s1")
        assert should is True
        assert kind == "idle_reminder"

    def test_sad_emotion_triggers_comfort(self):
        """上次情绪 sad，应触发 comfort。"""
        care = ProactiveCare(idle_seconds=9999)
        care.touch("s1", emotion="sad")
        should, kind = care.should_care("s1")
        # 可能先触发时段问候
        if should:
            assert kind in ("comfort", "morning", "afternoon", "evening", "night")

    def test_no_duplicate_period_greeting(self):
        """同一时段不重复问候。"""
        care = ProactiveCare(idle_seconds=9999)
        care.touch("s1")
        # 第一次可能触发时段问候
        should1, kind1 = care.should_care("s1")
        if should1 and kind1 in ("morning", "afternoon", "evening", "night"):
            # 标记已问候
            care._sessions["s1"]["greeted_periods"].add(kind1)
            # 再次检查，同一时段不应再触发
            should2, kind2 = care.should_care("s1")
            if should2:
                assert kind2 != kind1


class TestGenerateCare:
    def test_returns_string(self):
        care = ProactiveCare()
        msg = care.generate_care("morning")
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_unknown_type_falls_back(self):
        care = ProactiveCare()
        msg = care.generate_care("nonexistent_type")
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_all_types_have_templates(self):
        care = ProactiveCare()
        for t in (
            "idle_reminder",
            "morning",
            "afternoon",
            "evening",
            "night",
            "comfort",
            "first_meet",
        ):
            msg = care.generate_care(t)
            assert len(msg) > 0, f"empty template for {t}"


class TestCheckAndNotify:
    def test_first_meet_returns_message(self):
        care = ProactiveCare()
        msg = care.check_and_notify("s1")
        assert msg is not None
        assert isinstance(msg, str)

    def test_no_care_returns_none(self):
        care = ProactiveCare(idle_seconds=9999)
        care.touch("s1")
        # 如果没触发时段问候，应该返回 None
        # 手动标记所有时段已问候
        care._sessions["s1"]["greeted_periods"] = {
            "morning",
            "afternoon",
            "evening",
            "night",
        }
        msg = care.check_and_notify("s1")
        assert msg is None

    def test_idle_returns_message(self):
        care = ProactiveCare(idle_seconds=1)
        care.touch("s1")
        time.sleep(1.1)
        msg = care.check_and_notify("s1")
        assert msg is not None


class TestTouchAndRecord:
    def test_touch_creates_session(self):
        care = ProactiveCare()
        care.touch("s1")
        info = care.get_session_info("s1")
        assert info["exists"] is True
        assert info["last_emotion"] == "neutral"

    def test_touch_updates_emotion(self):
        care = ProactiveCare()
        care.touch("s1", emotion="happy")
        info = care.get_session_info("s1")
        assert info["last_emotion"] == "happy"

    def test_record_interaction_calls_memory(self):
        mock_mem = MagicMock()
        care = ProactiveCare(memory_store=mock_mem)
        care.record_interaction("s1", "你好", "happy")
        mock_mem.remember.assert_called_once()

    def test_record_interaction_memory_failure_ok(self):
        mock_mem = MagicMock()
        mock_mem.remember.side_effect = Exception("mem down")
        care = ProactiveCare(memory_store=mock_mem)
        # 不应抛异常
        care.record_interaction("s1", "你好", "happy")


class TestGetSessionInfo:
    def test_nonexistent_session(self):
        care = ProactiveCare()
        info = care.get_session_info("nope")
        assert info["exists"] is False

    def test_existing_session(self):
        care = ProactiveCare()
        care.touch("s1", emotion="sad")
        info = care.get_session_info("s1")
        assert info["exists"] is True
        assert info["last_emotion"] == "sad"
        assert isinstance(info["greeted_periods"], list)
