#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""内嵌记忆引擎「模型国内镜像自动降级」逻辑测试。

验证 memory_config.load_embedding_model() 的关键行为：
  ① 有本地缓存 → 直接离线加载，不去碰 HF_ENDPOINT（不联网）
  ② 无缓存 + 第一次加载失败 → 自动切 hf-mirror.com 重试
  ③ 结束后恢复原 HF_ENDPOINT，不污染全局环境
全程注入 fake，不触碰真实网络、不真实下载。
"""

import os
import sys
from pathlib import Path

import pytest

# 让 vendor 记忆引擎可导入
VENDOR = (
    Path(__file__).resolve().parent.parent
    / "vendor" / "universal-agent-memory" / "scripts"
)
sys.path.insert(0, str(VENDOR))

import memory_config
import sentence_transformers  # 模型在其模块内部被导入，patch 此模块级类

MIRROR = memory_config._MIRROR_ENDPOINT


class _FakeModel:
    """最小 fake，验证被返回即可。"""

    def __eq__(self, other):
        return isinstance(other, _FakeModel)


def test_cached_model_uses_local_path(monkeypatch):
    """① 本地缓存存在：直接用 SentenceTransformer(模型路径)，
    且不改动 HF_ENDPOINT（全程离线）。"""
    import types

    class FakePath:
        def __init__(self, p):
            self.p = p

        def exists(self):
            return True

        def mkdir(self, *a, **k):
            pass

        def __str__(self):
            return str(self.p)

    fake_path = FakePath("/tmp/fake/model")
    monkeypatch.setattr(memory_config, "MODEL_PATH", fake_path)

    seen = {}

    class _ST:
        def __init__(self, p):
            seen["path"] = str(p)
            seen["hf"] = os.environ.get("HF_ENDPOINT")

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", _ST)

    # 显式清空镜像环境变量，确保进入『未设置』分支
    os.environ.pop("HF_ENDPOINT", None)
    model = memory_config.load_embedding_model()

    assert str(seen["path"]) == "/tmp/fake/model"
    assert seen["hf"] is None  # 未设置镜像 → 缓存命中时不触发


def test_mirror_fallback_uses_mirror_and_restores(monkeypatch):
    """无缓存 + 一次加载失败 → 二次切镜像重试，且结束后恢复 HF_ENDPOINT。"""
    import pathlib
    fake_path = Path("/tmp/nonexistent-model")
    monkeypatch.setattr(memory_config, "MODEL_PATH", fake_path)
    monkeypatch.setattr(pathlib.Path, "exists", lambda self: self == fake_path and False)

    # 原环境无 HF_ENDPOINT
    os.environ.pop("HF_ENDPOINT", None)

    # 注入非线性判定：当 HF_ENDPOINT 是镜像时算成功（模拟镜像可用）
    calls = []

    def fake_st(endpoint):
        calls.append(os.environ.get("HF_ENDPOINT", "(none)"))
        if os.environ.get("HF_ENDPOINT", "") != MIRROR:
            raise ConnectionError("直连超时")
        return _FakeModel()

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", fake_st)

    model = memory_config.load_embedding_model()

    # 断言确实重试了两次：直连(none) → 镜像
    assert calls[0] == "(none)"
    assert calls[1] == MIRROR
    # 结束恢复：HF_ENDPOINT 恢复为原值（未设置）
    assert os.environ.get("HF_ENDPOINT", None) is None


def test_mirror_fallback_restores_user_endpoint(monkeypatch):
    """用户原设 HF_ENDPOINT 为镜像时：直连失败→镜像重试→恢复用户原值。"""
    import pathlib
    fake_path = Path("/tmp/nonexistent-model")
    monkeypatch.setattr(memory_config, "MODEL_PATH", fake_path)
    monkeypatch.setattr(pathlib.Path, "exists", lambda self: False)

    os.environ["HF_ENDPOINT"] = "https://my-mirror.example.com"

    calls = []

    def fake_st(endpoint):
        calls.append(os.environ.get("HF_ENDPOINT", "(none)"))
        # 无论直连还是我们临时镜像都让它失败，触发镜像重试到 hf-mirror
        if os.environ.get("HF_ENDPOINT", "") == "https://my-mirror.example.com":
            raise ConnectionError("用户镜像也失败")
        if os.environ.get("HF_ENDPOINT", "") == MIRROR:
            return _FakeModel()  # hf-mirror 成功
        raise ConnectionError("其它失败")

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", fake_st)

    model = memory_config.load_embedding_model()
    assert isinstance(model, _FakeModel)
    # 用户原镜像恢复
    assert os.environ.get("HF_ENDPOINT") == "https://my-mirror.example.com"
    os.environ.pop("HF_ENDPOINT", None)