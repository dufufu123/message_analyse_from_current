"""
文本情感分析模块（重写版）

基于分词结果 + 情感词典 + 否定窗口 + 程度副词的严谨情感评分。

算法流程：
1. 遍历分词后的token列表
2. 对每个token，查情感词典获取极性和强度
3. 对情感词，向前扫描2-3个token的窗口：
   a. 否定检查：窗口内存在否定词 → 极性翻转 ×(-0.7)
   b. 程度检查：窗口内存在程度副词 → 极性 × 强度倍率
4. 汇总所有调整后的极性值
5. 归一化到 [-1, 1]，根据阈值划分正/负/中性

对比旧版：
  - 旧: 80个硬编码词 + text.count() 子串匹配，否定词/程度词未使用
  - 新: 1000+词情感词典 + token边界匹配 + 否定翻转 + 程度倍率
"""

import math
from dataclasses import dataclass
from typing import Optional

from snownlp import SnowNLP

from analysis.lexicon_loader import get_lexicon
from config.settings import SENTIMENT_THRESHOLDS
from utils.logger import logger

# 否定窗口大小（检查情感词前N个token）
NEGATION_WINDOW = 3
# 程度词窗口大小
INTENSIFIER_WINDOW = 2
# 否定翻转时的阻尼系数（不完全翻转，保留部分原始信号）
NEGATION_DAMPING = 0.7
# 程度倍率上限
MAX_INTENSITY_MULT = 3.0
# 程度倍率下限
MIN_INTENSITY_MULT = 0.2


@dataclass
class SentimentResult:
    """情感分析结果"""
    score: float = 0.0           # -1.0(负面) ~ +1.0(正面)
    label: str = "neutral"       # positive / negative / neutral
    confidence: float = 0.0      # 置信度 0~1
    word_count: int = 0          # 匹配到的情感词数量
    pos_count: int = 0           # 正面词数量
    neg_count: int = 0           # 负面词数量
    matched_words: list = None   # 匹配到的情感词详情
    method: str = "lexicon"      # 分析方法

    def __post_init__(self):
        if self.matched_words is None:
            self.matched_words = []

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "label": self.label,
            "confidence": self.confidence,
            "word_count": self.word_count,
            "pos_count": self.pos_count,
            "neg_count": self.neg_count,
            "matched_words": self.matched_words,
            "method": self.method,
        }


