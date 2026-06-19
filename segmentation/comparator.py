"""
分词算法对比评估器

对比三种分词算法的性能：
1. jieba (词典DAG + HMM)
2. MaxMatch FMM/BMM/BiMM (最大匹配)
3. HMM + Viterbi (序列标注)

评估指标：
- 分词速度 (字/秒)
- 平均词数
- 唯一词数
- 词长分布
- 两两Jaccard相似度
- Dice系数
"""

import time
from collections import Counter

import pandas as pd

from segmentation.algorithm_jieba import JiebaSegmenter
from segmentation.algorithm_max_match import MaxMatchSegmenter
from segmentation.algorithm_dp import DPUnigramSegmenter
from utils.logger import logger


class SegmentationComparator:
    """Compare multiple segmentation algorithms on the same texts."""

    def __init__(self, sample_texts: list[str]):
        """
        Args:
            sample_texts: List of text strings to use for comparison.
        """
        self.texts = sample_texts

        # Initialize all three segmenters
        self.segmenters = {
            "jieba": JiebaSegmenter(mode="accurate"),
            "maxmatch_fmm": MaxMatchSegmenter(strategy="fmm"),
            "maxmatch_bmm": MaxMatchSegmenter(strategy="bmm"),
            "maxmatch_bimm": MaxMatchSegmenter(strategy="bimm"),
            "dp_unigram": DPUnigramSegmenter(),
        }

    def run_all(self) -> pd.DataFrame:
        """Run all segmenters on the sample texts and collect results.

        Returns:
            DataFrame with columns: algorithm, total_time, avg_time_ms,
            total_tokens, unique_tokens, tokens_per_text, avg_token_len.
        """
        results = []

        for name, segmenter in self.segmenters.items():
            logger.info(f"Running {name}...")
            all_tokens = []
            start = time.perf_counter()

            for text in self.texts:
                tokens = segmenter.segment(text)
                all_tokens.extend(tokens)

            elapsed = time.perf_counter() - start
            total_chars = sum(len(t) for t in all_tokens)

            results.append({
                "algorithm": name,
                "total_time_s": round(elapsed, 3),
                "avg_time_ms": round((elapsed / len(self.texts)) * 1000, 2),
                "total_tokens": len(all_tokens),
                "unique_tokens": len(set(all_tokens)),
                "tokens_per_text": round(len(all_tokens) / len(self.texts), 1),
                "avg_token_len": round(total_chars / len(all_tokens), 2) if all_tokens else 0,
                "chars_per_sec": round(total_chars / elapsed, 0) if elapsed > 0 else 0,
            })

        df = pd.DataFrame(results)
        logger.info(f"Comparison complete:\n{df.to_string()}")
        return df

    def compare_pairwise(self, algo_a: str, algo_b: str) -> dict:
        """Compute pairwise similarity metrics between two algorithms.

        Args:
            algo_a: First algorithm name.
            algo_b: Second algorithm name.

        Returns:
            Dict with jaccard_similarity and dice_coefficient.
        """
        seg_a = self.segmenters[algo_a]
        seg_b = self.segmenters[algo_b]

        all_a = Counter()
        all_b = Counter()

        for text in self.texts:
            all_a.update(seg_a.segment(text))
            all_b.update(seg_b.segment(text))

        set_a = set(all_a.keys())
        set_b = set(all_b.keys())

        intersection = set_a & set_b
        union = set_a | set_b

        jaccard = len(intersection) / len(union) if union else 0
        dice = (2 * len(intersection)) / (len(set_a) + len(set_b)) if (set_a or set_b) else 0

        return {
            "algorithm_a": algo_a,
            "algorithm_b": algo_b,
            "jaccard_similarity": round(jaccard, 4),
            "dice_coefficient": round(dice, 4),
            "shared_tokens": len(intersection),
            "tokens_only_in_a": len(set_a - set_b),
            "tokens_only_in_b": len(set_b - set_a),
        }

    def get_word_freq_comparison(self, top_n: int = 30) -> pd.DataFrame:
        """Compare top-N word frequencies across all algorithms.

        Args:
            top_n: Number of top words per algorithm.

        Returns:
            DataFrame with columns: algorithm, word, count, rank.
        """
        rows = []
        for name, segmenter in self.segmenters.items():
            counter = Counter()
            for text in self.texts:
                counter.update(segmenter.segment(text))
            for rank, (word, count) in enumerate(counter.most_common(top_n), 1):
                rows.append({
                    "algorithm": name,
                    "word": word,
                    "count": count,
                    "rank": rank,
                })
        return pd.DataFrame(rows)

    def get_token_length_distribution(self) -> pd.DataFrame:
        """Get word length distribution for each algorithm.

        Returns:
            DataFrame: algorithm × token_len → count.
        """
        rows = []
        for name, segmenter in self.segmenters.items():
            len_counter = Counter()
            for text in self.texts:
                for token in segmenter.segment(text):
                    len_counter[len(token)] += 1
            for length, count in sorted(len_counter.items()):
                rows.append({
                    "algorithm": name,
                    "token_length": length,
                    "count": count,
                })
        return pd.DataFrame(rows)
