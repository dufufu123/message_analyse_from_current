"""
Database connection helpers and common query functions.
"""

from sqlalchemy import func, text

from database.models import WebPage, get_session, get_engine


def get_db_stats() -> dict:
    """Get overall database statistics for the dashboard.

    Returns:
        Dict with keys: total_pages, segmented_count, analyzed_count,
        harmful_count, positive_count, negative_count, neutral_count.
    """
    with get_session() as session:
        total = session.query(func.count(WebPage.id)).scalar() or 0
        segmented = (
            session.query(func.count(WebPage.id))
            .filter(WebPage.processed >= 1)
            .scalar()
            or 0
        )
        analyzed = (
            session.query(func.count(WebPage.id))
            .filter(WebPage.processed >= 2)
            .scalar()
            or 0
        )
        harmful = (
            session.query(func.count(WebPage.id))
            .filter(WebPage.harmful_is_harmful == 1)
            .scalar()
            or 0
        )
        positive = (
            session.query(func.count(WebPage.id))
            .filter(WebPage.sentiment_label == "positive")
            .scalar()
            or 0
        )
        negative = (
            session.query(func.count(WebPage.id))
            .filter(WebPage.sentiment_label == "negative")
            .scalar()
            or 0
        )
        neutral = (
            session.query(func.count(WebPage.id))
            .filter(WebPage.sentiment_label == "neutral")
            .scalar()
            or 0
        )

    return {
        "total_pages": total,
        "segmented_count": segmented,
        "analyzed_count": analyzed,
        "harmful_count": harmful,
        "positive_count": positive,
        "negative_count": negative,
        "neutral_count": neutral,
    }


def get_source_site_stats() -> list[dict]:
    """Get record counts grouped by source site.

    Returns:
        List of dicts with source_site and count.
    """
    with get_session() as session:
        results = (
            session.query(
                WebPage.source_site,
                func.count(WebPage.id).label("count"),
            )
            .group_by(WebPage.source_site)
            .order_by(func.count(WebPage.id).desc())
            .all()
        )
    return [{"source_site": r[0], "count": r[1]} for r in results]


def get_processed_pages(limit: int = 1000, offset: int = 0) -> list[WebPage]:
    """Get pages that have been analyzed (processed >= 2).

    Args:
        limit: Maximum number of pages to return.
        offset: Number of pages to skip.

    Returns:
        List of WebPage objects.
    """
    with get_session() as session:
        return (
            session.query(WebPage)
            .filter(WebPage.processed >= 2)
            .order_by(WebPage.id.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )


def get_unprocessed_pages(batch_size: int = 500) -> list[WebPage]:
    """Get pages that haven't been segmented yet (processed = 0).

    Args:
        batch_size: Number of pages to fetch.

    Returns:
        List of WebPage objects with clean_text populated.
    """
    with get_session() as session:
        return (
            session.query(WebPage)
            .filter(WebPage.processed == 0, WebPage.clean_text != "")
            .limit(batch_size)
            .all()
        )
