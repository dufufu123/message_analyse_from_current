"""
Scrapy Item definitions for the text content security crawler.
"""

import scrapy


class WebPageItem(scrapy.Item):
    """Represents a crawled web page before it enters the pipeline.

    Uses scrapy.Item (dict-like) for compatibility with the Pipeline
    and Scrapy's internal item processing.
    """

    url = scrapy.Field()
    title = scrapy.Field()
    raw_html = scrapy.Field()
    clean_text = scrapy.Field()
    source_site = scrapy.Field()
    category = scrapy.Field()
    publish_time = scrapy.Field()
