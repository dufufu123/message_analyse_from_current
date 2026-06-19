"""
Scrapy Pipeline that stores WebPageItem records into SQLite.

Uses batch inserts for performance — accumulates items in memory
and flushes to the database on spider close or batch threshold.
"""

import logging

from database.models import WebPage, get_session
from utils.text_cleaner import clean_text

logger = logging.getLogger(__name__)


class SQLitePipeline:
    """Scrapy pipeline that persists WebPageItem instances to SQLite.

    Accumulates items in a batch list and bulk-inserts them
    when the spider closes or the batch size is reached.
    """

    BATCH_SIZE = 200

    def __init__(self):
        self.batch: list[WebPage] = []
        self.total_stored = 0
        self.total_skipped = 0

    def process_item(self, item, spider):
        """Process a single scraped item — insert into DB via batch."""
        # Clean the HTML to get plain text
        cleaned = clean_text(item.get("raw_html", ""))
        if not cleaned or len(cleaned) < 50:
            self.total_skipped += 1
            return item

        page = WebPage(
            url=item.get("url", ""),
            title=item.get("title", ""),
            raw_html=item.get("raw_html", ""),
            clean_text=cleaned,
            source_site=item.get("source_site", ""),
            category=item.get("category", ""),
            text_length=len(cleaned),
            processed=0,
        )

        # Try to parse publish_time if provided
        publish_time = item.get("publish_time")
        if publish_time:
            try:
                from datetime import datetime
                # Try common formats
                for fmt in [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d",
                ]:
                    try:
                        page.publish_time = datetime.strptime(
                            str(publish_time)[:19], fmt
                        )
                        break
                    except ValueError:
                        continue
            except Exception:
                pass

        self.batch.append(page)

        if len(self.batch) >= self.BATCH_SIZE:
            self._flush_batch()

        return item

    def _flush_batch(self):
        """Write accumulated items to the database."""
        if not self.batch:
            return
        try:
            with get_session() as session:
                for page in self.batch:
                    try:
                        session.add(page)
                        session.flush()
                    except Exception:
                        session.rollback()
                        self.total_skipped += 1
                        continue
                session.commit()
            self.total_stored += len(self.batch)
            logger.info(
                f"[Pipeline] Flushed {len(self.batch)} items → "
                f"total stored={self.total_stored}, skipped={self.total_skipped}"
            )
        except Exception as e:
            logger.error(f"[Pipeline] Batch flush failed: {e}")
        finally:
            self.batch.clear()

    def close_spider(self, spider):
        """Flush remaining items when the spider closes."""
        self._flush_batch()
        logger.info(
            f"[Pipeline] Spider '{spider.name}' finished. "
            f"Stored={self.total_stored}, Skipped={self.total_skipped}"
        )
