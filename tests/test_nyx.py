#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""NyxAgent 增强模块单元测试。"""

from nyx import NyxAgent


def make_agent():
    return NyxAgent("personas/nyx.json")


class TestEmotionState:
    def test_initial_neutral(self):
        nyx = make_agent()
        assert nyx.emotion_state == "neutral"
        assert nyx.emotion_history == []

    def test_empathy_mapping(self):
        nyx = make_agent()
        nyx.update_emotion("sad")
        assert nyx.emotion_state == "gentle"
        nyx.update_emotion("happy")
        assert nyx.emotion_state == "happy"
        nyx.update_emotion("angry")
        assert nyx.emotion_state == "calm"
        nyx.update_emotion("surprised")
        assert nyx.emotion_state == "curious"

    def test_emotion_history_tracked(self):
        nyx = make_agent()
        nyx.update_emotion("happy")
        nyx.update_emotion("sad")
        assert nyx.emotion_history == ["happy", "gentle"]


class TestMode:
    def test_default_companion(self):
        nyx = make_agent()
        assert nyx.mode == "companion"

    def test_switch_to_work(self):
        nyx = make_agent()
        msg = nyx.switch_mode("work")
        assert nyx.mode == "work"
        assert "工作" in msg

    def test_switch_to_companion(self):
        nyx = make_agent()
        nyx.switch_mode("work")
        nyx.switch_mode("companion")
        assert nyx.mode == "companion"

    def test_switch_invalid(self):
        nyx = make_agent()
        msg = nyx.switch_mode("sleep")
        assert nyx.mode == "companion"
        assert "不存在" in msg

    def test_mode_prompt(self):
        nyx = make_agent()
        nyx.switch_mode("work")
        assert "工作模式" in nyx.get_mode_prompt()
        nyx.switch_mode("companion")
        assert "陪伴模式" in nyx.get_mode_prompt()


class TestWrap:
    def test_companion_adds_ending(self):
        nyx = make_agent()
        assert nyx.wrap("任务完成了") in ("任务完成了呀", "任务完成了呢", "任务完成了~")

    def test_work_mode_no_fluff(self):
        nyx = make_agent()
        nyx.switch_mode("work")
        assert nyx.wrap("任务完成了") == "任务完成了"

    def test_no_double_ending(self):
        nyx = make_agent()
        assert nyx.wrap("任务完成啦") == "任务完成啦"

    def test_gentle_wrap(self):
        nyx = make_agent()
        nyx.update_emotion("sad")  # → gentle
        reply = nyx.wrap("我会一直陪着你")
        assert reply.startswith("（轻声）")

    def test_turn_count_increments(self):
        nyx = make_agent()
        assert nyx.turn_count == 0
        nyx.wrap("你好")
        nyx.wrap("在吗")
        assert nyx.turn_count == 2


class TestDialogStrategy:
    def test_should_ask_back_every_3(self):
        nyx = make_agent()
        for _ in range(3):
            nyx.wrap("x")
        assert nyx.should_ask_back() is True

    def test_should_ask_back_initial_false(self):
        nyx = make_agent()
        assert nyx.should_ask_back() is False

    def test_proactive_prompt_gentle(self):
        nyx = make_agent()
        nyx.update_emotion("sad")
        assert "心情不好" in nyx.get_proactive_prompt()

    def test_proactive_prompt_long_conversation(self):
        nyx = make_agent()
        for _ in range(6):
            nyx.wrap("x")
        assert "很多轮" in nyx.get_proactive_prompt()

    def test_proactive_prompt_empty_default(self):
        nyx = make_agent()
        assert nyx.get_proactive_prompt() == ""


class TestGreeting:
    def test_greeting_base(self):
        nyx = make_agent()
        assert "夜安" in nyx.greeting()

    def test_greeting_with_context(self):
        nyx = make_agent()
        g = nyx.greeting("上次聊到生日")
        assert "上次聊到生日" in g
