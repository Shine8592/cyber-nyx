#!/usr/bin/env python3
"""Agent Core 抽象接口层（v0.2 核心）

cyber-nyx 与「具体 Agent 内核」解耦：
  - 本项目定义稳定的 AgentCore 接口规范
  - Hermes 作为底层实现（HermesAdapter）
  - 未来若 Hermes 升级/替换，只改 adapter，cyber-nyx 主体不动

用法（第三方内核便于接入）：
    from bridges.agent_core import AgentCore
    class MyAgent(AgentCore):
        def submit(self, task: str) -> str: ...
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolResult:
    """工具/任务执行结果。"""
    ok: bool                      # 是否成功
    output: str                   # 文本输出（人设润色前的原始结果）
    error: Optional[str] = None   # 失败时的错误描述
    took: float = 0.0             # 耗时（秒）
    meta: dict = field(default_factory=dict)  # 内核自定义元信息


class AgentCore(ABC):
    """Agent 内核统一接口。

    任何 Agent 内核（Hermes / 其他）只要实现这 4 个方法，
    即可无缝接入 cyber-nyx 拟人壳。

    稳定性契约：cyber-nyx 只依赖本接口，不依赖内核内部实现。
    """

    name: str = "generic"                     # 内核名

    @abstractmethod
    def submit(self, task: str, timeout: int = 120) -> ToolResult:
        """提交一个任务给内核执行，返回结果。

        task: 自然语言任务描述（如"列出当前目录文件"）
        实现方应给出普通文本输出（不含人设语气）。
        """

    @abstractmethod
    def task_style(self) -> str:
        """返回该内核偏好的『任务描述风格』提示，用于引导 LLM 把
        主人生成的自然语言转成该内核能执行的任务。"""

    def health(self) -> bool:
        """内核是否可用（可选覆盖，默认 False 表示未检测）。"""
        return False

    def list_tools(self):
        """内核暴露的能力清单（可选，默认为空）。"""
        return []


class NoCore(AgentCore):
    """兜底实现：未配置任何内核时（演示模式）。"""
    name = "none"

    def submit(self, task: str, timeout: int = 120) -> ToolResult:
        return ToolResult(
            ok=False,
            output="（未接入 Agent 内核，无法执行该任务）",
            error="no-core",
        )

    def task_style(self) -> str:
        return ""

    def health(self) -> bool:
        return False

    def list_tools(self):
        return ["none"]