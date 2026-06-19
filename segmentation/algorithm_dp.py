"""
分词算法3：基于统计的DP最短路径分词器（自定义实现）

算法原理：
  将中文分词转化为最优化问题：给定输入文本，寻找使得词序列
  概率乘积最大的分词方案。

  使用 unigram 语言模型：
    P(W) = Π P(w_i), 其中 P(w) = freq(w) / total_freq

  取负对数转化为最短路径问题：
    cost(w) = -log(P(w))
    min Σ cost(w_i)

  使用动态规划求解：
    dp[i] = min_{j < i}(dp[j] + cost(text[j:i]))

    dp[0] = 0
    dp[i] 表示 text[0:i] 的最小分词代价

  与 jieba 的区别：
    - jieba: 先构建DAG（有向无环图包含所有词典匹配），再用DP找最优路径，
      最后用HMM处理未登录词（OOV）
    - 本算法: 直接用DP穷举所有可能的子串，对已知词用频次代价，
      对未知词（OOV）用线性惩罚函数

  与 MaxMatch 的区别：
    - MaxMatch: 贪心策略，每次取最长匹配，局部最优
    - 本算法: 全局最优，考虑所有可能的分词方案

参考：
  - J. Gao et al., "Chinese Word Segmentation and Named Entity Recognition:
    A Pragmatic Approach", Computational Linguistics, 2005.
  - 宗成庆《统计自然语言处理》第6章
"""

import math

import jieba

from config.settings import SEGMENTATION_MAX_WORD_LEN
from segmentation.preprocessor import TextPreprocessor
from utils.logger import logger


class DPUnigramSegmenter:
    """Dynamic-programming-based unigram Chinese word segmenter.

    Uses jieba's word-frequency dictionary as a unigram language model.
    Finds the globally optimal segmentation by minimizing the total
    negative log-probability cost via dynamic programming.

    Complexity: O(n * max_word_len) time, O(n) space,
    where n = text length, max_word_len = max dictionary word length.

    States: Uses the word frequency dictionary directly — no BMES tagging.
    """

    def __init__(
        self,
        max_word_len: int = SEGMENTATION_MAX_WORD_LEN,
        oov_penalty: float = 15.0,
        preprocessor: TextPreprocessor | None = None,
    ):
        """
        Args:
            max_word_len: Maximum word length to consider (from dictionary).
            oov_penalty: Cost penalty for out-of-vocabulary characters.
                         Higher = more aggressive grouping of unknown chars.
            preprocessor: Optional TextPreprocessor instance.
        """
        self.max_word_len = max_word_len
        self.oov_penalty = oov_penalty  # Cost per character for OOV
        self.preprocessor = preprocessor or TextPreprocessor()
        self._word_cost: dict[str, float] = {}
        self._total_freq: float = 1.0
        self._load_dictionary()
        logger.info(
            f"DPUnigramSegmenter initialized: dict_size={len(self._word_cost)}, "
            f"max_word_len={self.max_word_len}, oov_penalty={self.oov_penalty}"
        )

    def _load_dictionary(self) -> None:
        """Build word-cost table from jieba's frequency dictionary.

        cost(w) = -log(freq(w) / total_freq)
        = log(total_freq) - log(freq(w))

        This ensures: common words → low cost → preferred in DP.
        """
        # Force jieba initialization
        if not jieba.dt.FREQ:
            list(jieba.cut("初始化"))

        total = sum(jieba.dt.FREQ.values())
        self._total_freq = max(total, 1.0)
        log_total = math.log(self._total_freq)

        for word, freq in jieba.dt.FREQ.items():
            # cost = log(total) - log(freq)
            # Lower cost = more common word
            cost = log_total - math.log(max(freq, 1))
            self._word_cost[word] = cost

        logger.info(f"Built cost table for {len(self._word_cost)} words")

    @property
    def name(self) -> str:
        return "dp_unigram"

    def _word_log_prob(self, word: str) -> float:
        """Return -log(P(word)). Lower = more probable."""
        if word in self._word_cost:
            return self._word_cost[word]
        # OOV: penalize by length — each char costs oov_penalty
        return self.oov_penalty * len(word)

    # ----------------------------------------------------------------
    # Dynamic Programming — minimum-cost segmentation
    # ----------------------------------------------------------------

    def _dp_segment(self, text: str) -> list[str]:
        """Find the globally optimal segmentation using DP.

        dp[i] = minimum cost to segment text[0:i]
        back[i] = index of previous split point for the optimal path

        Args:
            text: Preprocessed text string.

        Returns:
            List of word tokens (optimal segmentation).
        """
        n = len(text)
        if n == 0:
            return []

        # dp[i] = best cost for prefix of length i
        dp = [float("inf")] * (n + 1)
        dp[0] = 0

        # back[i] = split point that achieved dp[i]
        back = [0] * (n + 1)

        for i in range(1, n + 1):
            # Try all possible last words ending at position i
            max_lookback = min(self.max_word_len, i)
            for length in range(1, max_lookback + 1):
                j = i - length
                word = text[j:i]
                cost = dp[j] + self._word_log_prob(word)
                if cost < dp[i]:
                    dp[i] = cost
                    back[i] = j

        # Backtrack to recover the token sequence
        tokens = []
        i = n
        while i > 0:
            j = back[i]
            tokens.append(text[j:i])
            i = j

        return list(reversed(tokens))

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def segment(self, text: str) -> list[str]:
        """Segment Chinese text using DP-based unigram model.

        Args:
            text: Chinese plain text.

        Returns:
            List of word tokens (globally optimal per the unigram model).
        """
        text = self.preprocessor.preprocess(text)

        if not text:
            return []

        tokens = self._dp_segment(text)
        tokens = self.preprocessor.remove_stopwords(tokens)
        return tokens

    def batch_segment(self, texts: list[str]) -> list[list[str]]:
        """Segment multiple texts."""
        return [self.segment(text) for text in texts]

    def add_words(self, words: list[str]) -> None:
        """Add custom words to the cost table (treated as common words)."""
        for word in words:
            # Assign a low cost to make DP prefer this word
            self._word_cost[word] = 0.1
            # Update max_word_len if needed
            if len(word) > self.max_word_len:
                self.max_word_len = len(word)

    def get_stats(self) -> dict:
        """Get segmenter statistics."""
        return {
            "algorithm": "DP Unigram (shortest path)",
            "dictionary_size": len(self._word_cost),
            "max_word_len": self.max_word_len,
            "oov_penalty": self.oov_penalty,
            "total_freq": self._total_freq,
        }
