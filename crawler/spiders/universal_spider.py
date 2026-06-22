"""
通用文章爬虫 (Universal Article Spider)

用法：
    scrapy crawl universal -a site=cnblogs -a max_pages=1000
    或通过 run_crawler.py 启动

工作流程：
    1. 从 link_discovery 生成的 JSON 加载已发现URL
    2. 填入 start_urls → Scrapy 自动调度请求
    3. parse_article 提取标题/正文/日期 → Pipeline → SQLite
"""

import json
import logging
from pathlib import Path
from typing import Optional

import scrapy

from crawler.items import WebPageItem
from crawler.site_profiles import SITE_PROFILES

logger = logging.getLogger(__name__)

DISCOVERED_URLS_FILE = "data/raw/discovered_urls.json"


class UniversalArticleSpider(scrapy.Spider):
    """通用文章爬虫 — 从已发现的URL列表抓取文章正文。"""

    name = "universal"

    custom_settings = {
        "CONCURRENT_REQUESTS": 16,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "DOWNLOAD_TIMEOUT": 15,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1,
        "AUTOTHROTTLE_MAX_DELAY": 5,
        "LOG_LEVEL": "INFO",
    }

    def __init__(self, site=None, max_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.target_site = site
        self.max_pages = int(max_pages) if max_pages else 20000

        # 加载URL到 start_urls（Scrapy 核心机制，最可靠）
        self._load_start_urls()

        self._crawled = 0
        self._failed = 0
        self._stored = 0

        logger.info(
            f"Spider initialized: site={self.target_site or 'all'}, "
            f"start_urls={len(self.start_urls)}, max_pages={self.max_pages}"
        )

    def _load_start_urls(self):
        """从JSON文件加载URL，自动过滤DB中已存在的URL（去重）。"""
        url_path = Path(DISCOVERED_URLS_FILE)
        if not url_path.exists():
            logger.error(f"URL file not found: {DISCOVERED_URLS_FILE}")
            logger.error("Run: python crawler/run_crawler.py discover")
            self.start_urls = []
            return

        with open(url_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sites_data = data.get("sites", {})

        # 收集所有候选URL
        if self.target_site and self.target_site in sites_data:
            candidate_urls = sites_data[self.target_site].get("urls", [])[:self.max_pages]
        else:
            candidate_urls = []
            for site_key, site_data in sites_data.items():
                urls = site_data.get("urls", [])
                candidate_urls.extend(urls[:self.max_pages])

        total_candidates = len(candidate_urls)

        # 批量查询DB中已存在的URL，只保留新的
        from database.models import WebPage, get_session, get_engine


        existing = set()
        # 分批查询，每次最多10000个URL
        batch_size = 5000
        with get_session() as session:
            for i in range(0, len(candidate_urls), batch_size):
                batch = candidate_urls[i:i + batch_size]
                result = (
                    session.query(WebPage.url)
                    .filter(WebPage.url.in_(batch))
                    .all()
                )
                existing.update(r[0] for r in result)

        new_urls = [u for u in candidate_urls if u not in existing]
        skipped = total_candidates - len(new_urls)
        self.start_urls = new_urls

        logger.info(
            f"URL dedup: {total_candidates} candidates → "
            f"{skipped} already in DB → {len(new_urls)} new to crawl"
        )

        # 给每个URL打上 site_key 标记
        self._url_site_map = {}
        for site_key, site_data in sites_data.items():
            for u in site_data.get("urls", [])[:self.max_pages]:
                if u in new_urls:  # 只给确实要抓的URL建映射
                    self._url_site_map[u] = site_key

    # ----------------------------------------------------------------
    # 核心解析
    # ----------------------------------------------------------------
    def parse(self, response):
        """解析文章页面（start_urls 默认回调）。"""
        # 从 URL 推断站点
        site_key = self._url_site_map.get(response.url, "")
        if not site_key:
            # 通过域名匹配
            for sk, profile in SITE_PROFILES.items():
                domain = profile.get("domain", "")
                if domain and domain in response.url:
                    site_key = sk
                    break
        if not site_key:
            site_key = "unknown"

        profile = SITE_PROFILES.get(site_key, {})
        self._crawled += 1

        # ---- 提取标题 ----
        title = self._extract_title(response, profile)

        # ---- 提取正文 ----
        body_text = self._extract_body(response, profile)

        # ---- 提取日期 ----
        publish_time = self._extract_date(response, profile)

        # ---- 进度日志 ----
        if self._crawled % 100 == 0:
            logger.info(
                f"[{site_key}] Crawled {self._crawled} pages "
                f"(stored={self._stored}, failed={self._failed})"
            )

        yield WebPageItem(
            url=response.url,
            title=title,
            raw_html=response.text,
            clean_text="",  # Pipeline 清洗
            source_site=site_key,
            category=profile.get("category", "general"),
            publish_time=publish_time,
        )

    def _extract_title(self, response, profile: dict) -> str:
        """用站点配置的选择器提取标题。"""
        selectors = profile.get("title_selector", "title::text")
        for sel in selectors.split(","):
            sel = sel.strip()
            if not sel:
                continue
            try:
                result = response.css(sel).get()
                if result and result.strip():
                    return result.strip()
            except Exception:
                continue
        return ""

    def _extract_body(self, response, profile: dict) -> str:
        """用站点配置的选择器提取正文。"""
        selectors = profile.get("body_selector", "article")
        for sel in selectors.split(","):
            sel = sel.strip()
            if not sel:
                continue
            try:
                parts = response.css(sel + " *::text").getall()
                if parts:
                    text = " ".join(p.strip() for p in parts if p.strip())
                    if len(text) > 100:
                        return text
            except Exception:
                continue

        # 兜底：取 body 全部文本
        try:
            parts = response.css("body *::text").getall()
            return " ".join(p.strip() for p in parts if p.strip())
        except Exception:
            return ""

    def _extract_date(self, response, profile: dict) -> Optional[str]:
        """用站点配置的选择器提取发布日期。"""
        selectors = profile.get("date_selector", "")
        if not selectors:
            return None
        for sel in selectors.split(","):
            sel = sel.strip()
            if not sel:
                continue
            try:
                result = response.css(sel).get()
                if result and result.strip():
                    return result.strip()[:19]
            except Exception:
                continue
        return None

    # ----------------------------------------------------------------
    # 错误处理
    # ----------------------------------------------------------------
    def handle_error(self, failure):
        """请求失败回调。"""
        self._failed += 1
        logger.debug(f"Request failed: {failure.request.url}")

    # ----------------------------------------------------------------
    # 收尾统计
    # ----------------------------------------------------------------
    def closed(self, reason):
        from database.connection import get_db_stats
        stats = get_db_stats()
        logger.info(f"\n{'='*60}")
        logger.info(f"Spider '{self.name}' closed: {reason}")
        logger.info(f"{'='*60}")
        logger.info(f"  Requests sent:      {self._crawled}")
        logger.info(f"  Requests failed:    {self._failed}")
        logger.info(f"  DB total pages:     {stats['total_pages']}")
        logger.info(f"{'='*60}")
