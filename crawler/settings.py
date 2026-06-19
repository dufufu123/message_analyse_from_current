"""
Scrapy settings for the text content security crawler project.
"""

from config.settings import CRAWLER_SETTINGS

# ---- Spider settings ----
BOT_NAME = "text_security_crawler"
SPIDER_MODULES = ["crawler.spiders"]
NEWSPIDER_MODULE = "crawler.spiders"

# ---- Concurrency & politeness ----
CONCURRENT_REQUESTS = CRAWLER_SETTINGS["concurrent_requests"]
CONCURRENT_REQUESTS_PER_DOMAIN = 8
DOWNLOAD_DELAY = CRAWLER_SETTINGS["download_delay"]
RANDOMIZE_DOWNLOAD_DELAY = CRAWLER_SETTINGS["randomize_download_delay"]

# ---- Auto-throttle ----
AUTOTHROTTLE_ENABLED = CRAWLER_SETTINGS["autothrottle_enabled"]
AUTOTHROTTLE_START_DELAY = CRAWLER_SETTINGS["autothrottle_start_delay"]
AUTOTHROTTLE_MAX_DELAY = CRAWLER_SETTINGS["autothrottle_max_delay"]
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0

# ---- Retry ----
RETRY_ENABLED = True
RETRY_TIMES = CRAWLER_SETTINGS["retry_times"]
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429]

# ---- Timeout ----
DOWNLOAD_TIMEOUT = CRAWLER_SETTINGS["download_timeout"]

# ---- Robots.txt ----
ROBOTSTXT_OBEY = CRAWLER_SETTINGS["obey_robots_txt"]

# ---- Pipelines ----
ITEM_PIPELINES = {
    "crawler.pipelines.SQLitePipeline": 300,
}

# ---- Middlewares ----
DOWNLOADER_MIDDLEWARES = {
    "crawler.middlewares.UserAgentRotatorMiddleware": 400,
    # "crawler.middlewares.ProxyMiddleware": 500,
}

# ---- Cookies ----
COOKIES_ENABLED = False  # Disable cookies for cleaner scraping

# ---- Logging ----
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATEFORMAT = "%Y-%m-%d %H:%M:%S"

# ---- Feed exports ----
FEED_EXPORT_ENCODING = "utf-8"

# ---- Reactor ----
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
