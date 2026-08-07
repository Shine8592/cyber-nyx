# -*- coding: utf-8 -*-
"""STT 本地语音识别模块（sherpa-onnx · zipformer-zh 14M 流式中文模型）

- 引擎：sherpa-onnx（CPU 离线推理，无 torch / GPU 依赖）
- 模型：sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23
        （下载约 70MB，解压后 int8 权重约 24MB，全本地运行）
- 安装：pip 清华源装引擎 + GitHub Release 直链下载模型 → runtime/stt/

用法：
    from stt import get_status, install_start, transcribe
"""
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import wave
from io import BytesIO
from pathlib import Path

MODEL_NAME = "sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23"
MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23.tar.bz2"
)
MODEL_FILES = (
    "encoder-epoch-99-avg-1.int8.onnx",
    "decoder-epoch-99-avg-1.int8.onnx",
    "joiner-epoch-99-avg-1.int8.onnx",
    "tokens.txt",
)
PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).resolve().parent
else:
    BASE = Path(__file__).resolve().parent

STT_DIR = BASE / "runtime" / "stt"
MODEL_DIR = STT_DIR / MODEL_NAME

STATE = {"running": False, "phase": "", "log": [], "ok": False, "error": ""}
_LOCK = threading.Lock()
_REC = None
_REC_LOCK = threading.Lock()


def _log(msg):
    with _LOCK:
        STATE["log"].append("[%s] %s" % (time.strftime("%H:%M:%S"), msg))
        if len(STATE["log"]) > 200:
            STATE["log"] = STATE["log"][-200:]


def get_status() -> dict:
    """模型 + 引擎就绪状态（含安装进度）。"""
    model_ok = all((MODEL_DIR / f).exists() for f in MODEL_FILES)
    try:
        import sherpa_onnx  # noqa

        engine = sherpa_onnx.__version__
        engine_ok = True
    except Exception:
        engine, engine_ok = "", False
    return {
        "installed": model_ok and engine_ok,
        "model": model_ok,
        "engine": engine_ok,
        "engine_version": engine,
        "model_dir": str(MODEL_DIR) if model_ok else "",
        "running": STATE["running"],
        "phase": STATE["phase"],
        "log": STATE["log"],
        "ok": STATE["ok"],
        "error": STATE["error"],
    }


def install_start() -> dict:
    """后台线程启动一键安装。"""
    if STATE["running"]:
        return {"ok": True, "running": True}
    STATE["running"] = True
    STATE["ok"] = False
    STATE["error"] = ""
    STATE["log"] = []
    threading.Thread(target=_install_worker, daemon=True).start()
    return {"ok": True, "running": True}


def _install_worker():
    try:
        STT_DIR.mkdir(parents=True, exist_ok=True)
        _log("步骤 1/3：安装 sherpa-onnx 引擎（清华源）…")
        STATE["phase"] = "安装 sherpa-onnx 引擎…"
        p = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "sherpa-onnx",
             "-i", PIP_MIRROR],
            capture_output=True, text=True,
        )
        if p.returncode != 0:
            p = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "sherpa-onnx"],
                capture_output=True, text=True,
            )
        if p.returncode != 0:
            raise RuntimeError("pip 安装失败：%s" % (p.stderr[-400:] if p.stderr else "未知"))
        import sherpa_onnx  # noqa

        _log("sherpa-onnx %s 安装完成" % sherpa_onnx.__version__)

        if not MODEL_DIR.exists():
            _log("步骤 2/3：下载语音识别模型（约 70MB）…")
            tarball = STT_DIR / (MODEL_NAME + ".tar.bz2")
            urllib.request.urlretrieve(MODEL_URL, str(tarball), _dl_reporter)
            _log("下载完成，步骤 3/3：解压模型…")
            STATE["phase"] = "解压模型…"
            with tarfile.open(str(tarball), "r:bz2") as tf:
                tf.extractall(str(STT_DIR))
            tarball.unlink(missing_ok=True)
        if not all((MODEL_DIR / f).exists() for f in MODEL_FILES):
            raise RuntimeError("模型文件不完整")
        _log("语音识别模型就绪（zipformer-zh 14M，int8）")
        STATE["ok"] = True
    except Exception as e:
        STATE["error"] = str(e)
        _log("安装失败：%s" % e)
    finally:
        STATE["running"] = False
        STATE["phase"] = ""


def _dl_reporter(block_num, block_size, total):
    if total > 0:
        pct = min(99, int(block_num * block_size * 100 / total))
        STATE["phase"] = "下载语音识别模型 %d%%" % pct
        if pct % 5 == 0:
            _log("下载语音识别模型 %d%%" % pct)


def _get_recognizer():
    """懒加载全局识别器（只加载一次，多请求复用）。"""
    global _REC
    if _REC is None:
        with _REC_LOCK:
            if _REC is None:
                import sherpa_onnx

                _REC = sherpa_onnx.OnlineRecognizer.from_transducer(
                    tokens=str(MODEL_DIR / "tokens.txt"),
                    encoder=str(MODEL_DIR / "encoder-epoch-99-avg-1.int8.onnx"),
                    decoder=str(MODEL_DIR / "decoder-epoch-99-avg-1.int8.onnx"),
                    joiner=str(MODEL_DIR / "joiner-epoch-99-avg-1.int8.onnx"),
                    num_threads=2, sample_rate=16000, feature_dim=80,
                    enable_endpoint_detection=False,
                )
    return _REC


def transcribe(data: bytes) -> str:
    """识别 16kHz 单声道 WAV 字节流 → 文本。"""
    if not data:
        return ""
    with wave.open(BytesIO(data), "rb") as wf:
        if wf.getframerate() != 16000:
            raise ValueError("音频需为 16kHz 采样率（当前 %dHz）" % wf.getframerate())
        if wf.getnchannels() != 1:
            raise ValueError("音频需为单声道")
        import numpy as np

        samples = np.frombuffer(wf.readframes(-1), dtype=np.int16)
    if len(samples) == 0:
        return ""
    rec = _get_recognizer()
    stream = rec.create_stream()
    stream.accept_waveform(16000, samples)
    stream.accept_waveform(16000, np.zeros(1600, dtype=np.int16))
    while rec.is_ready(stream):
        rec.decode_stream(stream)
    return rec.get_result(stream)
