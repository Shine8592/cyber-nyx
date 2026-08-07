import os
from pathlib import Path

def get_opencode_global() -> Path:
    """全局记忆系统根目录（跨 Agent 通用，不依赖 opencode 专属路径）。
    优先 MEMORY_GLOBAL_DIR；未设置时，优先真实部署目录 ~/.hermes/memory（若存在）
    ，否则回退旧的 ~/.config/opencode/memory（为 cron/nohup 无 env 场景兜底）。
    """
    env = os.environ.get("MEMORY_GLOBAL_DIR")
    if env:
        return Path(env).resolve()
    # 真实部署路径探测：~/.hermes/memory 存在则优先（GitHub 修复版逻辑，兼容性保留）
    hermes = Path.home() / ".hermes" / "memory"
    if hermes.exists():
        return hermes
    return Path.home() / ".config" / "opencode" / "memory"

def get_project_root() -> Path:
    """项目根目录：优先 MEMORY_PROJECT_ROOT（跨 Agent 通用），兼容 OPENCODE_PROJECT_ROOT。
    未设置时回退 ~/.hermes（真实部署）。
    """
    env = os.environ.get("MEMORY_PROJECT_ROOT") or os.environ.get("OPENCODE_PROJECT_ROOT")
    if env:
        return Path(env).resolve()
    if (Path.home() / ".hermes" / "memory").exists():
        return Path.home() / ".hermes"
    return Path.cwd().resolve()

def get_memory_dir() -> Path:
    """项目级记忆存储目录（兼容旧路径 .opencode/memory，支持 MEMORY_STORE 覆盖）。
    未设环境变量时（如 cron/nohup 直接跑脚本），优先真实部署路径，
    否则回退 cwd/.opencode/memory —— 避免读空目录导致索引/检索全 0。"""
    env = os.environ.get("MEMORY_STORE")
    if env:
        return Path(env).resolve()
    # 真实部署路径探测：~/.hermes/memory 存在则优先（GitHub 修复版逻辑，兼容性保留）
    hermes = Path.home() / ".hermes" / "memory"
    if hermes.exists():
        return hermes
    return get_project_root() / ".opencode" / "memory"

def get_scripts_dir() -> Path:
    return get_opencode_global() / "scripts"

def get_hermes_dir() -> Path:
    """记忆核心文件目录（.opencode/）"""
    return get_project_root() / ".opencode"

MEMORY_DIR = get_memory_dir()
HERMES_DIR = get_hermes_dir()
SCRIPTS_DIR = get_scripts_dir()

INDEX_PATH = MEMORY_DIR / "semantic_index.faiss"
METADATA_PATH = MEMORY_DIR / "semantic_metadata.json"

# 嵌入模型：支持 MEMORY_MODEL_NAME 覆盖，智能默认：优先多语言（已下载），否则回退旧模型
_ML_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"   # 优先：中英文效果均佳
_EN_MODEL  = "all-MiniLM-L6-v2"                        # 回退：仅英文，但已下载

def _choose_default_model() -> str:
    """自动选最佳已缓存模型"""
    global_dir = get_opencode_global()
    ml_cache = global_dir / "models" / _ML_MODEL.replace("/", "_").replace(":", "_")
    if ml_cache.exists():
        return _ML_MODEL
    legacy = global_dir / "semantic_model"
    if legacy.exists():
        return _EN_MODEL
    return _ML_MODEL

DEFAULT_MODEL = _ML_MODEL
MODEL_NAME = os.environ.get("MEMORY_MODEL_NAME", _choose_default_model())

# --- Cross-encoder 重排模型（v3.0，支持 MEMORY_RERANKER 环境变量；off 禁用） ---
_DEF_RERANKER = "cross-encoder/ms-marco-MiniLM-L-6-v2"

def get_reranker_path() -> Path:
    safe = _DEF_RERANKER.replace("/", "_").replace(":", "_")
    return get_opencode_global() / "rerankers" / safe

