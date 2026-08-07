#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""Hermes Adapter — 用 Hermes CLI 作为 cyber-nyx 的 Agent 内核实现。

符合 bridges/agent_core.py 的 AgentCore 接口。
通过 `hermes -z` 一次性非交互模式调用 Hermes 执行任务。

Hermes 升级 → 只改这个 adapter 的调用细节，cyber-nyx 主体不动。
"""

import os
import shutil
import subprocess
import sys

from bridges.agent_core import AgentCore, ToolResult


class HermesCore(AgentCore):
    name = "hermes"

    def __init__(self, model: str = "", provider: str = ""):
        # 优先显式配置，其次 PATH，最后已知安装路径
        self.bin = os.environ.get("NYX_HERMES_BIN", "")
        if not self.bin:
            self.bin = (
                shutil.which("hermes") or "/usr/local/lib/hermes-agent/venv/bin/hermes"
            )
        self.model = model or os.environ.get("NYX_HERMES_MODEL", "")
        self.provider = provider or os.environ.get("NYX_HERMES_PROVIDER", "")

    def _args(self, extra):
        if sys.platform == "win32" and self.bin.lower().endswith((".cmd", ".bat")):
            return ["cmd", "/c", self.bin, *extra]
        return [self.bin, *extra]

    def task_style(self) -> str:
        return (
            "主人会给出自然语言请求。请把它表述成一个 Hermes 能执行的、"
            "明确的单一任务指令（一句话，含明确目标），不要加语气。"
        )

    def submit(
        self, task: str, timeout: int = 120, persona_inject: str = ""
    ) -> ToolResult:
        import time

        t0 = time.time()
        # 人设注入：让 Hermes 内核以 Nyx 的身份和语气执行
        prompt = task
        if persona_inject:
            prompt = f"{persona_inject}\n任务：{task}"
        cmd = self._args(["-z", prompt])
        if self.model:
            cmd += ["-m", self.model]
        if self.provider:
            cmd += ["--provider", self.provider]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.environ.get("NYX_HERMES_CWD"),
            )
            took = time.time() - t0
            if proc.returncode == 0 and proc.stdout.strip():
                return ToolResult(ok=True, output=proc.stdout.strip(), took=took)
            # Hermes 可能把结果输出到 stderr 或空
            return ToolResult(
                ok=False,
                output=proc.stdout.strip() or proc.stderr.strip() or "(Hermes 无输出)",
                error=f"exit={proc.returncode}",
                took=took,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                ok=False, output="", error=f"Hermes 超时({timeout}s)", took=timeout
            )
        except FileNotFoundError:
            return ToolResult(
                ok=False, output="", error="找不到 hermes 命令，请确认已安装"
            )

    def health(self) -> bool:
        try:
            r = subprocess.run(
                self._args(["--version"]), capture_output=True, text=True, timeout=10
            )
            return r.returncode == 0
        except Exception:
            return False

    def list_tools(self):
        return ["terminal", "file", "web", "memory", "skills", "cron"]
