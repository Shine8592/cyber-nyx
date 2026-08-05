#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""情绪识别模块单元测试。"""

from emotion import EMOTION_LABELS, classify_with_llm, infer_emotion


class TestHappy:
    def test_happy_keyword(self):
        assert infer_emotion("今天好开心啊") == ("happy", 0.5)

    def test_happy_laugh(self):
        emotion, intensity = infer_emotion("哈哈哈哈哈")
        assert emotion == "happy"
        assert intensity > 0.5  # 强化词加成

    def test_happy_emoji(self):
        assert infer_emotion("太好了😄")[0] == "happy"


class TestSad:
    def test_sad_keyword(self):
        assert infer_emotion("呜呜呜好难过")[0] == "sad"

    def test_sad_cry(self):
        emotion, intensity = infer_emotion("呜呜呜")
        assert emotion == "sad"
        assert intensity >= 0.5

    def test_sad_emoji(self):
        assert infer_emotion("😢")[0] == "sad"


class TestAngry:
    def test_angry_keyword(self):
        assert infer_emotion("你真讨厌")[0] == "angry"

    def test_angry_strong(self):
        emotion, intensity = infer_emotion("气死我了！！！")
        assert emotion == "angry"
        assert intensity >= 0.75  # 强化词 + 连续感叹号


class TestSurprised:
    def test_surprised_keyword(self):
        assert infer_emotion("天哪不是吧")[0] == "surprised"

    def test_surprised_emoji(self):
        assert infer_emotion("😲")[0] == "surprised"


class TestShy:
    def test_shy_keyword(self):
        assert infer_emotion("人家害羞啦")[0] == "shy"

    def test_shy_love(self):
        assert infer_emotion("喜欢你呀")[0] == "shy"


class TestCurious:
    def test_curious_question(self):
        assert infer_emotion("为什么天是蓝的？")[0] == "curious"

    def test_curious_ma(self):
        assert infer_emotion("你吃饭了吗")[0] == "curious"


class TestNeutral:
    def test_neutral_plain(self):
        assert infer_emotion("今天天气不错") == ("neutral", 0.0)

    def test_empty(self):
        assert infer_emotion("") == ("neutral", 0.0)
        assert infer_emotion(None) == ("neutral", 0.0)


class TestLabels:
    def test_labels_complete(self):
        for e in ["happy", "sad", "angry", "surprised", "shy", "curious", "neutral"]:
            assert e in EMOTION_LABELS


class TestClassifyWithLLM:
    def test_llm_parse(self):
        def fake_chat(prompt):
            return '{"emotion":"happy","intensity":0.9}'

        assert classify_with_llm("随便说点啥", fake_chat) == ("happy", 0.9)

    def test_llm_garbage_falls_back(self):
        def fake_chat(prompt):
            return "这不是JSON"

        emotion, _ = classify_with_llm("哈哈真开心", fake_chat)
        assert emotion == "happy"  # 回退关键词

    def test_llm_exception_falls_back(self):
        def fake_chat(prompt):
            raise RuntimeError("boom")

        assert classify_with_llm("😢", fake_chat)[0] == "sad"

    def test_llm_invalid_emotion_normalized(self):
        def fake_chat(prompt):
            return '{"emotion":"furious","intensity":2.0}'

        emotion, intensity = classify_with_llm("测试", fake_chat)
        assert emotion == "neutral"  # 未知情绪归一化
        assert 0.0 <= intensity <= 1.0  # 强度封顶
