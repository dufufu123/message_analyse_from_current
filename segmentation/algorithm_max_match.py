"""
分词算法2：基于最大匹配的中文分词器（自定义实现）

实现三种变体：
- FMM (Forward Maximum Matching)：前向最大匹配
- BMM (Backward Maximum Matching)：后向最大匹配
- BiMM (Bidirectional Maximum Matching)：双向最大匹配

算法原理：
  给定词典D和最大词长L，对输入文本从某个方向开始，
  每次取长度为L的子串，逐步缩短直到在D中找到匹配或
  长度降为1（单字成词），然后指针移动相应长度继续匹配。

FMM 伪代码：
  i = 0
  while i < len(text):
      for length in [max_len, ..., 1]:
          word = text[i : i+length]
          if word in dictionary or length == 1:
              result.append(word)
              i += length
              break

BiMM 规则（选择FMM和BMM中更好的结果）：
  1. 如果两者词数不同，选词数少的
  2. 如果词数相同，选单字词少的
  3. 如果单字词数也相同，选BMM（统计上BMM略优）
"""

from collections import Counter

import jieba

from config.settings import SEGMENTATION_MAX_WORD_LEN
from segmentation.preprocessor import TextPreprocessor
from utils.logger import logger


class MaxMatchSegmenter:
    """Custom Maximum Matching Chinese word segmenter.

    Implements three matching strategies: FMM, BMM, and BiMM.
    Uses the jieba internal dictionary as its vocabulary.

    References:
        - P. K. Wong and C. Chan, "Chinese Word Segmentation based on
          Maximum Matching and Word Binding Force", COLING 1996.
        - 梁南元, "书面汉语自动分词系统 — CDWS", 中文信息学报, 1987.
    """

    def __init__(
        self,
        strategy: str = "bimm",
        max_word_len: int = SEGMENTATION_MAX_WORD_LEN,
        preprocessor: TextPreprocessor | None = None,
    ):
        """
        Args:
            strategy: 'fmm', 'bmm', or 'bimm'.
            max_word_len: Maximum Chinese word length to consider.
            preprocessor: Optional TextPreprocessor instance.
        """
        self.strategy = strategy.lower()
        self.max_word_len = max_word_len
        self.preprocessor = preprocessor or TextPreprocessor()
        self._dictionary: set[str] = set()
        self._load_dictionary()
        logger.info(
            f"MaxMatchSegmenter initialized: strategy={self.strategy}, "
            f"dict_size={len(self._dictionary)}, max_word_len={self.max_word_len}"
        )

    def _load_dictionary(self) -> None:
        """Load vocabulary from jieba's default dictionary.

        jieba.dt.FREQ is a dict mapping word → (frequency, tag).
        We sort by frequency descending so longer, more common words
        are prioritized during matching.
        """
        if not jieba.dt.FREQ:
            # Force jieba to initialize
            list(jieba.cut("初始化"))

        # Take all words from jieba's frequency dictionary
        self._dictionary = set(jieba.dt.FREQ.keys())
        logger.debug(f"Loaded {len(self._dictionary)} dictionary entries from jieba")

    @property
    def name(self) -> str:
        return f"max_match({self.strategy})"

    @property
    def dictionary(self) -> set[str]:
        return self._dictionary

    # ----------------------------------------------------------------
    # Core algorithms
    # ----------------------------------------------------------------

    def _fmm_segment(self, text: str) -> list[str]:
        """Forward Maximum Matching.

        Scans text left-to-right. At each position, tries to match
        the longest possible dictionary word starting at that position.

        Args:
            text: Preprocessed text string.

        Returns:
            List of word tokens.
        """
        tokens = []
        i = 0
        n = len(text)

        while i < n:
            matched = False
            # Try from longest to shortest
            for length in range(min(self.max_word_len, n - i), 0, -1):
                word = text[i : i + length]
                if word in self._dictionary or length == 1:
                    tokens.append(word)
                    i += length
                    matched = True
                    break

            if not matched:
                # Fallback: single character
                tokens.append(text[i])
                i += 1

        return tokens

    def _bmm_segment(self, text: str) -> list[str]:
        """Backward Maximum Matching.

        Scans text right-to-left. At each position, tries to match
        the longest possible dictionary word ending at that position.

        Args:
            text: Preprocessed text string.

        Returns:
            List of word tokens (in reading order).
        """
        tokens_reversed = []
        n = len(text)
        i = n

        while i > 0:
            matched = False
            # Try from longest to shortest
            start_max = max(0, i - self.max_word_len)
            for length in range(i - start_max, 0, -1):
                start = i - length
                word = text[start:i]
                if word in self._dictionary or length == 1:
                    tokens_reversed.append(word)
                    i = start
                    matched = True
                    break

            if not matched:
                tokens_reversed.append(text[i - 1])
                i -= 1

        return list(reversed(tokens_reversed))

    def _bimm_segment(self, text: str) -> list[str]:
        """Bidirectional Maximum Matching.

        Runs both FMM and BMM, then selects the better result using
        heuristic rules:
          1. Fewer total tokens → less ambiguity
          2. Fewer single-character tokens → more meaningful words
          3. Default to BMM (empirically better for Chinese)

        Args:
            text: Preprocessed text string.

        Returns:
            List of word tokens (best of FMM and BMM).
        """
        fmm_tokens = self._fmm_segment(text)
        bmm_tokens = self._bmm_segment(text)

        # Rule 1: fewer total tokens is better
        if len(fmm_tokens) != len(bmm_tokens):
            return fmm_tokens if len(fmm_tokens) < len(bmm_tokens) else bmm_tokens

        # Rule 2: fewer single-character tokens is better
        fmm_singles = sum(1 for t in fmm_tokens if len(t) == 1)
        bmm_singles = sum(1 for t in bmm_tokens if len(t) == 1)

        if fmm_singles != bmm_singles:
            return fmm_tokens if fmm_singles < bmm_singles else bmm_tokens

        # Rule 3: BMM is empirically better for Chinese
        return bmm_tokens

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def segment(self, text: str) -> list[str]:
        """Segment a single text string.

        Args:
            text: Chinese text to segment.

        Returns:
            List of word tokens.
        """
        text = self.preprocessor.preprocess(text)

        if self.strategy == "fmm":
            tokens = self._fmm_segment(text)
        elif self.strategy == "bmm":
            tokens = self._bmm_segment(text)
        elif self.strategy == "bimm":
            tokens = self._bimm_segment(text)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")

        tokens = self.preprocessor.remove_stopwords(tokens)
        return tokens

    def batch_segment(self, texts: list[str]) -> list[list[str]]:
        """Segment multiple texts.

        Args:
            texts: List of Chinese text strings.

        Returns:
            List of token lists.
        """
        return [self.segment(text) for text in texts]

    def add_words(self, words: list[str]) -> None:
        """Add custom words to the dictionary.

        Args:
            words: List of words to add.
        """
        for word in words:
            self._dictionary.add(word)

    def get_stats(self) -> dict:
        """Get segmenter statistics."""
        return {
            "strategy": self.strategy,
            "dictionary_size": len(self._dictionary),
            "max_word_len": self.max_word_len,
        }
