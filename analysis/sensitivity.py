"""
文本敏感性检测模块（重写版）

基于分词token + AC自动机 + 词边界匹配。

关键改进：
1. analyze() 接受 token 列表而非原始文本
2. 用 \x00 哨兵符连接token做词边界匹配
3. 扩充词库到300+词
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import ahocorasick

from config.settings import SENSITIVE_WORDS_FILE, SENSITIVITY_CATEGORIES
from utils.logger import logger


@dataclass
class SensitivityResult:
    score: float = 0.0
    flags: list[str] = field(default_factory=list)
    matched_words: list[dict] = field(default_factory=list)
    is_sensitive: bool = False

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "flags": self.flags,
            "matched_words": self.matched_words,
            "is_sensitive": self.is_sensitive,
        }


class SensitivityDetector:
    """基于分词token的敏感性检测器。

    使用词边界匹配：将tokens用哨兵符连接后跑AC自动机，
    避免"政治"匹配"非政治"这类子串误报。
    """

    SENTINEL = "\x00"
    THRESHOLD = 0.05

    def __init__(self, wordlist_path: str | Path | None = None):
        self.automaton = ahocorasick.Automaton()
        self.category_weights = {}
        for cat, info in SENSITIVITY_CATEGORIES.items():
            self.category_weights[cat] = info["weight"]
        self._word_meta: dict[int, dict] = {}
        self._word_counter = 0

        path = Path(wordlist_path) if wordlist_path else SENSITIVE_WORDS_FILE
        self._load_words(path)
        logger.info(
            f"SensitivityDetector: {self._word_counter} words, "
            f"{len(self.category_weights)} categories"
        )

    def _load_words(self, path: Path) -> None:
        if not path.exists():
            logger.error(f"Sensitive word file not found: {path}")
            return

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    meta_part, keyword = line.split(None, 1)
                    category, weight_str = meta_part.split(":", 1)
                    weight = float(weight_str)
                except (ValueError, IndexError):
                    continue

                if category not in self.category_weights:
                    continue

                keyword = keyword.strip()
                if not keyword:
                    continue

                idx = self._word_counter
                self.automaton.add_word(keyword, (idx, keyword))
                self._word_meta[idx] = {
                    "word": keyword,
                    "category": category,
                    "weight": weight,
                }
                self._word_counter += 1

        self.automaton.make_automaton()

    def detect(self, tokens: list[str]) -> SensitivityResult:
        """对分词后的token列表进行敏感性检测。

        Args:
            tokens: 分词后的token列表。

        Returns:
            SensitivityResult with score, flags, matched words.
        """
        if not tokens or not self._word_counter:
            return SensitivityResult()

        # 用哨兵符连接，确保词边界
        scan_text = self.SENTINEL + self.SENTINEL.join(tokens) + self.SENTINEL

        # 收集匹配
        matches: dict[str, dict] = {}
        for end_idx, (word_id, word) in self.automaton.iter(scan_text):
            # 验证匹配在词边界内（两边都是哨兵符或首尾）
            start = end_idx - len(word) + 1
            if start > 0 and scan_text[start - 1] != self.SENTINEL:
                continue  # 匹配跨词边界（子串误报），跳过
            if end_idx < len(scan_text) - 1 and scan_text[end_idx + 1] != self.SENTINEL:
                continue  # 匹配跨词边界，跳过

            if word in matches:
                matches[word]["count"] += 1
            else:
                meta = self._word_meta.get(word_id, {})
                matches[word] = {
                    "word": word,
                    "category": meta.get("category", "unknown"),
                    "weight": meta.get("weight", 0.5),
                    "count": 1,
                }

        if not matches:
            return SensitivityResult()

        # 按类别汇总
        category_scores: dict[str, float] = {}
        for m in matches.values():
            cat = m["category"]
            cat_weight = self.category_weights.get(cat, 1.0)
            contrib = m["weight"] * cat_weight * m["count"]
            category_scores[cat] = category_scores.get(cat, 0) + contrib

        # 归一化
        total_weight = sum(self.category_weights.values())
        max_score = max(total_weight * 5, 1.0)
        score = min(1.0, sum(category_scores.values()) / max_score)

        # 确定标记类别
        flags = [cat for cat, s in category_scores.items() if s > self.THRESHOLD]

        return SensitivityResult(
            score=round(score, 4),
            flags=flags,
            matched_words=list(matches.values()),
            is_sensitive=score > self.THRESHOLD,
        )

    def batch_detect(self, token_lists: list[list[str]]) -> list[SensitivityResult]:
        return [self.detect(tokens) for tokens in token_lists]
