"""
分词算法1：基于 jieba 的中文分词器

支持三种模式：
- 精确模式 (accurate)：最精确的分词，适合文本分析
- 全模式 (full)：把所有可能的词都扫描出来，速度快但不能解决歧义
- 搜索引擎模式 (search)：在精确模式基础上对长词再次切分，提高召回率

底层原理：基于前缀词典的词图扫描 + HMM (隐马尔可夫模型) 未登录词识别
"""

from typing import Literal

import jieba

from segmentation.preprocessor import TextPreprocessor


class JiebaSegmenter:
    """Chinese word segmentation using the jieba library.

    jieba algorithm:
      1. Build a prefix dictionary from the vocabulary
      2. Construct a DAG (Directed Acyclic Graph) for all possible segmentations
      3. Find the most probable path using dynamic programming
      4. For unknown words, use HMM with Viterbi decoding
    """

    def __init__(
        self,
        mode: Literal["accurate", "full", "search"] = "accurate",
        preprocessor: TextPreprocessor | None = None,
    ):
        """
        Args:
            mode: Segmentation mode — 'accurate', 'full', or 'search'.
            preprocessor: Optional TextPreprocessor instance.
        """
        self.mode = mode
        self.preprocessor = preprocessor or TextPreprocessor()

        # Enable parallel processing for speed
        jieba.setLogLevel(20)  # Suppress debug logs

    @property
    def name(self) -> str:
        return f"jieba({self.mode})"

    def segment(self, text: str) -> list[str]:
        """Segment a single text string.

        Args:
            text: Chinese text to segment.

        Returns:
            List of word tokens.
        """
        text = self.preprocessor.preprocess(text)

        if self.mode == "accurate":
            tokens = list(jieba.cut(text, cut_all=False))
        elif self.mode == "full":
            tokens = list(jieba.cut(text, cut_all=True))
        elif self.mode == "search":
            tokens = list(jieba.cut_for_search(text))
        else:
            tokens = list(jieba.cut(text, cut_all=False))

        # Clean up: strip whitespace, filter empty
        tokens = [t.strip() for t in tokens if t.strip()]
        tokens = self.preprocessor.remove_stopwords(tokens)

        return tokens

    def batch_segment(self, texts: list[str]) -> list[list[str]]:
        """Segment multiple texts.

        Args:
            texts: List of Chinese text strings.

        Returns:
            List of token lists, one per input text.
        """
        return [self.segment(text) for text in texts]

    def add_words(self, words: list[str]) -> None:
        """Add custom words to the jieba dictionary.

        Args:
            words: List of words to add.
        """
        for word in words:
            jieba.add_word(word)
