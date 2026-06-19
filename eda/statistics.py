"""
EDA Statistics computation module.
Queries the database and computes statistical summaries for visualization.
"""

import json
from collections import Counter
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import func

from database.models import WebPage, get_session
from config.settings import EDA_SAMPLE_SIZE
from utils.logger import logger


def load_dataframe(sample_size: int | None = None) -> pd.DataFrame:
    """Load web page records into a pandas DataFrame for analysis.

    Args:
        sample_size: Max rows to load. Defaults to EDA_SAMPLE_SIZE config.

    Returns:
        DataFrame with columns: id, url, title, text_length, source_site,
        category, crawl_time, publish_time, processed, sentiment_label, etc.
    """
    limit = sample_size or EDA_SAMPLE_SIZE
    with get_session() as session:
        rows = (
            session.query(WebPage)
            .filter(WebPage.clean_text != "")
            .limit(limit)
            .all()
        )

    data = []
    for r in rows:
        data.append({
            "id": r.id,
            "url": r.url,
            "title": r.title,
            "text_length": r.text_length,
            "source_site": r.source_site,
            "category": r.category,
            "crawl_time": r.crawl_time,
            "publish_time": r.publish_time,
            "processed": r.processed,
            "sentiment_label": r.sentiment_label,
            "sentiment_score": r.sentiment_score,
            "sensitivity_score": r.sensitivity_score,
            "harmful_score": r.harmful_score,
            "harmful_is_harmful": r.harmful_is_harmful,
        })

    df = pd.DataFrame(data)
    logger.info(f"Loaded {len(df)} records for EDA")
    return df


def site_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Count of pages per source site, sorted descending."""
    return (
        df.groupby("source_site")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )


def category_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Count of pages per category (news/forum/blog)."""
    return (
        df.groupby("category")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )


def text_length_stats(df: pd.DataFrame) -> dict:
    """Descriptive statistics for text_length."""
    stats = df["text_length"].describe()
    return stats.to_dict()


def text_length_by_source(df: pd.DataFrame) -> pd.DataFrame:
    """Mean text length grouped by source site."""
    return (
        df.groupby("source_site")["text_length"]
        .agg(["mean", "median", "std", "count"])
        .reset_index()
        .sort_values("mean", ascending=False)
    )


def publish_time_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Count of articles by publish date (daily)."""
    df = df.copy()
    df["pub_date"] = pd.to_datetime(df["publish_time"], errors="coerce")
    trend = df.groupby(df["pub_date"].dt.date).size().reset_index(name="count")
    trend.columns = ["date", "count"]
    return trend.sort_values("date")


def publish_hour_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Count of articles by hour of day (0–23)."""
    df = df.copy()
    df["hour"] = pd.to_datetime(df["publish_time"], errors="coerce").dt.hour
    return df.groupby("hour").size().reset_index(name="count")


def word_frequency_from_seg(df: pd.DataFrame, algorithm: str = "jieba", top_n: int = 50) -> pd.DataFrame:
    """Compute top-N word frequencies from stored segmentation JSON.

    Args:
        df: DataFrame with a 'seg' column (or id column for DB lookup).
        algorithm: 'jieba', 'maxmatch', or 'hmm'.
        top_n: Number of top words to return.

    Returns:
        DataFrame with columns: word, count.
    """
    counter = Counter()

    with get_session() as session:
        pages = (
            session.query(WebPage.seg_jieba, WebPage.seg_maxmatch, WebPage.seg_dp)
            .filter(WebPage.processed >= 1)
            .limit(10000)
            .all()
        )

    col_map = {"jieba": 0, "maxmatch": 1, "dp": 2}
    col_idx = col_map.get(algorithm, 0)

    for row in pages:
        seg_json = row[col_idx]
        if seg_json:
            try:
                tokens = json.loads(seg_json)
                counter.update(tokens)
            except (json.JSONDecodeError, TypeError):
                pass

    freq = pd.DataFrame(counter.most_common(top_n), columns=["word", "count"])
    return freq


def sentiment_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Count by sentiment label."""
    return (
        df.groupby("sentiment_label")
        .size()
        .reset_index(name="count")
    )


def sensitivity_score_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Distribution of sensitivity scores."""
    return df["sensitivity_score"].describe().to_dict()


def harmful_site_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Harmful content rate by source site."""
    stats = (
        df.groupby("source_site")
        .agg(
            total=("harmful_is_harmful", "count"),
            harmful=("harmful_is_harmful", "sum"),
        )
        .reset_index()
    )
    stats["harmful_rate"] = stats["harmful"] / stats["total"].replace(0, 1)
    return stats.sort_values("harmful_rate", ascending=False)


def missing_values_report(df: pd.DataFrame) -> pd.DataFrame:
    """Report missing/null counts per column."""
    missing = df.isnull().sum().reset_index()
    missing.columns = ["column", "missing_count"]
    missing["missing_pct"] = (missing["missing_count"] / len(df)) * 100
    return missing.sort_values("missing_count", ascending=False)
