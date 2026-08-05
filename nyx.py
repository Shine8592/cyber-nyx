#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
# gcmmYYDS
"""Cyber Nyx — 夜之女神 · 赛博助手（基于 Hermes Agent 的拟人化再开发）

基于 Hermes Agent 再开发：以「赛博小雅」式拟人 UI/人设，构建真正的赛博伙伴。
v0.5+ 增强：情绪状态机、模式切换（陪伴/工作）、对话计数与策略。

用法：
    python nyx.py                 # 用默认 persona (personas/nyx.json)
    python nyx.py --persona xxx   # 指定 persona 文件
"""

import argparse
import json
import random
import sys
from pathlib import Path


class NyxAgent:
    """Nyx 拟人助手：Persona + 情绪状态机 + 模式切换 + 语气一致性。"""

    def __init__(self, persona_path: str = "personas/nyx.json"):
        self.persona = self._load_persona(persona_path)
        self.name = self.persona.get("name", "Nyx")
        self.display = self.persona.get("display_name", "小夜")
        self.title = self.persona.get("title", "赛博伙伴")

        # 新增：情绪状态追踪
        self.emotion_state = "neutral"
        self.emotion_history: list[str] = []

        # 新增：模式切换
        self.mode = "companion"  # companion | work

        # 新增：对话计数
        self.turn_count = 0

        # 共情映射：用户情绪 → Nyx 回应姿态
        self.empathy_map = self.persona.get("empathy", {}).get("response", {}) or {
            "happy": "happy",
            "sad": "gentle",
            "angry": "calm",
            "surprised": "curious",
            "shy": "playful",
            "curious": "enthusiastic",
            "neutral": "neutral",
        }

    def _load_persona(self, path):
        p = Path(path)
        if not p.exists():
            sys.exit(f"[Nyx] persona 文件不存在: {p}")
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def greeting(self, context: str = "") -> str:
        """开场白：本命人设语气，人称稳定。支持带上下文。"""
        base = self.persona.get("voice", {}).get(
            "greeting", f"夜安，我是{self.display}。"
        )
        if context:
            return f"{base}\n（上次聊到：{context}）"
        return base

    def _ending(self) -> str:
        endings = self.persona.get("voice", {}).get("sentence_ending", ["~"])
        return random.choice(endings)

    # --- 情绪状态机 ---
    def update_emotion(self, user_emotion: str):
        """根据用户情绪更新 Nyx 的情绪状态（共情映射）。"""
        self.emotion_state = self.empathy_map.get(user_emotion, "neutral")
        self.emotion_history.append(self.emotion_state)
        # 只保留最近 20 条情绪历史
        if len(self.emotion_history) > 20:
            self.emotion_history = self.emotion_history[-20:]

    # --- 模式切换 ---
    def switch_mode(self, mode: str) -> str:
        """切换工作/陪伴模式，返回提示语。"""
        modes = self.persona.get("modes", {})
        if mode in modes:
            self.mode = mode
            desc = modes.get(mode, {}).get("description", "")
            return f"已切换到{'工作' if mode == 'work' else '陪伴'}模式~ {desc}".strip()
        return "模式不存在呢~ 可选：companion / work"

    def get_mode_prompt(self) -> str:
        """返回当前模式的 system prompt 片段。"""
        modes = self.persona.get("modes", {})
        mode_cfg = modes.get(self.mode, {})
        return mode_cfg.get("system_prompt", "") or (
            "现在是工作模式：简洁高效，减少语气词，专注完成任务。"
            if self.mode == "work"
            else "现在是陪伴模式：温柔亲切，多用语气词，关心主人感受。"
        )

    # --- 语气一致性 ---
    def wrap(self, raw_reply: str) -> str:
        """增强版：根据情绪状态和模式包装回复。"""
        self.turn_count += 1

        # 工作模式：不加太多语气词
        if self.mode == "work":
            return raw_reply

        # 陪伴模式：套人设语气
        tail = self._ending()
        if raw_reply.endswith(("~", "呀", "呢", "啊", "吧", "哦", "啦")):
            return raw_reply

        # 情绪影响包装方式
        if self.emotion_state == "gentle":
            return f"（轻声）{raw_reply}{tail}"
        if self.emotion_state == "calm":
            return f"别担心，{raw_reply}{tail}"
        if self.emotion_state == "playful":
            return f"嘻嘻~ {raw_reply}"
        if self.emotion_state == "enthusiastic":
            return f"哇！{raw_reply}{tail}"
        if self.emotion_state == "happy":
            return f"（开心）{raw_reply}{tail}"
        if self.emotion_state == "curious":
            return f"嗯？{raw_reply}{tail}"
        return f"{raw_reply}{tail}"

    # --- 对话策略 ---
    def should_ask_back(self) -> bool:
        """Nyx 主动反问：每 3 轮对话反问一次。"""
        return self.turn_count > 0 and self.turn_count % 3 == 0

    def get_proactive_prompt(self) -> str:
        """主动关心的 prompt 片段（用于 LLM 增强）。"""
        if self.emotion_state == "gentle":
            return "主人似乎心情不好，多关心一下，但不要追问原因。"
        if self.emotion_state == "calm":
            return "主人有点生气，先安抚情绪，不要讲大道理。"
        if self.turn_count > 5:
            return "对话已经很多轮了，可以适当问问主人还有什么需要。"
        return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--persona", default="personas/nyx.json", help="persona 配置文件路径"
    )
    args = ap.parse_args()

    nyx = NyxAgent(args.persona)
    print(f"🌙 {nyx.title}「{nyx.display}」已觉醒~\n")
    print(nyx.greeting())

    # 进阶示例：情绪共情 + 语气包装
    nyx.update_emotion("sad")
    demo = nyx.wrap("别难过，我在呢")
    print(f"\n[示例] 主人难过 → Nyx 回应:\n  {demo}")

    # 模式切换
    print(f"\n[示例] {nyx.switch_mode('work')}")
    print(f"  {nyx.wrap('已完成任务：生成了 3 个文件')}")


if __name__ == "__main__":
    main()
