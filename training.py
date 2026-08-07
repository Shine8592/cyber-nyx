# -*- coding: utf-8 -*-
"""环境检测 / 一键安装 / 一键训练（训练引擎：GPT-SoVITS v2）

下载通道（按顺序 fallback）：
  - 预训练权重: hf-mirror.com -> huggingface.co
  - GPT-SoVITS 源码: ghfast.top 代理 -> github 直连
  - PyPI: 清华镜像 -> 官方
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).resolve().parent
    RES_DIR = Path(sys._MEIPASS)
else:
    BASE = Path(__file__).resolve().parent
    RES_DIR = BASE
GSV = BASE / "GPT_SoVITS"
RUNTIME = BASE / "runtime"
VENV = RUNTIME / "venv"
VENV_PY = VENV / "Scripts" / "python.exe" if os.name == "nt" else VENV / "bin" / "python"
TRAIN_DATA = BASE / "train_data"
MODELS = TRAIN_DATA / "models"
LOGS = TRAIN_DATA / "logs"
FFMPEG_DIR = BASE / "tools" / "ffmpeg_bin"
FFMPEG_BIN = FFMPEG_DIR / "ffmpeg.exe" if os.name == "nt" else FFMPEG_DIR / "ffmpeg"


def _ensure_bundled() -> None:
    """frozen 模式下把打包的脚本/资源释放到 EXE 旁边的可写目录。"""
    if not getattr(sys, "frozen", False) or RES_DIR == BASE:
        return
    TRAIN_DATA.mkdir(parents=True, exist_ok=True)
    for rel in ("train_data/train_one.py",):
        src = RES_DIR / rel
        if not src.exists():
            continue
        dst = BASE / rel
        if not dst.exists() or src.stat().st_size != dst.stat().st_size:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


_ensure_bundled()

GSV_ZIP_SOURCES = [
    "https://ghfast.top/https://github.com/RVC-Boss/GPT-SoVITS/archive/refs/heads/main.zip",
    "https://github.com/RVC-Boss/GPT-SoVITS/archive/refs/heads/main.zip",
]
PIP_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"
TORCH_INDEX = "https://download.pytorch.org/whl/cu121"

WEIGHTS = [
    {
        "rel": "pretrained_models/gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt",
        "hf": "lj1995/GPT-SoVITS/resolve/main/gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt",
        "size": 155,
    },
    {
        "rel": "pretrained_models/gsv-v2final-pretrained/s2G2333k.pth",
        "hf": "lj1995/GPT-SoVITS/resolve/main/gsv-v2final-pretrained/s2G2333k.pth",
        "size": 85,
    },
    {
        "rel": "pretrained_models/gsv-v2final-pretrained/s2D2333k.pth",
        "hf": "lj1995/GPT-SoVITS/resolve/main/gsv-v2final-pretrained/s2D2333k.pth",
        "size": 85,
    },
    {
        "rel": "pretrained_models/chinese-roberta-wwm-ext-large/config.json",
        "hf": "lj1995/GPT-SoVITS/resolve/main/pretrained_models/chinese-roberta-wwm-ext-large/config.json",
        "size": 1,
    },
    {
        "rel": "pretrained_models/chinese-roberta-wwm-ext-large/pytorch_model.bin",
        "hf": "lj1995/GPT-SoVITS/resolve/main/pretrained_models/chinese-roberta-wwm-ext-large/pytorch_model.bin",
        "size": 650,
    },
    {
        "rel": "pretrained_models/chinese-roberta-wwm-ext-large/tokenizer.json",
        "hf": "lj1995/GPT-SoVITS/resolve/main/pretrained_models/chinese-roberta-wwm-ext-large/tokenizer.json",
        "size": 1,
    },
    {
        "rel": "pretrained_models/chinese-hubert-base/config.json",
        "hf": "lj1995/GPT-SoVITS/resolve/main/pretrained_models/chinese-hubert-base/config.json",
        "size": 1,
    },
    {
        "rel": "pretrained_models/chinese-hubert-base/preprocessor_config.json",
        "hf": "lj1995/GPT-SoVITS/resolve/main/pretrained_models/chinese-hubert-base/preprocessor_config.json",
        "size": 1,
    },
    {
        "rel": "pretrained_models/chinese-hubert-base/pytorch_model.bin",
        "hf": "lj1995/GPT-SoVITS/resolve/main/pretrained_models/chinese-hubert-base/pytorch_model.bin",
        "size": 180,
    },
    {
        "rel": "text/G2PWModel/g2pW.onnx",
        "hf": "lj1995/GPT-SoVITS/resolve/main/text/G2PWModel/g2pW.onnx",
        "size": 630,
    },
    {
        "rel": "pretrained_models/fast_langdetect/lid.176.bin",
        "hf": "lj1995/GPT-SoVITS/resolve/main/pretrained_models/fast_langdetect/lid.176.bin",
        "size": 120,
    },
]

FFMPEG_ZIP_SOURCES = [
    "https://ghfast.top/https://github.com/GyanD/codexffmpeg/releases/download/7.0.2/ffmpeg-7.0.2-essentials_build.zip",
    "https://github.com/GyanD/codexffmpeg/releases/download/7.0.2/ffmpeg-7.0.2-essentials_build.zip",
]

PY_INSTALLER_SOURCES = [
    "https://mirrors.huaweicloud.com/python/3.10.11/python-3.10.11-amd64.exe",
    "https://registry.npmmirror.com/-/binary/python/3.10.11/python-3.10.11-amd64.exe",
]
PY310_EXE = RUNTIME / "python310" / "python.exe"
_SYS_PY = {"cmd": "", "t": 0.0}
_DETECT_CACHE = {"t": 0.0, "d": None}


def _probe(exe_args, code):
    """在指定 python 上跑一段代码，返回 stdout；失败返回空串。"""
    try:
        r = subprocess.run(
            list(exe_args) + ["-c", code], capture_output=True, timeout=25, text=True,
            encoding="utf-8", errors="replace",
        )
        if r.returncode == 0:
            return (r.stdout or "").strip()
    except Exception:
        pass
    return ""


def _find_system_python():
    """找一个可用的系统 Python 3.10+（用于创建训练 venv），60s 缓存。"""
    t = time.time()
    if _SYS_PY["cmd"] and t - _SYS_PY["t"] < 60:
        return _SYS_PY["cmd"]
    _SYS_PY.update(t=t)
    for args in (["python"], ["py", "-3.12"], ["py", "-3.11"], ["py", "-3.10"]):
        ver = _probe(args, "import sys;print('%d.%d.%d' % sys.version_info[:3])")
        if ver:
            try:
                mj, mn = int(ver.split(".")[0]), int(ver.split(".")[1])
            except Exception:
                continue
            if (mj, mn) >= (3, 10):
                _SYS_PY["cmd"] = args[0]
                return args[0]
    return ""


def _ensure_embedded_python(store):
    """无系统 Python 3.10+ 时（frozen 场景），自动下载并静默安装内置 Python。"""
    if PY310_EXE.exists():
        return str(PY310_EXE)
    _log(store, "未找到 Python 3.10+，自动下载内置 Python 3.10.11（约 28MB）")
    installer = RUNTIME / "python-3.10.11-amd64.exe"
    if not _download(PY_INSTALLER_SOURCES, installer, store):
        raise RuntimeError("Python 下载失败（网络问题请重试）")
    _log(store, "静默安装 Python 3.10 ...")
    try:
        r = subprocess.run(
            [str(installer), "/quiet", "InstallAllUsers=0", "PrependPath=0",
             "Include_launcher=0", "Include_test=0", "Include_doc=0",
             "Include_debug=0", f"TargetDir={PY310_EXE.parent}"],
            timeout=900,
        )
    except Exception as e:
        raise RuntimeError(f"Python 安装异常: {e}")
    installer.unlink(missing_ok=True)
    if r.returncode != 0 or not PY310_EXE.exists():
        raise RuntimeError("Python 静默安装失败，请手动安装 Python 3.10+")
    return str(PY310_EXE)


def _training_base_py(store=None):
    """训练链 python 参数：已有 venv → 系统 Python 3.10+ → 自动安装内置（frozen）。
    返回命令行参数列表，找不到返回空列表。"""
    if VENV_PY.exists():
        return [str(VENV_PY)]
    sys_py = _find_system_python()
    if sys_py:
        return [sys_py]
    if getattr(sys, "frozen", False) and store is not None:
        return [_ensure_embedded_python(store)]
    return []

SETUP_STATE = {
    "running": False,
    "phase": "",
    "progress": 0.0,
    "log": [],
    "ok": False,
    "error": "",
}
TRAIN_STATE = {
    "running": False,
    "stage": "",
    "progress": 0.0,
    "log": [],
    "name": "",
    "ok": False,
    "error": "",
    "model_dir": "",
}
_LOCK = threading.Lock()


def _log(store, msg):
    with _LOCK:
        store["log"].append("[%s] %s" % (time.strftime("%H:%M:%S"), msg))
        if len(store["log"]) > 500:
            store["log"] = store["log"][-500:]


def _run(cmd, store, cwd=None, env=None, timeout=None):
    _log(store, "> " + " ".join(str(c) for c in cmd))
    e = dict(os.environ)
    e.setdefault("PYTHONIOENCODING", "utf-8")
    e.setdefault("TRAIN_VERBOSE", "1")
    if env:
        e.update(env)
    p = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, env=e,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    for line in iter(p.stdout.readline, b""):
        try:
            text = line.decode("utf-8", "replace").rstrip()
        except Exception:
            text = ""
        if text:
            _log(store, text)
    code = p.wait(timeout=timeout)
    return code


def _download(urls, dest, store, expected_mb=0):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    last_err = None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                got = 0
                t0 = time.time()
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    if total and time.time() - t0 > 0.5:
                        t0 = time.time()
                        SETUP_STATE["progress"] = (got / total) * 100 if total else 0
            if total and got < total:
                raise RuntimeError(f"下载不完整 {got}/{total}")
            os.replace(tmp, dest)
            _log(store, f"下载完成 {dest.name} ({got // 1048576}MB)")
            return True
        except Exception as e:
            last_err = e
            _log(store, f"通道失败 {url.split('/')[2]}: {type(e).__name__}")
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
    _log(store, f"下载失败: {dest.name} ({last_err})")
    return False


def _weights_missing():
    miss = []
    for w in WEIGHTS:
        f = GSV / w["rel"]
        if not f.exists():
            miss.append(w)
        elif w["size"] >= 10 and f.stat().st_size < w["size"] * 1000 * 900:
            miss.append(w)
    return miss


def detect_env():
    t = time.time()
    cached = _DETECT_CACHE["d"]
    if cached and t - _DETECT_CACHE["t"] < 30:
        return cached
    try:
        import edge_tts  # noqa

        edge = True
    except Exception:
        edge = False
    base = _training_base_py()
    if base:
        py_ver = _probe(base, "import sys;print('%d.%d.%d' % sys.version_info[:3])")
        torch_v = _probe(base, "import torch;print(torch.__version__)")
        cuda_gpu = _probe(base, "import torch\n"
                                "if torch.cuda.is_available():print(torch.cuda.get_device_name(0))\n"
                                "else:print('')")
    else:
        py_ver, torch_v, cuda_gpu = "", "", ""
    d = {
        "python": py_ver,
        "python_ok": _ver_ge(py_ver, (3, 10)),
        "runtime": "runtime/venv" if VENV_PY.exists() else (
            "系统 Python" if _find_system_python() else ("内置 Python" if PY310_EXE.exists() else "未就绪")),
        "edge_tts": edge,
        "torch": torch_v,
        "cuda": bool(cuda_gpu),
        "gpu": cuda_gpu,
    }
    d["gsv"] = (GSV / "text" / "chinese.py").exists()
    d["ffmpeg"] = FFMPEG_BIN.exists() or shutil.which("ffmpeg") is not None
    miss = _weights_missing()
    d["weights_missing"] = [w["rel"].split("/")[-1] for w in miss]
    d["weights_ok"] = not miss
    d["models"] = []
    if MODELS.is_dir():
        for m in sorted(MODELS.iterdir()):
            if m.is_dir() and (m / "s2G.pth").exists():
                d["models"].append(m.name)
    d["ready"] = (
        d["python_ok"] and d["edge_tts"] and d["torch"] and d["gsv"] and d["ffmpeg"] and d["weights_ok"]
    )
    _DETECT_CACHE.update(t=t, d=d)
    return d


def _ver_ge(ver, target):
    try:
        parts = [int(x) for x in ver.split(".")[:2]]
        return len(parts) == 2 and tuple(parts) >= target
    except Exception:
        return False


def setup_start():
    if SETUP_STATE["running"]:
        return {"ok": False, "error": "安装已在进行中"}
    SETUP_STATE.update(running=True, phase="启动", progress=0.0, log=[], ok=False, error="")
    threading.Thread(target=_setup_worker, daemon=True).start()
    return {"ok": True}


def _setup_worker():
    try:
        _log(SETUP_STATE, "=== 一键安装开始 ===")
        RUNTIME.mkdir(parents=True, exist_ok=True)
        TRAIN_DATA.mkdir(parents=True, exist_ok=True)

        SETUP_STATE["phase"] = "准备 Python 环境"
        base_py = _training_base_py(SETUP_STATE)
        if not base_py:
            raise RuntimeError("未找到 Python 3.10+，请先安装 Python 3.10 及以上版本")
        if not VENV_PY.exists():
            _log(SETUP_STATE, f"使用 {base_py[0]} 创建训练虚拟环境")
            _run(base_py + ["-m", "venv", str(VENV)], SETUP_STATE)
        SETUP_STATE["phase"] = "安装基础依赖 (edge-tts)"
        _run([str(VENV_PY), "-m", "pip", "install", "--quiet", "--index-url", PIP_INDEX, "edge-tts"],
             SETUP_STATE)

        SETUP_STATE["phase"] = "安装 PyTorch"
        import subprocess as sp

        has_gpu = False
        try:
            r = sp.run(["nvidia-smi"], capture_output=True, timeout=10)
            has_gpu = r.returncode == 0
        except Exception:
            has_gpu = False
        if has_gpu:
            _log(SETUP_STATE, "检测到 NVIDIA GPU，安装 CUDA 版 PyTorch")
            _run([str(VENV_PY), "-m", "pip", "install", "--quiet",
                  "--index-url", TORCH_INDEX, "torch", "torchaudio"], SETUP_STATE)
        else:
            _log(SETUP_STATE, "未检测到 GPU，安装 CPU 版 PyTorch")
            _run([str(VENV_PY), "-m", "pip", "install", "--quiet",
                  "--index-url", PIP_INDEX, "torch", "torchaudio"], SETUP_STATE)

        SETUP_STATE["phase"] = "下载 GPT-SoVITS 引擎"
        if not d_gsv_code_present():
            zip_path = RUNTIME / "gptsovits.zip"
            if not _download(GSV_ZIP_SOURCES, zip_path, SETUP_STATE, expected_mb=300):
                raise RuntimeError("GPT-SoVITS 源码下载失败（网络问题请重试）")
            import zipfile

            with zipfile.ZipFile(zip_path) as z:
                z.extractall(RUNTIME / "_gsv_tmp")
            src = RUNTIME / "_gsv_tmp" / "GPT-SoVITS-main"
            if (src / "GPT_SoVITS").exists():
                shutil.copytree(src / "GPT_SoVITS", GSV, dirs_exist_ok=True)
                shutil.copytree(src / "tools", BASE / "tools", dirs_exist_ok=True)
                shutil.copy2(src / "requirements.txt", BASE / "requirements.txt")
            shutil.rmtree(RUNTIME / "_gsv_tmp", ignore_errors=True)
            zip_path.unlink(missing_ok=True)
            _log(SETUP_STATE, "GPT-SoVITS 代码就绪")

        SETUP_STATE["phase"] = "下载预训练模型"
        miss = _weights_missing()
        for i, w in enumerate(miss):
            _log(SETUP_STATE, f"权重 [{i + 1}/{len(miss)}] {w['rel'].split('/')[-1]}")
            dest = GSV / w["rel"]
            ok = _download(
                ["https://hf-mirror.com/" + w["hf"], "https://huggingface.co/" + w["hf"]],
                dest, SETUP_STATE,
            )
            if not ok:
                raise RuntimeError(f"权重下载失败: {w['rel']}")
        SETUP_STATE["progress"] = 100

        SETUP_STATE["phase"] = "安装 GPT-SoVITS 依赖"
        _run([str(VENV_PY), "-m", "pip", "install", "--quiet", "--index-url", PIP_INDEX,
              "-r", str(GSV / "requirements.txt")], SETUP_STATE)

        SETUP_STATE["phase"] = "配置 ffmpeg"
        if not FFMPEG_BIN.exists() and not shutil.which("ffmpeg"):
            zip_path = RUNTIME / "ffmpeg.zip"
            if _download(FFMPEG_ZIP_SOURCES, zip_path, SETUP_STATE):
                import zipfile

                with zipfile.ZipFile(zip_path) as z:
                    z.extractall(RUNTIME / "_ffmpeg_tmp")
                inner = next((p for p in (RUNTIME / "_ffmpeg_tmp").iterdir() if p.is_dir()), None)
                if inner:
                    shutil.copytree(inner / "bin", FFMPEG_DIR, dirs_exist_ok=True)
                shutil.rmtree(RUNTIME / "_ffmpeg_tmp", ignore_errors=True)
                zip_path.unlink(missing_ok=True)

        SETUP_STATE.update(phase="完成", progress=100, ok=True)
        _log(SETUP_STATE, "=== 环境安装完成，可以开始训练 ===")
    except Exception as e:
        SETUP_STATE.update(error=str(e), ok=False)
        _log(SETUP_STATE, f"安装失败: {e}")
    finally:
        SETUP_STATE["running"] = False


def d_gsv_code_present():
    return (GSV / "text" / "chinese.py").exists()


def train_start(name, audio_path, s1_epochs=20, s2_epochs=60):
    if TRAIN_STATE["running"]:
        return {"ok": False, "error": "训练已在进行中"}
    if SETUP_STATE["running"]:
        return {"ok": False, "error": "环境安装中，请先等待完成"}
    safe = "".join(c for c in name if c.isalnum() or c in "-_") or "voice"
    TRAIN_STATE.update(
        running=True, stage="启动", progress=0.0, log=[], name=safe, ok=False, error="", model_dir=""
    )
    threading.Thread(target=_train_worker, args=(safe, audio_path, s1_epochs, s2_epochs),
                     daemon=True).start()
    return {"ok": True}


def _train_worker(name, audio_path, s1_epochs, s2_epochs):
    try:
        _log(TRAIN_STATE, f"=== 开始训练: {name} ===")
        script = TRAIN_DATA / "train_one.py"
        if not script.exists():
            raise RuntimeError("缺少 train_data/train_one.py，请重新安装")
        base = _training_base_py()
        if not base:
            raise RuntimeError("未找到 Python 3.10+，请先在「声音克隆」中一键安装环境")
        venv_py = VENV_PY if VENV_PY.exists() else None
        cmd = [str(venv_py if venv_py else base[0]), str(script), "--name", name,
               "--audio", str(audio_path),
               "--s1-epochs", str(s1_epochs), "--s2-epochs", str(s2_epochs)]
        code = _run(cmd, TRAIN_STATE, cwd=str(BASE))
        if code != 0:
            raise RuntimeError(f"训练进程退出码 {code}，见日志")
        model_dir = None
        if MODELS.is_dir():
            for m in sorted(MODELS.iterdir(), reverse=True):
                if m.is_dir() and (m / "s2G.pth").exists():
                    model_dir = str(m)
                    break
        TRAIN_STATE.update(stage="完成", progress=100, ok=True, model_dir=model_dir or "")
        _log(TRAIN_STATE, f"=== 训练完成: {model_dir or '未找到模型'} ===")
        register_clone_from_model(model_dir or "", name)
    except Exception as e:
        TRAIN_STATE.update(error=str(e), ok=False)
        _log(TRAIN_STATE, f"训练失败: {e}")
    finally:
        TRAIN_STATE["running"] = False


def register_clone_from_model(model_dir, name):
    try:
        from app import CLONE_DIR, CLONE_PROFILES, _scan_clone_profiles

        m = Path(model_dir)
        refs = list(m.glob("ref.*"))
        if not refs:
            return
        audio = refs[0]
        txt = m / "ref.txt"
        prompt = txt.read_text(encoding="utf-8").strip() if txt.exists() else ""
        safe = "".join(c for c in name if c.isalnum() or c in "-_") or "clone"
        dest = CLONE_DIR / f"{safe}{audio.suffix}"
        shutil.copy2(audio, dest)
        if prompt:
            (CLONE_DIR / f"{safe}.txt").write_text(prompt, encoding="utf-8")
        CLONE_PROFILES.pop(safe, None)
        CLONE_PROFILES[safe] = {"audio": str(dest), "prompt_text": prompt}
        _log(TRAIN_STATE, f"已注册克隆音色: {safe}")
    except Exception as e:
        _log(TRAIN_STATE, f"注册克隆音色失败: {e}")


def train_status():
    return dict(TRAIN_STATE)


def setup_status():
    return dict(SETUP_STATE)


