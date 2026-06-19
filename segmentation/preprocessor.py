"""
Text preprocessor for Chinese word segmentation.

Pipeline: HTML cleaning → whitespace normalization → stopword removal → output.
"""

import re
from pathlib import Path

from config.settings import PAUSE_WORDS_FILE
from utils.logger import logger


class TextPreprocessor:
    """Preprocess Chinese text before segmentation.

    Handles: HTML tag removal, whitespace normalization,
    full-width character conversion, and stopword filtering.
    """

    def __init__(self, stopwords_file: str | Path | None = None):
        self._stopwords: set[str] = set()
        if stopwords_file is None:
            stopwords_file = PAUSE_WORDS_FILE
        self._load_stopwords(stopwords_file)

    def _load_stopwords(self, path: str | Path) -> None:
        """Load stopwords from file, one word per line."""
        path = Path(path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word and not word.startswith("#"):
                        self._stopwords.add(word)
            logger.info(f"Loaded {len(self._stopwords)} stopwords from {path}")
        else:
            logger.warning(f"Stopwords file not found: {path}")

    def is_chinese_char(self, ch: str) -> bool:
        """Check if character is in the CJK Unified Ideographs range."""
        return "一" <= ch <= "鿿"

    def remove_stopwords(self, tokens: list[str]) -> list[str]:
        """Filter out stopwords and single-char non-Chinese tokens.

        Args:
            tokens: List of word tokens.

        Returns:
            Filtered token list.
        """
        result = []
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            if token in self._stopwords:
                continue
            # Keep Chinese chars, meaningful multi-char tokens
            if len(token) == 1 and not self.is_chinese_char(token):
                continue
            result.append(token)
        return result

    def normalize_text(self, text: str) -> str:
        """Normalize text: full-width → half-width, collapse whitespace.

        Args:
            text: Raw text input.

        Returns:
            Normalized text string.
        """
        # full-width digits to half-width
        fwd = "０１２３４５６７８９"
        hwd = "0123456789"
        trans = str.maketrans(fwd, hwd)
        text = text.translate(trans)

        # full-width letters to half-width
        fw_upper = "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
        hw_upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        trans = str.maketrans(fw_upper, hw_upper)
        text = text.translate(trans)

        fw_lower = "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
        hw_lower = "abcdefghijklmnopqrstuvwxyz"
        trans = str.maketrans(fw_lower, hw_lower)
        text = text.translate(trans)

        # collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def preprocess(self, text: str) -> str:
        """Full preprocessing pipeline: normalize → ready for segmentation.

        Args:
            text: Raw or cleaned text.

        Returns:
            Normalized text string suitable for tokenization.
        """
        text = self.normalize_text(text)
        return text
