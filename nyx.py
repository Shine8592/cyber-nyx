#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""Cyber Nyx — 夜之女神 · 赛博助手（Hermes 拟人壳层入口）

把「赛博小雅」式拟人 UI/人设，套在 Hermes Agent 之上。
当前为骨架版：加载 persona → 构造带人设的对话/调用层。

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
    """Nyx 拟人助手：Persona + 语气一致性 + 记忆占位。"""

    def __init__(self, persona_path: str = "personas/nyx.json"):
        self.persona = self._load_persona(persona_path)
        self.name = self.persona.get("name", "Nyx")
        self.display = self.persona.get("display_name", "小夜")
        self.title = self.persona.get("title", "赛博伙伴")

    def _load_persona(self, path):
        p = Path(path)
        if not p.exists():
            sys.exit(f"[Nyx] persona 文件不存在: {p}")
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def greeting(self):
        """开场白：本命人设语气，人称稳定。"""
        return self.persona.get("voice", {}).get(
            "greeting", f"夜安，我是{self.display}。"
        )

    def _ending(self) -> str:
        endings = self.persona.get("voice", {}).get("sentence_ending", ["~"])
        return random.choice(endings)

    def wrap(self, raw_reply: str) -> str:
        """给 Hermes 内核的原始回复套上人设语气（骨架演示）。"""
        tail = self._ending()
        # 避免重复句尾：若已含 ~ 则不追加
        if raw_reply.endswith("~"):
            return raw_reply
        return f"{raw_reply}{tail}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--persona", default="personas/nyx.json", help="persona 配置文件路径")
    args = ap.parse_args()

    nyx = NyxAgent(args.persona)
    print(f"🌙 {nyx.title}「{nyx.display}」已觉醒~\n")
    print(nyx.greeting())

    # 进阶示例：wrapper
    demo = nyx.wrap("我已经帮你查好了明天的天气：多云转晴，适合出行")
    print(f"\n[示例] Hermes 内核 ← 拟人润色:\n  {demo}")


if __name__ == "__main__":
    main()