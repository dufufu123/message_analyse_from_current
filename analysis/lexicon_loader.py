"""
情感词典加载器

加载和管理情感词典资源：
- sentiment_lexicon.tsv：情感词条（极性分数+强度+类别）
- negation_words.txt：否定词列表
- intensifier_words.txt：程度副词（含倍率）
"""

import re
from pathlib import Path
from typing import Optional

from config.settings import BASE_DIR
from utils.logger import logger

# 词典文件路径
LEXICON_DIR = BASE_DIR / "data" / "lexicon"
SENTIMENT_LEXICON_PATH = LEXICON_DIR / "sentiment_lexicon.tsv"
NEGATION_WORDS_PATH = BASE_DIR / "config" / "negation_words.txt"
INTENSIFIER_WORDS_PATH = BASE_DIR / "config" / "intensifier_words.txt"


class LexiconLoader:
    """情感词典加载和查询。

    词典格式 (TSV):
        word\tpolarity\tintensity\tcategory

    其中：
        polarity: -1.0(极度负面) ~ +1.0(极度正面)，0为中性
        intensity: 情感强度倍率，>1为增强，<1为减弱，0为功能词
        category: praise/criticism/joy/anger/sadness/fear/surprise/disgust/
                 negation/intensifier/diminisher/sentiment
    """

    def __init__(self):
        self._words: dict[str, dict] = {}        # word → {polarity, intensity, category}
        self._negation_words: set[str] = set()   # 否定词集合
        self._intensifiers: dict[str, float] = {} # 程度词 → 倍率
        self._loaded = False

    def load(self) -> None:
        """加载所有词典文件。"""
        if self._loaded:
            return

        self._load_sentiment_lexicon()
        self._load_negation_words()
        self._load_intensifier_words()
        self._loaded = True

        pos_count = sum(1 for v in self._words.values() if v["polarity"] > 0)
        neg_count = sum(1 for v in self._words.values() if v["polarity"] < 0)
        logger.info(
            f"Lexicon loaded: {len(self._words)} words "
            f"(positive={pos_count}, negative={neg_count}), "
            f"negations={len(self._negation_words)}, "
            f"intensifiers={len(self._intensifiers)}"
        )

    # ----------------------------------------------------------
    # 加载子模块
    # ----------------------------------------------------------
    def _load_sentiment_lexicon(self) -> None:
        """加载情感词典TSV文件。"""
        path = SENTIMENT_LEXICON_PATH
        if not path.exists():
            logger.error(f"Sentiment lexicon not found: {path}")
            return

        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                try:
                    word = parts[0].strip()
                    polarity = float(parts[1])
                    intensity = float(parts[2]) if len(parts) > 2 else 1.0
                    category = parts[3].strip() if len(parts) > 3 else "sentiment"
                    self._words[word] = {
                        "polarity": polarity,
                        "intensity": intensity,
                        "category": category,
                    }
                except ValueError:
                    logger.debug(f"Skip line {line_num}: {line[:60]}")
                    continue

    def _load_negation_words(self) -> None:
        """加载否定词列表（每行一个词）。"""
        path = NEGATION_WORDS_PATH
        if not path.exists():
            logger.warning(f"Negation words file not found: {path}")
            self._negation_words = _DEFAULT_NEGATIONS
            return

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word and not word.startswith("#"):
                    self._negation_words.add(word)

    def _load_intensifier_words(self) -> None:
        """加载程度副词列表（每行：词 倍率）。"""
        path = INTENSIFIER_WORDS_PATH
        if not path.exists():
            logger.warning(f"Intensifier words file not found: {path}")
            self._intensifiers = dict(_DEFAULT_INTENSIFIERS)
            return

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        self._intensifiers[parts[0]] = float(parts[1])
                    except ValueError:
                        continue

    # ----------------------------------------------------------
    # 查询接口
    # ----------------------------------------------------------
    def get(self, word: str) -> Optional[dict]:
        """获取词条的词典信息。"""
        return self._words.get(word)

    def get_polarity(self, word: str) -> float:
        """获取词条的极性分数（0表示不在词典中）。"""
        entry = self._words.get(word)
        return entry["polarity"] if entry else 0.0

    def get_intensity(self, word: str) -> float:
        """获取词条的强度系数（1.0表示普通情感词或不在词典中）。"""
        entry = self._words.get(word)
        return entry["intensity"] if entry else 1.0

    def get_category(self, word: str) -> str:
        """获取词条的类别。"""
        entry = self._words.get(word)
        return entry["category"] if entry else ""

    def is_negation(self, word: str) -> bool:
        """判断是否为否定词。"""
        return word in self._negation_words

    def is_intensifier(self, word: str) -> bool:
        """判断是否为程度副词。"""
        return word in self._intensifiers

    def get_intensifier_mult(self, word: str) -> float:
        """获取程度副词的倍率（1.0表示非程度词）。"""
        return self._intensifiers.get(word, 1.0)

    def is_diminisher(self, word: str) -> bool:
        """判断是否为减弱词（倍率<1的程度副词）。"""
        mult = self._intensifiers.get(word, 1.0)
        return 0 < mult < 1.0

    def __contains__(self, word: str) -> bool:
        return word in self._words

    def __len__(self) -> int:
        return len(self._words)


# ================================================================
# 内置默认词典（文件缺失时兜底）
# ================================================================
_DEFAULT_NEGATIONS = {
    "不", "没", "没有", "无", "非", "未", "莫", "勿", "别", "休",
    "不要", "不会", "不必", "不可", "不用", "不能", "不得", "不许", "不准",
    "并非", "毫无", "从不", "决不", "毫不", "并未", "尚无",
    "岂", "哪", "怎", "难道", "何必",
}

_DEFAULT_INTENSIFIERS = {
    # 强程度词 (2.0-2.5x)
    "极其": 2.5, "极度": 2.5, "万分": 2.5, "非常": 2.0,
    "特别": 2.0, "尤其": 2.0, "格外": 2.0, "分外": 2.0,
    "十分": 2.0, "相当": 1.8, "颇": 1.8, "甚": 1.8,
    "太": 1.8, "真": 1.5, "好": 1.5, "多么": 2.0,
    "异常": 2.0, "绝对": 1.8,
    # 中等程度词 (1.3-1.8x)
    "很": 1.5, "挺": 1.3, "比较": 1.3, "较": 1.3,
    "更": 1.5, "更加": 1.5, "还": 1.3, "越": 1.5,
    "越来越": 1.8, "越发": 1.5, "愈加": 1.5,
    "多": 1.3, "这么": 1.3, "那么": 1.3, "如此": 1.5,
    "蛮": 1.3, "满": 1.3, "好不": 1.5,
    "够": 1.3, "怪": 1.3, "老": 1.3,
    # 减弱词 (0.3-0.7x)
    "有点": 0.5, "有些": 0.5, "稍微": 0.3, "略微": 0.3,
    "稍稍": 0.3, "略": 0.5, "稍": 0.5, "多少": 0.5,
    "还": 0.5, "还算": 0.5, "不太": 0.3, "不怎么": 0.3,
    "不大": 0.3,
}


# ================================================================
# 全局单例
# ================================================================
_lexicon_instance: Optional[LexiconLoader] = None


def get_lexicon() -> LexiconLoader:
    """获取全局词典加载器单例。"""
    global _lexicon_instance
    if _lexicon_instance is None:
        _lexicon_instance = LexiconLoader()
        _lexicon_instance.load()
    return _lexicon_instance
