"""Shared fixtures for cyber-nyx tests."""
import os
import sys
from pathlib import Path

import pytest

# Ensure the project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def clear_env():
    """Clear LLM-related env vars so tests always use demo mode."""
    for key in ["NYX_API_BASE", "NYX_API_KEY", "NYX_MODEL", "NYX_HERMES_BIN",
                "NYX_HERMES_MODEL", "NYX_STREAM", "NYX_RETRY_MAX", "NYX_RETRY_BASE",
                "NYX_MCP_SCRIPT", "MEMORY_STORE", "MEMORY_PROJECT_ROOT", "MEMORY_GLOBAL_DIR"]:
        os.environ.pop(key, None)
    yield
    for key in ["NYX_API_BASE", "NYX_API_KEY", "NYX_MODEL", "NYX_HERMES_BIN",
                "NYX_HERMES_MODEL", "NYX_STREAM", "NYX_RETRY_MAX", "NYX_RETRY_BASE",
                "NYX_MCP_SCRIPT", "MEMORY_STORE", "MEMORY_PROJECT_ROOT", "MEMORY_GLOBAL_DIR"]:
        os.environ.pop(key, None)