_RERANK_ENV = os.environ.get("MEMORY_RERANKER", "").strip()
if _RERANK_ENV.lower() == "off":
    RERANK_ENABLED = False
    RERANKER_NAME = ""
    RERANKER_PATH = None
else:
    RERANK_ENABLED = True
    RERANKER_NAME = _RERANK_ENV or _DEF_RERANKER
    RERANKER_PATH = get_reranker_path()

def get_model_path() -> Path:
    """模型本地缓存目录（按模型名区分，避免混用）"""
    safe = MODEL_NAME.replace("/", "_").replace(":", "_")
    return get_opencode_global() / "models" / safe

MODEL_PATH = get_model_path()


# --- 嵌入模型统一加载（含国内镜像自动降级） ---
# 国内直连 HuggingFace 常超时，首次需下载模型。由本函数统一处理：
#   ① 本地缓存存在 → 直接加载（全程离线，最快）
#   ② 缓存缺失 → 先走 HF_ENDPOINT（默认官方或用户自设镜像）
#   ③ 失败 → 自动切 hf-mirror.com 国内镜像重试（结束后恢复原 HF_ENDPOINT，不污染全局）
_MIRROR_ENDPOINT = "https://hf-mirror.com"

def _load_embedding():
    """按当前 HF_ENDPOINT 加载并缓存模型（允许联网下载）。"""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    try:
        MODEL_PATH.mkdir(parents=True, exist_ok=True)
        model.save(str(MODEL_PATH))  # 持久化缓存，下次离线直读
    except Exception:
        pass  # 缓存失败不致命，返回已加载模型即可
    return model

def load_embedding_model():
    """加载嵌入模型（含镜像降级）。

    ① 本地缓存存在 → 离线直读（最快）；
    ② 否则在线下载（尊重用户设的 HF_ENDPOINT 镜像）；
    ③ 直连失败自动切 hf-mirror.com 国内镜像重试。
    全部失败则抛异常，由调用方回退/兜底。
    """
    from sentence_transformers import SentenceTransformer
    if MODEL_PATH.exists():
        return SentenceTransformer(str(MODEL_PATH))  # ① 离线直读

    _old = os.environ.get("HF_ENDPOINT", "")
    os.environ.pop("TRANSFORMERS_OFFLINE", None)  # 允许联网下载
    try:
        # ② 先按当前 endpoint 直连下载
        return _load_embedding()
    except Exception:
        # ③ 直连失败 → 切国内镜像重试
        try:
            os.environ["HF_ENDPOINT"] = _MIRROR_ENDPOINT
            return _load_embedding()
        finally:
            # 恢复原 HF_ENDPOINT，避免污染全局
            if _old:
                os.environ["HF_ENDPOINT"] = _old
            else:
                os.environ.pop("HF_ENDPOINT", None)

STM_DIR = MEMORY_DIR / "stm"
LTM_FILE = HERMES_DIR / "MEMORY.md"
COORDINATOR_FILE = MEMORY_DIR / "memory_coordinator.json"
ARCHIVE_DIR = MEMORY_DIR / "archive"
DAILY_DIR = MEMORY_DIR / "daily"
DIFF_LOG_PATH = MEMORY_DIR / "memory_diff.jsonl"   # 审计日志（阶段三-8）

MAX_CHUNK_CHARS = 1200

CORE_FILES = ["SOUL.md", "USER.md", "MEMORY.md", "AGENTS.md"]
PROJECT_ROOT = get_project_root()

def ensure_dirs():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    STM_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    DAILY_DIR.mkdir(parents=True, exist_ok=True)


# Faiss 原生 C++ I/O 不支持中文路径，用序列化绕开
_faiss = None
_np = None

def _load_faiss():
    global _faiss, _np
    if _faiss is None:
        import faiss
        import numpy as np
        _faiss = faiss
        _np = np

def write_index_safe(index, path: Path):
    _load_faiss()
    buf = _faiss.serialize_index(index)
    path.write_bytes(buf.tobytes())

def read_index_safe(path: Path):
    _load_faiss()
    buf = _np.frombuffer(path.read_bytes(), dtype=_np.uint8)
    return _faiss.deserialize_index(buf)
