#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""missqiu.icu API 集成 — 百度绘图 / 图片识别（走国内代理）

源站对海外 IP 回源被拦（TencentEdgeOne 520），需要国内 HTTP 代理。
代理列表可在设置面板配置（逗号分隔），自动探测可用代理并缓存。

端点：
    draw(text, style, ratio)  -> baidudraw.php   百度绘图
    vision(text, url, type)   -> aitl.php        图片识别
"""

import json
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://missqiu.icu/API"
PROBE_URL = "https://missqiu.icu/"
DRAW_ENDPOINT = "baidudraw.php"
VISION_ENDPOINT = "aitl.php"

_lock = threading.Lock()
_working_proxy = None      # 当前可用代理，如 http://ip:port
_working_at = 0.0          # 上次验证时间
_last_probe = 0.0          # 上次全量探测时间
_available = []            # 探测通过的代理列表


def _urllib_open(url: str, proxy: str | None, timeout: int = 30) -> bytes:
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}
    )
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()


def _probe_one(proxy: str) -> bool:
    """单个代理连通性：访问源站根路径，200 视为通。"""
    try:
        _urllib_open(PROBE_URL, proxy, timeout=8)
        return True
    except Exception:
        return False


def probe_proxies(proxies: list[str], force: bool = False) -> list[str]:
    """并发探测代理列表，返回可用列表（缓存 120 秒）。"""
    global _last_probe, _available, _working_proxy, _working_at
    now = time.time()
    if not force and now - _last_probe < 120 and _available:
        return _available
    if not proxies:
        return []
    ok = []
    with ThreadPoolExecutor(max_workers=min(8, len(proxies))) as ex:
        results = list(ex.map(_probe_one, proxies))
    for p, good in zip(proxies, results):
        if good:
            ok.append(p)
    with _lock:
        _last_probe = now
        _available = ok
        if _working_proxy not in ok:
            _working_proxy = ok[0] if ok else None
            _working_at = 0.0
    return ok


def _get_proxy(proxies: list[str]) -> str | None:
    """取当前可用代理；缓存超过 60 秒则重新探测。"""
    global _working_proxy, _working_at
    now = time.time()
    with _lock:
        if _working_proxy and now - _working_at < 60:
            return _working_proxy
    if not proxies:
        return None
    ok = probe_proxies(proxies)
    with _lock:
        _working_proxy = ok[0] if ok else None
        _working_at = time.time()
    return _working_proxy


def call(endpoint: str, params: dict, proxies: list[str], timeout: int = 90) -> dict:
    """走可用代理调用 missqiu API；失败自动换下一个代理重试。"""
    url = f"{BASE}/{endpoint}?" + urllib.parse.urlencode(params)
    attempts = []
    for _ in range(3):
        proxy = _get_proxy(proxies)
        if not proxy:
            return {"error": "没有可用代理，请在设置中配置国内代理"}
        attempts.append(proxy)
        try:
            raw = _urllib_open(url, proxy, timeout=timeout)
            data = json.loads(raw.decode("utf-8", "ignore"))
            if isinstance(data, dict) and data.get("error") and data["error"].get("code") in ("1305", "1210", "1205"):
                # 模型限流 / 参数错误 — 返回给上层处理，不再换代理
                return data
            return data
        except Exception as e:
            with _lock:
                _working_proxy = None
                _working_at = 0.0
            last_err = str(e)
    return {"error": {"code": -1, "message": f"代理调用失败: {last_err}，尝试过: {attempts}"}}


def draw(text: str, style: str, ratio: str, apikey: str, proxies: list[str]) -> dict:
    """百度绘图。style: 电影写真/人像摄影/卡通/古风/插画/宫崎骏/赛博朋克/复古胶片/莫奈画作/梵高风格/风景/二次元
    ratio: 16:9 / 4:3 / 1:1 / 3:4 / 9:16"""
    if not apikey:
        return {"error": {"code": -1, "message": "未配置 missqiu API Key"}}
    return call(DRAW_ENDPOINT, {
        "text": text, "style": style, "ratio": ratio, "apikey": apikey,
    }, proxies)


def vision(text: str, url: str, type_: int, apikey: str, proxies: list[str]) -> dict:
    """图片识别。url 必须完整编码（内部含 & 等字符）。"""
    if not apikey:
        return {"error": {"code": -1, "message": "未配置 missqiu API Key"}}
    return call(VISION_ENDPOINT, {
        "text": text, "url": url, "type": type_, "apikey": apikey,
    }, proxies)
