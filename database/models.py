"""
SQLAlchemy ORM models for the Text Content Security System.

Defines the WebPage table that serves as the central data store
for all crawled, segmented, and analyzed content.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    TIMESTAMP,
    Index,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config.settings import DATABASE_URL


class Base(DeclarativeBase):
    pass


class WebPage(Base):
    """Represents one crawled web page and its analysis results."""

    __tablename__ = "web_pages"

    # ---- Primary key ----
    id = Column(Integer, primary_key=True, autoincrement=True)

    # ---- Crawl metadata ----
    url = Column(String(2048), nullable=False, unique=True, comment="Page URL")
    title = Column(String(1024), default="", comment="Page title")
    raw_html = Column(Text, default="", comment="Original HTML content")
    clean_text = Column(Text, default="", comment="Cleaned plain text after HTML stripping")
    source_site = Column(String(256), nullable=False, index=True, comment="Source website domain")
    category = Column(String(64), default="", index=True, comment="Content category: news/forum/blog")
    crawl_time = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        comment="When the page was crawled",
    )
    publish_time = Column(TIMESTAMP(timezone=True), nullable=True, comment="Original publish time")
    text_length = Column(Integer, default=0, comment="Length of clean_text in characters")

    # ---- Segmentation results (JSON strings of token lists) ----
    seg_jieba = Column(Text, default="", comment="JSON: tokens from jieba segmentation")
    seg_maxmatch = Column(Text, default="", comment="JSON: tokens from max-match segmentation")
    seg_dp = Column(Text, default="", comment="JSON: tokens from DP unigram segmentation")

    # ---- Sensitivity analysis ----
    sensitivity_score = Column(Float, default=0.0, comment="Sensitivity score 0.0–1.0")
    sensitivity_flags = Column(Text, default="", comment="JSON: list of flagged categories")

    # ---- Sentiment analysis ----
    sentiment_score = Column(Float, default=0.0, comment="Sentiment score -1.0–1.0")
    sentiment_label = Column(
        String(16), default="", comment="Sentiment label: positive/negative/neutral"
    )

    # ---- Harmful content detection ----
    harmful_score = Column(Float, default=0.0, comment="Harmful content score 0.0–1.0")
    harmful_flags = Column(Text, default="", comment="JSON: list of harmful categories detected")
    harmful_is_harmful = Column(Integer, default=0, comment="0=safe, 1=harmful")

    # ---- Processing status ----
    processed = Column(
        Integer, default=0, index=True, comment="0=raw, 1=segmented, 2=analyzed"
    )
    analysis_seg_source = Column(
        String(16), default="jieba", comment="Which seg algorithm's tokens were used for analysis"
    )
    sentiment_details = Column(Text, default="", comment="JSON: detailed sentiment result")
    sensitivity_details = Column(Text, default="", comment="JSON: detailed sensitivity result")
    harmful_details = Column(Text, default="", comment="JSON: detailed harmful detection result")

    # ---- Indexes ----
    __table_args__ = (
        Index("idx_source_site", "source_site"),
        Index("idx_category", "category"),
        Index("idx_processed", "processed"),
        Index("idx_harmful", "harmful_is_harmful"),
        Index("idx_sentiment", "sentiment_label"),
    )

    def set_seg_tokens(self, algorithm: str, tokens: list[str]) -> None:
        """Store segmentation tokens as JSON."""
        if algorithm == "jieba":
            self.seg_jieba = json.dumps(tokens, ensure_ascii=False)
        elif algorithm == "maxmatch":
            self.seg_maxmatch = json.dumps(tokens, ensure_ascii=False)
        elif algorithm == "dp":
            self.seg_dp = json.dumps(tokens, ensure_ascii=False)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

    def get_seg_tokens(self, algorithm: str) -> list[str]:
        """Retrieve segmentation tokens from JSON storage."""
        if algorithm == "jieba":
            raw = self.seg_jieba
        elif algorithm == "maxmatch":
            raw = self.seg_maxmatch
        elif algorithm == "dp":
            raw = self.seg_dp
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")
        if not raw:
            return []
        return json.loads(raw)

    def set_sensitivity_flags(self, flags: list[str]) -> None:
        """Store sensitivity flag categories as JSON."""
        self.sensitivity_flags = json.dumps(flags, ensure_ascii=False)

    def get_sensitivity_flags(self) -> list[str]:
        """Retrieve sensitivity flag categories."""
        if not self.sensitivity_flags:
            return []
        return json.loads(self.sensitivity_flags)

    def set_harmful_flags(self, flags: list[str]) -> None:
        """Store harmful content flag categories as JSON."""
        self.harmful_flags = json.dumps(flags, ensure_ascii=False)

    def get_harmful_flags(self) -> list[str]:
        """Retrieve harmful content flag categories."""
        if not self.harmful_flags:
            return []
        return json.loads(self.harmful_flags)

    def __repr__(self) -> str:
        return (
            f"<WebPage(id={self.id}, source='{self.source_site}', "
            f"title='{self.title[:50] if self.title else ''}', "
            f"processed={self.processed})>"
        )


# ---- Engine and session factory ----
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create the SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            echo=False,
            connect_args={"check_same_thread": False},  # Required for SQLite
            pool_pre_ping=True,
        )
    return _engine


def get_session() -> Session:
    """Create a new database session.

    Usage:
        with get_session() as session:
            page = session.query(WebPage).first()
    """
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return _SessionLocal()


def init_database() -> None:
    """Create all tables in the database. Safe to call multiple times."""
    engine = get_engine()
    Base.metadata.create_all(engine)
