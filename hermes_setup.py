# -*- coding: utf-8 -*-
"""HERMES Agent 自动部署模块

检测本机 hermes CLI：
  - 已安装 → 直接桥接（HermesCore 套壳）
  - 未安装 → 自动下载官方 install.ps1 并静默部署
    （官方安装器自动处理 uv / Python 3.11 / Node 22 / ripgrep / ffmpeg / PortableGit，
      安装到 %LOCALAPPDATA%\\hermes\\hermes-agent）

部署完成后：
  - 把 hermes 绝对路径写入 config.json 的 hermes.bin
  - 软件立即以 Hermes 为内核运行（"套上咱们的衣服"）
"""
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import settings as app_settings

HERMES_STATE = {
    "running": False,
    "phase": "",
    "log": [],
    "ok": False,
    "error": "",
    "version": "",
}
_LOCK = threading.Lock()


def _log(msg):
    with _LOCK:
        HERMES_STATE["log"].append("[%s] %s" % (time.strftime("%H:%M:%S"), msg))
        if len(HERMES_STATE["log"]) > 400:
            HERMES_STATE["log"] = HERMES_STATE["log"][-400:]


def _candidates() -> list:
    """按优先级返回可能的 hermes 可执行文件路径。"""
    cands = []
    cfg = app_settings.load().get("hermes", {})
    if cfg.get("bin"):
        cands.append(cfg["bin"])
    if os.environ.get("NYX_HERMES_BIN"):
        cands.append(os.environ["NYX_HERMES_BIN"])
    w = shutil.which("hermes")
    if w:
        cands.append(w)
    if os.name == "nt":
        roots = [
            Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "hermes",
            Path("D:/hermes"),
            Path("E:/hermes"),
        ]
        for base in roots:
            if not base.exists():
                continue
            venv_scripts = base / "hermes-agent" / "venv" / "Scripts"
            cands.append(str(venv_scripts / "hermes.exe"))
            cands.append(str(venv_scripts / "hermes.cmd"))
        cands.append(str(Path.home() / ".local" / "bin" / "hermes.exe"))
        cands.append(str(Path.home() / ".local" / "bin" / "hermes"))
    else:
        cands.append("/usr/local/lib/hermes-agent/venv/bin/hermes")
        cands.append(str(Path.home() / ".local" / "bin" / "hermes"))
    return cands


def _version(bin_path: str) -> str:
    try:
        if os.name == "nt" and bin_path.lower().endswith((".cmd", ".bat")):
            args = ["cmd", "/c", bin_path, "--version"]
        else:
            args = [bin_path, "--version"]
        r = subprocess.run(
            args, capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
        )
        if r.returncode == 0:
            return (r.stdout or r.stderr or "").strip().splitlines()[0][:80]
    except Exception:
        pass
    return ""


def find_hermes_bin() -> str:
    """返回可用的 hermes 路径，找不到返回空串。"""
    for c in _candidates():
        if not c:
            continue
        if os.path.isfile(c) and _version(c):
            return c
    return ""


def hermes_status() -> dict:
    bin_path = find_hermes_bin()
    ver = _version(bin_path) if bin_path else ""
    return {
        "installed": bool(bin_path),
        "ok": bool(bin_path),
        "bin": bin_path,
        "version": ver,
    }


def deploy_hermes() -> dict:
    if HERMES_STATE["running"]:
        return {"ok": False, "error": "部署已在进行中"}
    if find_hermes_bin():
        return {"ok": False, "error": "本机已安装 Hermes，无需部署"}
    HERMES_STATE.update(running=True, phase="启动", log=[], ok=False, error="", version="")
    threading.Thread(target=_deploy_worker, daemon=True).start()
    return {"ok": True}


def deploy_status() -> dict:
    return dict(HERMES_STATE)


def _download(urls, dest, expected_mb=0):
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    last_err = None
    for url in urls:
        try:
            _log(f"下载 {url.split('/')[2]} ...")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                got = 0
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
            if total and got < total:
                raise RuntimeError(f"下载不完整 {got}/{total}")
            os.replace(tmp, dest)
            _log(f"下载完成 {dest.name} ({got // 1048576}MB)")
            return True
        except Exception as e:
            last_err = e
            _log(f"通道失败 {url.split('/')[2]}: {type(e).__name__}")
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
    _log(f"下载失败: {dest.name} ({last_err})")
    return False


def _deploy_worker():
    try:
        _log("=== HERMES 自动部署开始 ===")
        ps1 = Path(app_settings.CONFIG_PATH).parent / "runtime" / "hermes-install.ps1"
        ps1.parent.mkdir(parents=True, exist_ok=True)
        HERMES_STATE["phase"] = "下载官方安装脚本"
        ok = _download(
            [
                "https://hermes-agent.nousresearch.com/install.ps1",
                "https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1",
            ],
            ps1,
        )
        if not ok:
            raise RuntimeError("官方安装脚本下载失败（网络问题请重试）")

        HERMES_STATE["phase"] = "执行官方安装器（首次约 5~20 分钟）"
        env = dict(os.environ)
        # 安装位置优先 D 盘（用户要求），D 盘不存在回退官方默认
        home = r"D:\hermes"
        if not os.path.isdir(home[:2] + "\\"):
            home = str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "hermes")
        env["HERMES_HOME"] = home
        cache_root = Path(home) / ".caches"
        env["UV_CACHE_DIR"] = str(cache_root / "uv-cache")
        env["UV_PYTHON_INSTALL_DIR"] = str(cache_root / "uv-python")
        env["npm_config_cache"] = str(cache_root / "npm")
        edge = None
        for p in [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]:
            if os.path.isfile(p):
                edge = p
                break
        if edge:
            env["AGENT_BROWSER_EXECUTABLE_PATH"] = edge
            _log(f"复用系统浏览器 {edge}，跳过 Chromium 下载")
        else:
            env.pop("AGENT_BROWSER_EXECUTABLE_PATH", None)
        env["npm_config_registry"] = "https://registry.npmmirror.com"
        _log(f"安装位置: {home}")
        ps_cmd = [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(ps1), "-NonInteractive", "-HermesHome", home,
        ]
        _log("> " + " ".join(ps_cmd))
        proc = subprocess.Popen(
            ps_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
            env=env,
        )
        lines = []
        for line in proc.stdout:
            s = line.strip()
            if s:
                lines.append(s)
                _log(s)
                if len(lines) > 600:
                    break
        try:
            proc.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            proc.kill()
            _log("安装器超时（30 分钟）")

        HERMES_STATE["phase"] = "验证安装结果"
        bin_path = find_hermes_bin()
        if bin_path:
            ver = _version(bin_path)
            cfg = app_settings.load()
            cfg.setdefault("hermes", {})["bin"] = bin_path
            app_settings.save(cfg)
            os.environ["NYX_HERMES_BIN"] = bin_path
            HERMES_STATE.update(phase="完成", ok=True, version=ver)
            _log(f"=== Hermes 部署完成: {ver} ===")
            _log(f"路径: {bin_path}")
            _log("提示：新安装的 Hermes 需配置模型。请运行 hermes setup 或在")
            _log("设置页填写 LLM API 后，Hermes 内核即生效。")
        else:
            raise RuntimeError("安装完成但未找到 hermes 可执行文件，请重试")
    except Exception as e:
        HERMES_STATE.update(error=str(e), ok=False)
        _log(f"部署失败: {e}")
    finally:
        HERMES_STATE["running"] = False
