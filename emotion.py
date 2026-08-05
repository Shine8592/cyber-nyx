#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""情绪识别增强 — 7 种情绪 + 强度，关键词快筛兜底。

情绪种类：
    happy / sad / angry / surprised / shy / curious / neutral

设计：
    关键词快筛（0ms，兜底）→ 可选的 LLM 精判（由上层决定是否调用）
    返回 (emotion, intensity) 二元组，intensity ∈ [0, 1]。

用法：
    from emotion import infer_emotion, EMOTION_LABELS
    emotion, intensity = infer_emotion("呜呜呜好难过")
"""

# 情绪中文标签（前端展示用）
EMOTION_LABELS = {
    "happy": "开心",
    "sad": "难过",
    "angry": "生气",
    "surprised": "惊讶",
    "shy": "害羞",
    "curious": "好奇",
    "neutral": "平静",
}

# 表情符号 → 情绪
_EMOJI_MAP = {
    "😄": "happy",
    "😊": "happy",
    "😁": "happy",
    "😂": "happy",
    "🥳": "happy",
    "😆": "happy",
    "😃": "happy",
    "🤣": "happy",
    "😢": "sad",
    "😭": "sad",
    "😞": "sad",
    "😔": "sad",
    "💔": "sad",
    "🥺": "sad",
    "😿": "sad",
    "😠": "angry",
    "😡": "angry",
    "🤬": "angry",
    "💢": "angry",
    "👿": "angry",
    "😲": "surprised",
    "😱": "surprised",
    "🤯": "surprised",
    "😳": "surprised",
    "😮": "surprised",
    "🥰": "shy",
    "😍": "shy",
    "💕": "shy",
    "❤": "happy",
    "💖": "happy",
    "🤔": "curious",
    "🧐": "curious",
    "❓": "curious",
    "❔": "curious",
}

# 关键词 → 情绪（按优先级从高到低）
_KEYWORDS: dict[str, list[str]] = {
    "angry": [
        "生气",
        "讨厌",
        "烦死",
        "气死",
        "滚",
        "去死",
        "有病",
        "烦人",
        "可恶",
        "混蛋",
        "火大",
        "受够了",
        "忍不了",
        "你走开",
    ],
    "sad": [
        "难过",
        "伤心",
        "哭",
        "呜呜",
        "委屈",
        "心碎",
        "崩溃",
        "好累",
        "绝望",
        "孤单",
        "寂寞",
        "想哭",
        "不开心",
        "抑郁",
        "失落",
        "唉",
        "算了",
        "没意思",
        "无聊",
    ],
    "surprised": [
        "卧槽",
        "天哪",
        "我的天",
        "不是吧",
        "真的吗",
        "我去",
        "哇塞",
        "竟然",
        "居然",
        "吓死",
        "震惊",
        "不可思议",
        "太突然",
        "啊？！",
        "不会吧",
        "开什么玩笑",
    ],
    "shy": [
        "害羞",
        "人家",
        "讨厌啦",
        "不要嘛",
        "脸红",
        "不好意思",
        "羞",
        "么么哒",
        "亲亲",
        "抱抱",
        "喜欢你",
        "爱你",
    ],
    "happy": [
        "开心",
        "高兴",
        "哈哈",
        "太好了",
        "棒",
        "666",
        "牛",
        "嘻嘻",
        "嘿嘿",
        "耶",
        "万岁",
        "完美",
        "恭喜",
        "快乐",
        "好耶",
        "厉害",
        "喜欢",
        "爱了",
        "爽",
        "期待",
    ],
    "curious": [
        "为什么",
        "怎么",
        "什么",
        "吗",
        "呢",
        "？",
        "?",
        "啥",
        "哪",
        "谁",
        "何时",
        "多少",
        "是不是",
        "难道",
        "好奇",
        "想知道",
        "求解释",
    ],
}

# 感叹号/问号数量 → 强度加成
_INTENSITY_BOOST = {
    "angry": ["！", "!", "气", "恨"],
    "surprised": ["！", "!", "啊", "哇"],
    "sad": ["呜呜", "哭", "…", "。。"],
    "happy": ["！", "!", "哈哈", "太"],
}


def _match_emotion(text: str) -> str | None:
    """关键词/表情快筛：命中返回情绪，否则 None。"""
    # 先查表情符号
    for ch in text:
        if ch in _EMOJI_MAP:
            return _EMOJI_MAP[ch]
    # 再查关键词（优先级列表顺序）
    for emotion, kws in _KEYWORDS.items():
        for kw in kws:
            if kw in text:
                return emotion
    return None


def infer_emotion(text: str) -> tuple[str, float]:
    """识别情绪，返回 (emotion, intensity)。

    - 关键词/表情快筛兜底，命中即返回
    - 未命中返回 neutral, 0.0
    """
    text = (text or "").strip()
    if not text:
        return "neutral", 0.0

    emotion = _match_emotion(text)
    if emotion is None:
        return "neutral", 0.0

    # 强度计算：基础 0.5 + 强化词加成（封顶 1.0）
    intensity = 0.5
    for kw in _INTENSITY_BOOST.get(emotion, []):
        count = text.count(kw)
        if count:
            intensity += min(0.25 * count, 0.4)
    # 标点放大：连续感叹号/问号
    for p in ("！！！", "？？？", "。。。", "!!!!", "!!!"):
        if p in text:
            intensity = min(intensity + 0.15, 1.0)
    return emotion, round(min(intensity, 1.0), 2)


def classify_with_llm(text: str, llm_chat) -> tuple[str, float]:
    """LLM 精判（可选）。llm_chat 为可调用对象，返回 OpenAI 风格回复。

    失败或解析失败时回退关键词快筛。返回 (emotion, intensity)。
    """
    prompt = (
        "你是一个情绪分析器。分析以下消息的情绪，只返回一个JSON："
        '{"emotion":"happy/sad/angry/surprised/shy/curious/neutral",'
        '"intensity":0.0~1.0}\n不要返回其他内容。\n消息：' + text
    )
    try:
        raw = llm_chat(prompt)
        import json
        import re

        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            data = json.loads(m.group(0))
            emotion = data.get("emotion", "neutral")
            if emotion not in EMOTION_LABELS:
                emotion = "neutral"
            intensity = max(0.0, min(float(data.get("intensity", 0.5)), 1.0))
            return emotion, round(intensity, 2)
    except Exception:
        pass
    return infer_emotion(text)
