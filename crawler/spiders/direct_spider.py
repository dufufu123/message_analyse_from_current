"""
DOM直采爬虫 (Direct Spider) v2 — 重写版

不使用 response.meta（Scrapy 2.16 会丢弃），改为 URL 反查上下文。
与 universal_spider (RSS模式) 完全独立，可并行运行。
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import scrapy

from crawler.items import WebPageItem
from crawler.direct_sites.configs import SITE_CONFIGS

logger = logging.getLogger(__name__)


class DirectSiteSpider(scrapy.Spider):
    """DOM直采爬虫。

    通过 start_urls 启动，用 _list_ctx 和 _article_urls 两个 dict
    存储 URL→上下文 映射，替代不可靠的 response.meta。
    """

    name = "direct"

    custom_settings = {
        "CONCURRENT_REQUESTS": 16,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
        "DOWNLOAD_DELAY": 0.2,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "DOWNLOAD_TIMEOUT": 15,
        "RETRY_TIMES": 2,
        "LOG_LEVEL": "INFO",
        "ROBOTSTXT_OBEY": False,
        "COOKIES_ENABLED": False,
        "OFFSITE_ENABLED": False,  # 禁止域名过滤（多站共用一个spider时必需）
    }

    PROGRESS_FILE = "data/direct_progress.json"
    PAGES_PER_RUN = 200  # 每轮每个入口URL翻多少页（IT之家有200+页内容）

    def __init__(self, site: str = None, max_articles: int = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_site = site
        self.max_articles_per_site = int(max_articles) if max_articles else 5000

        # 加载站点配置
        if site and site in SITE_CONFIGS:
            self._configs = {site: SITE_CONFIGS[site]}
        elif site:
            self._configs = {}
            logger.error(f"Unknown site: {site}")
        else:
            self._configs = dict(SITE_CONFIGS)

        # --- 加载翻页进度 ---
        self._progress: dict[str, int] = self._load_progress()

        # 上下文存储
        self._ctx: dict[str, dict] = {}
        self._article_links: dict[str, set] = {}
        self._list_page_count: dict[str, int] = {}
        self._article_count: dict[str, int] = {}

        # 注册初始列表页URL（从进度位置开始）
        for sk, config in self._configs.items():
            self._article_links[sk] = set()
            self._list_page_count[sk] = 0
            self._article_count[sk] = 0

            for start_url in config.get("start_urls", []):
                progress_key = f"{sk}|{start_url}"
                start_page = self._progress.get(progress_key, 0) + 1  # 从上次停的地方+1开始

                self._ctx[start_url] = {
                    "site_key": sk, "base_url": start_url,
                    "page_num": start_page, "is_article": False,
                    "start_page": start_page,
                }
                self.start_urls.append(start_url)

        logger.info(
            f"DirectSpider: {len(self._configs)} sites, {len(self.start_urls)} start URLs, "
            f"pages_per_run={self.PAGES_PER_RUN}"
        )

    # ================================================================
    # 进度持久化
    # ================================================================
    def _load_progress(self) -> dict[str, int]:
        """加载翻页进度文件。返回 {progress_key: last_page}。"""
        import json
        path = Path(self.PROGRESS_FILE)
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_progress(self) -> None:
        """保存翻页进度到文件。"""
        import json
        path = Path(self.PROGRESS_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        # 每个入口URL记录它翻到了第几页
        progress = {}
        for sk in self._configs:
            for start_url in self._configs[sk].get("start_urls", []):
                key = f"{sk}|{start_url}"
                # 用当前页数（start_page + pages_done）作为已完成的页码
                ctx = self._ctx.get(start_url, {})
                last = ctx.get("page_num", 0) - 1  # 减1因为page_num是当前要翻的页
                progress[key] = max(last, self._progress.get(key, -1))
        try:
            with open(path, "w") as f:
                json.dump(progress, f)
        except Exception as e:
            logger.warning(f"Failed to save progress: {e}")

    # ================================================================
    # 入口
    # ================================================================
    def parse(self, response):
        """Scrapy 默认回调——从 _ctx 反查上下文后分发。"""
        ctx = self._ctx.get(response.url)
        if not ctx:
            # 可能发生了重定向，用原始URL再试
            logger.debug(f"No ctx for {response.url}, skipping")
            return

        if ctx.get("is_article"):
            yield from self._parse_article(response, ctx["site_key"])
        else:
            yield from self._parse_list_page(response, ctx["site_key"],
                                              ctx["base_url"], ctx["page_num"])

    # ================================================================
    # 列表页解析
    # ================================================================
    def _parse_list_page(self, response, site_key: str, base_url: str, page_num: int):
        config = self._configs[site_key]
        self._list_page_count[site_key] += 1

        # 从 _ctx 获取本轮起始页码
        my_ctx = self._ctx.get(response.url, {})
        start_page = my_ctx.get("start_page", 1)

        # 提取文章链接
        article_pattern = re.compile(config["article_pattern"])
        exclude_patterns = [re.compile(p) for p in config.get("exclude_patterns", [])]
        new_links = 0

        for a in response.css("a::attr(href)").getall():
            if not a:
                continue
            full_url = urljoin(response.url, a.split("#")[0])
            if not article_pattern.search(full_url):
                continue
            if any(ep.search(full_url) for ep in exclude_patterns):
                continue
            if full_url not in self._article_links[site_key]:
                self._article_links[site_key].add(full_url)
                # 注册为文章URL，供 parse() 识别
                self._ctx[full_url] = {"site_key": site_key, "is_article": True}
                new_links += 1

        total = len(self._article_links[site_key])
        if page_num % 20 == 0:
            logger.info(
                f"[{site_key}] page #{page_num}: +{new_links} links "
                f"(total {total} discovered, {self._article_count[site_key]} crawled)"
            )

        # 翻页 — 每轮跑 PAGES_PER_RUN 页，从 start_page 开始
        max_articles = config.get("max_articles", self.max_articles_per_site)
        start_page = my_ctx.get("start_page", 1)
        max_page_this_run = start_page + self.PAGES_PER_RUN - 1

        if total < max_articles and page_num < max_page_this_run:
            next_url = self._find_next_page(response, config, base_url, page_num)
            if next_url:
                self._ctx[next_url] = {
                    "site_key": site_key, "base_url": base_url,
                    "page_num": page_num + 1, "is_article": False,
                    "start_page": start_page,
                }
                yield scrapy.Request(next_url, dont_filter=True)
        else:
            logger.info(f"[{site_key}] list done: {page_num} pages (start={start_page}), {total} links")

        # 发现新文章链接后开始抓文章（第一批100篇）
        if new_links > 0 and self._article_count[site_key] == 0:
            links = list(self._article_links[site_key])
            for u in links[:100]:
                yield scrapy.Request(u, dont_filter=True)

    # ================================================================
    # 文章页解析
    # ================================================================
    def _parse_article(self, response, site_key: str):
        config = self._configs[site_key]
        self._article_count[site_key] += 1
        count = self._article_count[site_key]
        sels = config["selectors"]

        title = self._css_first(response, sels.get("title", "title::text"))
        body = ""
        for sel in sels.get("body", "article").split(","):
            sel = sel.strip()
            try:
                parts = response.css(sel + " *::text").getall()
                if parts:
                    text = " ".join(p.strip() for p in parts if p.strip())
                    if len(text) > 100:
                        body = text
                        break
            except Exception:
                continue
        pub_time = self._css_first(response, sels.get("date", ""))

        if count % 200 == 0:
            logger.info(f"[{site_key}] crawled {count} articles")

        # 继续抓下一篇
        links = list(self._article_links[site_key])
        max_articles = config.get("max_articles", self.max_articles_per_site)
        if count < len(links) and count < max_articles:
            next_url = links[count]
            yield scrapy.Request(next_url, dont_filter=True)

        yield WebPageItem(
            url=response.url, title=title, raw_html=response.text,
            clean_text="", source_site=config.get("domain", site_key),
            category=config.get("category", "general"),
            publish_time=pub_time,
        )

    # ================================================================
    # 翻页
    # ================================================================
    def _find_next_page(self, response, config, base_url, current_page):
        pg = config.get("pagination", {})
        mode = pg.get("mode", "css")

        if mode == "css":
            for sel in pg.get("css", "").split(","):
                sel = sel.strip()
                try:
                    r = response.css(sel + "::attr(href)").get()
                    if r and r.strip():
                        return urljoin(response.url, r.strip())
                except Exception:
                    continue
            return None

        elif mode == "url_template":
            tpl = pg.get("template", "{base_url}/page/{page}")
            return tpl.replace("{base_url}", base_url.rstrip("/")).replace("{page}", str(current_page + 1))

        elif mode == "param":
            pn = pg.get("param_name", "page")
            step = pg.get("step", 1)
            first = pg.get("first_param_value", "0")
            if current_page == 1 and first:
                sep = "&" if "?" in base_url else "?"
                return f"{base_url}{sep}{pn}={first}"
            else:
                val = int(first or 1) + (current_page - 1) * step
                sep = "&" if "?" in response.url else "?"
                return f"{response.url}{sep}{pn}={val + step}"

        return None

    def _css_first(self, response, selectors: str) -> str:
        if not selectors:
            return ""
        for sel in selectors.split(","):
            sel = sel.strip()
            if not sel:
                continue
            try:
                r = response.css(sel).get()
                if r and r.strip():
                    return r.strip()
            except Exception:
                continue
        return ""

    # ================================================================
    # 统计
    # ================================================================
    def closed(self, reason):
        self._save_progress()  # 保存翻页进度，下次从这里继续
        from database.connection import get_db_stats
        stats = get_db_stats()
        logger.info(f"\n{'='*60}")
        logger.info(f"DirectSpider closed: {reason}")
        for sk in self._configs:
            logger.info(
                f"  {sk:25s}  pages={self._list_page_count.get(sk,0):>4d}  "
                f"links={len(self._article_links.get(sk,set())):>6d}  "
                f"crawled={self._article_count.get(sk,0):>5d}"
            )
        logger.info(f"  DB total: {stats['total_pages']:,}")
        logger.info(f"{'='*60}")
