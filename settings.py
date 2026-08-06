#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""Cyber Nyx 配置中心 — config.json 持久化 + 环境变量热更新

优先级：环境变量 > config.json > 默认值
设置界面保存 → 写 config.json → 更新 os.environ（立即生效，无需重启）

支持区块：
    llm     OpenAI 兼容 API（base / key / model）
    hermes  Hermes 内核（bin / model / provider）
"""

import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

DEFAULTS = {
    "llm": {"base": "", "key": "", "model": "gpt-4o-mini"},
    "hermes": {"bin": "", "model": "", "provider": ""},
    "auth": {"token": ""},
}

ENV_MAP = {
    ("llm", "base"): "NYX_API_BASE",
    ("llm", "key"): "NYX_API_KEY",
    ("llm", "model"): "NYX_MODEL",
    ("hermes", "bin"): "NYX_HERMES_BIN",
    ("hermes", "model"): "NYX_HERMES_MODEL",
    ("hermes", "provider"): "NYX_HERMES_PROVIDER",
    ("auth", "token"): "NYX_AUTH_TOKEN",
}


def load() -> dict:
    """读取 config.json（不存在则返回默认）。"""
    cfg = json.loads(json.dumps(DEFAULTS))
    try:
        if CONFIG_PATH.exists():
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            for section, fields in saved.items():
                if isinstance(fields, dict):
                    cfg.setdefault(section, {}).update(fields)
    except Exception:
        pass
    return cfg


def save(cfg: dict) -> None:
    """写 config.json（合并默认值，缺字段补齐）。"""
    merged = json.loads(json.dumps(DEFAULTS))
    for section, fields in cfg.items():
        if isinstance(fields, dict):
            merged.setdefault(section, {}).update(fields)
    CONFIG_PATH.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_to_env() -> None:
    """启动时把 config.json 值灌入环境变量（已有环境变量优先，不覆盖）。"""
    cfg = load()
    for (section, field), env in ENV_MAP.items():
        if os.environ.get(env):
            continue
        val = cfg.get(section, {}).get(field, "")
        if val:
            os.environ[env] = str(val)


def apply_to_env(cfg: dict) -> None:
    """保存后调用：更新 os.environ，使配置立即生效。"""
    for (section, field), env in ENV_MAP.items():
        val = (cfg.get(section) or {}).get(field, "")
        if val:
            os.environ[env] = str(val)
        else:
            os.environ.pop(env, None)


def mask_key(key: str) -> str:
    """API Key 脱敏：sk-abc...xyz，只露出首尾。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:6] + "..." + key[-4:]
