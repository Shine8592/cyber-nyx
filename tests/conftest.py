"""Shared fixtures for cyber-nyx tests."""

import os
import sys
from pathlib import Path

import pytest

# Ensure the project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 必须在 import app 之前设置：app.py 在 import 时读取鉴权开关并可能生成 token
os.environ["NYX_AUTH_DISABLE"] = "1"
# 测试环境关闭限流（测试客户端同一 IP 会频繁打接口）
os.environ["NYX_RATE_LIMIT_DISABLE"] = "1"


@pytest.fixture(autouse=True)
def clear_env():
    """Clear LLM-related env vars so tests always use demo mode."""
    for key in [
        "NYX_API_BASE",
        "NYX_API_KEY",
        "NYX_MODEL",
        "NYX_HERMES_BIN",
        "NYX_HERMES_MODEL",
        "NYX_STREAM",
        "NYX_RETRY_MAX",
        "NYX_RETRY_BASE",
        "NYX_MCP_SCRIPT",
        "MEMORY_STORE",
        "MEMORY_PROJECT_ROOT",
        "MEMORY_GLOBAL_DIR",
        "NYX_AUTH_TOKEN",
    ]:
        os.environ.pop(key, None)
    os.environ["NYX_AUTH_DISABLE"] = "1"  # 测试环境关闭鉴权
    yield
    for key in [
        "NYX_API_BASE",
        "NYX_API_KEY",
        "NYX_MODEL",
        "NYX_HERMES_BIN",
        "NYX_HERMES_MODEL",
        "NYX_STREAM",
        "NYX_RETRY_MAX",
        "NYX_RETRY_BASE",
        "NYX_MCP_SCRIPT",
        "MEMORY_STORE",
        "MEMORY_PROJECT_ROOT",
        "MEMORY_GLOBAL_DIR",
        "NYX_AUTH_TOKEN",
        "NYX_AUTH_DISABLE",
    ]:
        os.environ.pop(key, None)
