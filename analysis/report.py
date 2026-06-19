"""
分析报告生成器

汇总文本分析的各项结果，生成结构化的分析报告。
"""

import json
from datetime import datetime, timezone
from typing import Any

from database.models import WebPage, get_session
from analysis.sensitivity import SensitivityDetector
from analysis.sentiment import SentimentAnalyzer
from analysis.harmful_detector import HarmfulDetector
from segmentation.algorithm_jieba import JiebaSegmenter
from segmentation.algorithm_max_match import MaxMatchSegmenter
from segmentation.algorithm_dp import DPUnigramSegmenter
from utils.logger import logger


class BatchProcessor:
    """Runs the full pipeline: segmentation → analysis → database update.

    Processes pages in batches from the database.
    """

    BATCH_SIZE = 200

    def __init__(self):
        logger.info("Initializing BatchProcessor...")

        # Segmenters
        logger.info("Loading segmenters...")
        self.jieba_seg = JiebaSegmenter(mode="accurate")
        self.maxmatch_seg = MaxMatchSegmenter(strategy="bimm")
        self.dp_seg = DPUnigramSegmenter()

        # Analyzers
        logger.info("Loading analyzers...")
        self.sensitivity_detector = SensitivityDetector()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.harmful_detector = HarmfulDetector()

        self._stats = {
            "segmented": 0,
            "analyzed": 0,
            "errors": 0,
        }

    def process_all(self, max_pages: int | None = None) -> dict:
        """Run the full pipeline on all unprocessed pages.

        Args:
            max_pages: Optional limit for testing.

        Returns:
            Dict with processing statistics.
        """
        total = 0

        while True:
            with get_session() as session:
                pages = (
                    session.query(WebPage)
                    .filter(WebPage.processed < 2, WebPage.clean_text != "")
                    .limit(self.BATCH_SIZE)
                    .all()
                )

            if not pages:
                break

            self._process_batch(pages)
            total += len(pages)
            logger.info(
                f"Progress: {total} pages processed "
                f"(segged={self._stats['segmented']}, "
                f"analyzed={self._stats['analyzed']}, "
                f"errors={self._stats['errors']})"
            )

            if max_pages and total >= max_pages:
                break

        return self._stats

    def _process_batch(self, pages: list[WebPage]) -> None:
        """Process a batch of pages: segment → analyze → save.

        Args:
            pages: List of WebPage ORM instances.
        """
        texts = [page.clean_text for page in pages]

        # Step 1: Segmentation (all 3 algorithms)
        jieba_results = self.jieba_seg.batch_segment(texts)
        mm_results = self.maxmatch_seg.batch_segment(texts)
        dp_results = self.dp_seg.batch_segment(texts)

        # Step 2: Analysis — 使用 jieba 分词结果（tokens）而非原始文本
        sensitivity_results = self.sensitivity_detector.batch_detect(jieba_results)
        sentiment_results = self.sentiment_analyzer.batch_analyze(jieba_results)
        harmful_results = self.harmful_detector.batch_detect(jieba_results, texts)
        #                                        jieba tokens ──┘          └── raw text for regex

        # Step 3: Update database
        with get_session() as session:
            for i, page in enumerate(pages):
                try:
                    # Segmentation results
                    page.set_seg_tokens("jieba", jieba_results[i])
                    page.set_seg_tokens("maxmatch", mm_results[i])
                    page.set_seg_tokens("dp", dp_results[i])
                    page.processed = 1

                    # Sensitivity
                    sr = sensitivity_results[i]
                    page.sensitivity_score = sr.score
                    page.sensitivity_flags = json.dumps(sr.flags, ensure_ascii=False)
                    page.sensitivity_details = json.dumps(sr.to_dict(), ensure_ascii=False)

                    # Sentiment
                    sent = sentiment_results[i]
                    page.sentiment_score = sent.score
                    page.sentiment_label = sent.label
                    page.sentiment_details = json.dumps(sent.to_dict(), ensure_ascii=False)

                    # Harmful
                    hr = harmful_results[i]
                    page.harmful_score = hr.score
                    page.harmful_flags = json.dumps(hr.flags, ensure_ascii=False)
                    page.harmful_is_harmful = 1 if hr.is_harmful else 0
                    page.harmful_details = json.dumps(hr.to_dict(), ensure_ascii=False)

                    page.analysis_seg_source = "jieba"
                    page.processed = 2

                    session.add(page)
                    self._stats["analyzed"] += 1

                except Exception as e:
                    self._stats["errors"] += 1
                    logger.error(f"Error processing page {page.id}: {e}")
                    continue

            session.commit()

        self._stats["segmented"] += len(pages)


def generate_summary_report() -> dict[str, Any]:
    """Generate a summary report of all analysis results.

    Returns:
        Dict containing aggregated statistics.
    """
    from database.connection import get_db_stats, get_source_site_stats

    basic_stats = get_db_stats()
    source_stats = get_source_site_stats()

    with get_session() as session:
        from sqlalchemy import func
        avg_sensitivity = (
            session.query(func.avg(WebPage.sensitivity_score))
            .filter(WebPage.processed >= 2)
            .scalar()
        ) or 0.0
        avg_harmful = (
            session.query(func.avg(WebPage.harmful_score))
            .filter(WebPage.processed >= 2)
            .scalar()
        ) or 0.0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "basic_stats": basic_stats,
        "source_stats": source_stats,
        "avg_sensitivity_score": round(float(avg_sensitivity), 4),
        "avg_harmful_score": round(float(avg_harmful), 4),
        "sources": source_stats,
    }