class SentimentAnalyzer:
    """基于分词和情感词典的中文情感分析器。

    算法详述：
      给定 token 序列 T = [t0, t1, ..., tn-1]，
      对每个 token ti：
        1. 查词典得到 base_polarity(ti) 和 base_intensity(ti)
        2. 如果 base_polarity != 0（说明是情感词）：
           a. 否定窗口 [i-NEGATION_WINDOW, i-1]：
              扫描窗口内的否定词，奇数个 → 翻转，偶数个 → 恢复
              adjusted = base_polarity × (-NEGATION_DAMPING)^odd_count
           b. 程度窗口 [i-INTENSIFIER_WINDOW, i-1]：
              累乘窗口内所有程度副词的倍率值
              multiplier = clamp(Π intensity, MIN, MAX)
              adjusted = adjusted × multiplier
           c. 记录 (position, word, original_polarity, adjusted_polarity)
      最终得分 = tanh(Σ adjusted_polarity / sqrt(n_matches + 1))

    Usage:
        analyzer = SentimentAnalyzer()
        tokens = ["这个", "产品", "非常", "好", "用"]
        result = analyzer.analyze(tokens)
        print(result.label, result.score)
    """

    def __init__(self, use_snownlp_fallback: bool = True):
        """
        Args:
            use_snownlp_fallback: 词典无匹配时是否回退到 SnowNLP。
        """
        self.lexicon = get_lexicon()
        self.use_snownlp_fallback = use_snownlp_fallback
        logger.info(
            f"SentimentAnalyzer initialized: "
            f"lexicon={len(self.lexicon)} words, "
            f"negation_window={NEGATION_WINDOW}, "
            f"intensifier_window={INTENSIFIER_WINDOW}, "
            f"snownlp_fallback={use_snownlp_fallback}"
        )

    # ----------------------------------------------------------
    # 核心算法
    # ----------------------------------------------------------
    def analyze(self, tokens: list[str]) -> SentimentResult:
        """分析token列表的情感倾向。

        Args:
            tokens: 分词后的token列表（建议使用jieba分词结果）。

        Returns:
            SentimentResult with score, label, and details.
        """
        if not tokens or len(tokens) < 2:
            return SentimentResult()

        matched = []       # [(position, word, original_pol, adjusted_pol), ...]
        pos_count = 0
        neg_count = 0

        for i, token in enumerate(tokens):
            # Step 1: 查词典
            polarity = self.lexicon.get_polarity(token)
            if polarity == 0.0:
                continue  # 非情感词，跳过

            original_pol = polarity
            adjusted_pol = polarity

            # Step 2: 否定检查 (向前看 NEGATION_WINDOW 个token)
            negation_found = False
            odd_negations = 0
            for j in range(max(0, i - NEGATION_WINDOW), i):
                if self.lexicon.is_negation(tokens[j]):
                    odd_negations += 1

            if odd_negations > 0:
                if odd_negations % 2 == 1:
                    # 奇数个否定词 → 翻转
                    adjusted_pol = adjusted_pol * (-NEGATION_DAMPING)
                    negation_found = True
                else:
                    # 偶数个否定词 → 双否定 ≈ 肯定，轻微折扣
                    adjusted_pol = adjusted_pol * 0.85

            # Step 3: 程度副词检查 (向前看 INTENSIFIER_WINDOW 个token)
            intensifier_mult = 1.0
            for j in range(max(0, i - INTENSIFIER_WINDOW), i):
                mult = self.lexicon.get_intensifier_mult(tokens[j])
                if mult != 1.0:
                    intensifier_mult *= mult

            intensifier_mult = max(MIN_INTENSITY_MULT, min(MAX_INTENSITY_MULT, intensifier_mult))
            adjusted_pol = adjusted_pol * intensifier_mult

            # Step 4: 记录
            matched.append({
                "position": i,
                "word": token,
                "original_polarity": round(original_pol, 3),
                "adjusted_polarity": round(adjusted_pol, 3),
                "negation_applied": negation_found,
                "intensifier_applied": intensifier_mult != 1.0,
            })

            if adjusted_pol > 0:
                pos_count += 1
            else:
                neg_count += 1

        # Step 5: 汇总评分
        n_matches = len(matched)
        if n_matches == 0:
            return self._snownlp_fallback(tokens) if self.use_snownlp_fallback else SentimentResult()

        raw_score = sum(m["adjusted_polarity"] for m in matched)

        # 归一化：用 sqrt(n_matches) 做惩罚，避免少量词产生极端分
        # tanh 将 (-inf, inf) 平滑映射到 (-1, 1)
        normalized = raw_score / math.sqrt(n_matches + 1)
        final_score = math.tanh(normalized)

        # Clamp to [-1, 1]
        final_score = max(-1.0, min(1.0, final_score))

        # Step 6: 确定标签
        if final_score > SENTIMENT_THRESHOLDS.get("positive_min", 0.15):
            label = "positive"
        elif final_score < SENTIMENT_THRESHOLDS.get("negative_max", -0.15):
            label = "negative"
        else:
            label = "neutral"

        # 置信度：基于匹配词数量和分数幅度
        confidence = min(1.0, abs(raw_score) / 3.0 * min(1.0, n_matches / 5.0))

        return SentimentResult(
            score=round(final_score, 4),
            label=label,
            confidence=round(confidence, 4),
            word_count=n_matches,
            pos_count=pos_count,
            neg_count=neg_count,
            matched_words=matched[:20],  # 最多返回20个详情
            method="lexicon",
        )

    def _snownlp_fallback(self, tokens: list[str]) -> SentimentResult:
        """词典无匹配时回退到 SnowNLP（原始文本方式）。"""
        text = "".join(tokens)
        try:
            s = SnowNLP(text)
            raw = s.sentiments
            mapped = (raw - 0.5) * 2
            label = (
                "positive" if mapped > 0.15
                else "negative" if mapped < -0.15
                else "neutral"
            )
            return SentimentResult(
                score=round(mapped, 4),
                label=label,
                confidence=round(abs(raw - 0.5) * 2, 4),
                method="snownlp(fallback)",
            )
        except Exception:
            return SentimentResult()

    def batch_analyze(self, token_lists: list[list[str]]) -> list[SentimentResult]:
        """批量分析。"""
        return [self.analyze(tokens) for tokens in token_lists]
