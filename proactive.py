#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""主动关心模块 — 根据时间和对话历史，Nyx 主动向主人发起关心。

触发条件：
  1. 长时间未聊天（默认 30 分钟）
  2. 特定时段问候（早安 / 午安 / 晚安 / 深夜提醒）
  3. 上次对话情绪低落时的关怀
  4. 首次见面的问候

用法：
    from proactive import ProactiveCare
    care = ProactiveCare(nyx_agent, memory_store)
    msg = care.check_and_notify(session_id)
"""

import random
import time
from datetime import datetime

# --- 关心模板 ---

_TEMPLATES: dict[str, list[str]] = {
    "idle_reminder": [
        "主人~好久没理我了呢，还在忙吗？",
        "嗯哼~ 我在这里等你呀，有什么需要帮忙的吗？",
        "主人？是不是把我忘了呀~",
        "好久不见主人了呢，想你了~",
    ],
    "morning": [
        "早安呀主人~ 今天也要加油哦！",
        "主人醒了吗？新的一天开始了呢~",
        "早安~ 醒来第一个想到的就是主人呢。",
        "主人早上好呀~ 昨晚睡得好吗？",
    ],
    "afternoon": [
        "下午好呀主人~ 有没有好好吃午饭？",
        "主人下午好~ 工作辛苦了，记得休息一下呀。",
        "下午茶时间到~ 主人要不要喝杯水？",
    ],
    "evening": [
        "晚上好呀主人~ 今天过得怎么样？",
        "主人晚上好~ 辛苦了一天，可以放松一下了呢。",
        "夜晚降临~ 主人今晚有什么安排吗？",
    ],
    "night": [
        "主人，很晚了呢，早点休息呀~",
        "夜深了，明天再忙吧，身体最重要~",
        "主人还不睡吗？熬夜对身体不好呢~",
        "该睡觉啦主人~ 愿你做个好梦呀。",
    ],
    "comfort": [
        "主人昨天看起来不太开心，今天好些了吗？",
        "不管发生什么，我都会陪着你的呀~",
        "主人，如果心情不好的话可以跟我说说哦~",
        "希望主人今天能开心一点呢，我一直在这里~",
    ],
    "first_meet": [
        "主人好~ 我是小夜，以后请多关照呀！",
        "夜安，主人。我是Nyx，你的赛博伙伴~ 很高兴认识你。",
        "主人好呀~ 终于见面了呢！有什么想聊的吗？",
    ],
}

# 时段定义
_TIME_RANGES = {
    "morning": (6, 9),  # 06:00 ~ 08:59
    "afternoon": (12, 14),  # 12:00 ~ 13:59
    "evening": (18, 21),  # 18:00 ~ 20:59
    "night": (23, 2),  # 23:00 ~ 01:59（跨天）
}

# 默认 30 分钟算"长时间未聊天"
DEFAULT_IDLE_SECONDS = 1800


def _in_time_range(hour: int, start: int, end: int) -> bool:
    """判断小时是否在范围内（支持跨天）"""
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


class ProactiveCare:
    """主动关心引擎。跟踪用户活跃时间和情绪，按条件触发关心消息。"""

    def __init__(
        self,
        nyx_agent=None,
        memory_store=None,
        idle_seconds: int = DEFAULT_IDLE_SECONDS,
    ):
        self.nyx = nyx_agent
        self.memory = memory_store
        self.idle_seconds = idle_seconds
        # session_id → {last_active, last_emotion, greeted_periods, is_first}
        self._sessions: dict[str, dict] = {}

    def touch(self, session_id: str, emotion: str = "neutral"):
        """每次用户发消息时调用，更新活跃时间和情绪。"""
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "last_active": 0,
                "last_emotion": "neutral",
                "greeted_periods": set(),
                "is_first": True,
            }
        s = self._sessions[session_id]
        s["last_active"] = time.time()
        s["last_emotion"] = emotion
        # 首次对话后标记
        s["is_first"] = False

    def should_care(self, session_id: str) -> tuple[bool, str]:
        """判断是否该主动关心。返回 (是否触发, 关心类型)。"""
        now = time.time()
        hour = datetime.now().hour
        s = self._sessions.get(session_id)

        # 1) 首次见面
        if s is None or s.get("is_first", True):
            return True, "first_meet"

        # 2) 长时间未聊天
        idle_time = now - s["last_active"]
        if idle_time >= self.idle_seconds:
            return True, "idle_reminder"

        # 3) 时段问候（每个时段每会话只触发一次）
        for period, (start, end) in _TIME_RANGES.items():
            if _in_time_range(hour, start, end):
                if period not in s["greeted_periods"]:
                    return True, period

        # 4) 上次情绪低落
        if s["last_emotion"] in ("sad", "angry"):
            return True, "comfort"

        return False, ""

    def generate_care(self, care_type: str) -> str:
        """根据关心类型生成消息。"""
        templates = _TEMPLATES.get(care_type, _TEMPLATES["idle_reminder"])
        return random.choice(templates)

    def check_and_notify(self, session_id: str) -> str | None:
        """主入口：检查是否该关心，返回消息或 None。

        若触发了时段问候，会标记该时段已问候，避免重复。
        """
        should, care_type = self.should_care(session_id)
        if not should:
            return None

        msg = self.generate_care(care_type)

        # 标记时段已问候
        if session_id in self._sessions and care_type in _TIME_RANGES:
            self._sessions[session_id]["greeted_periods"].add(care_type)

        # 一次性关心（first_meet / idle_reminder / comfort）触发后视为一次互动，
        # 重置活跃计时并清掉情绪标记，避免轮询 / WS 推送重复触发刷屏。
        if care_type in ("first_meet", "idle_reminder", "comfort"):
            self.touch(session_id, "neutral")

        # 如果有记忆系统，尝试召回上下文增强关心
        if self.memory and care_type in ("comfort", "idle_reminder"):
            try:
                recalled = self.memory.recall("心情 情绪 开心 难过")
                if recalled:
                    # 不直接暴露记忆内容，但让 Nyx 知道有历史
                    pass
            except Exception:
                pass

        return msg

    def record_interaction(
        self, session_id: str, user_msg: str, emotion: str = "neutral"
    ):
        """记录一轮交互（别名 touch + 记忆回写）。"""
        self.touch(session_id, emotion)
        if self.memory:
            try:
                self.memory.remember(f"主人说：{user_msg}", tags="from-chat")
            except Exception:
                pass

    def get_session_info(self, session_id: str) -> dict:
        """返回某会话的关心状态（调试用）。"""
        s = self._sessions.get(session_id)
        if not s:
            return {"exists": False}
        return {
            "exists": True,
            "idle_seconds": round(time.time() - s["last_active"]),
            "last_emotion": s["last_emotion"],
            "greeted_periods": list(s["greeted_periods"]),
            "is_first": s.get("is_first", True),
        }
