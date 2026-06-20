"""
链接发现模块 — 从RSS/Atom Feed、Sitemap和首页收集文章URL

工作流程：
  1. 优先从 RSS/Atom Feed 获取文章链接（最稳定）
  2. 如果 RSS 不可用，尝试解析 sitemap.xml
  3. 最后兜底：从首页抓取符合 article_link_pattern 的链接

输出：每个站点的去重URL列表，供 universal_spider 爬取正文使用
"""

import re
import json
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from crawler.site_profiles import SITE_PROFILES, SITE_LIST, DEFAULT_PER_SITE_LIMIT
from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

# 输出文件
DISCOVERED_URLS_FILE = DATA_DIR / "raw" / "discovered_urls.json"
# 确保目录存在
DISCOVERED_URLS_FILE.parent.mkdir(parents=True, exist_ok=True)

# 请求头
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class LinkDiscoverer:
    """从多种来源发现文章URL"""

    def __init__(self, per_site_limit: int = DEFAULT_PER_SITE_LIMIT):
        self.per_site_limit = per_site_limit
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.timeout = 15

    # ------------------------------------------------------------
    # 方法1：RSS/Atom Feed 解析（最稳定）
    # ------------------------------------------------------------
    def _discover_from_rss(self, feed_url: str) -> list[str]:
        """从RSS/Atom Feed提取文章URL列表。

        不使用feedparser库（避免依赖），直接解析XML：
        RSS 2.0: <item><link>...</link></item>
        Atom:    <entry><link href="..."/></entry>
        """
        urls = []
        try:
            resp = self.session.get(feed_url, timeout=20)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "xml")

            # RSS 2.0
            for item in soup.find_all("item"):
                link = item.find("link")
                if link and link.text:
                    urls.append(link.text.strip())

            # Atom
            if not urls:
                for entry in soup.find_all("entry"):
                    link = entry.find("link")
                    if link:
                        href = link.get("href", "")
                        if href:
                            urls.append(href.strip())
                    # Atom may also have <id> tag with URL
                    if not link:
                        id_tag = entry.find("id")
                        if id_tag and id_tag.text and id_tag.text.startswith("http"):
                            urls.append(id_tag.text.strip())

            logger.info(f"  RSS feed '{feed_url}': found {len(urls)} links")
        except requests.RequestException as e:
            logger.warning(f"  RSS feed '{feed_url}' failed: {e}")
        except Exception as e:
            logger.warning(f"  RSS feed '{feed_url}' parse error: {e}")

        return urls

    # ------------------------------------------------------------
    # 方法2：Sitemap 解析
    # ------------------------------------------------------------
    def _discover_from_sitemap(self, sitemap_url: str) -> list[str]:
        """从sitemap.xml提取URL列表。

        支持：
        - 标准sitemap: <url><loc>...</loc></url>
        - Sitemap索引: <sitemapindex><sitemap><loc>...</loc></sitem></sitemapindex>
        """
        urls = []
        try:
            resp = self.session.get(sitemap_url, timeout=20)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "xml")

            # sitemap index → 递归
            sitemap_tags = soup.find_all("sitemap")
            for sm in sitemap_tags:
                loc = sm.find("loc")
                if loc and loc.text:
                    sub_urls = self._discover_from_sitemap(loc.text.strip())
                    urls.extend(sub_urls)
                    if len(urls) >= self.per_site_limit:
                        break

            # 标准 URL 条目
            for url_tag in soup.find_all("url"):
                loc = url_tag.find("loc")
                if loc and loc.text:
                    urls.append(loc.text.strip())
                    if len(urls) >= self.per_site_limit:
                        break

            logger.info(f"  Sitemap '{sitemap_url}': found {len(urls)} links")
        except requests.RequestException as e:
            logger.warning(f"  Sitemap '{sitemap_url}' failed: {e}")
        except Exception as e:
            logger.warning(f"  Sitemap '{sitemap_url}' parse error: {e}")

        return urls

    # ------------------------------------------------------------
    # 方法3：首页抓取链接（兜底）
    # ------------------------------------------------------------
    def _discover_from_homepage(
        self, start_url: str, link_pattern: str
    ) -> list[str]:
        """从首页HTML中抓取匹配 pattern 的文章链接。

        Args:
            start_url: 首页URL。
            link_pattern: 用于匹配文章链接的正则表达式。

        Returns:
            去重的文章URL列表。
        """
        urls = set()
        if not link_pattern:
            return list(urls)

        try:
            resp = self.session.get(start_url, timeout=20)
            # 优先 UTF-8，兜底 apparent_encoding
            encodings = [resp.apparent_encoding, "utf-8", "gb2312", "gbk"]
            html = None
            for enc in encodings:
                if enc:
                    try:
                        html = resp.content.decode(enc, errors="replace")
                        break
                    except Exception:
                        continue
            if html is None:
                html = resp.text

            soup = BeautifulSoup(html, "html.parser")
            pattern = re.compile(link_pattern)

            for a in soup.find_all("a", href=True):
                href = a["href"]
                full_url = urljoin(start_url, href.split("#")[0])
                if pattern.search(full_url):
                    urls.add(full_url)
                    if len(urls) >= self.per_site_limit:
                        break

            logger.info(f"  Homepage '{start_url}': found {len(urls)} links (pattern: {link_pattern})")
        except requests.RequestException as e:
            logger.warning(f"  Homepage '{start_url}' failed: {e}")
        except Exception as e:
            logger.warning(f"  Homepage '{start_url}' parse error: {e}")

        return list(urls)

    # ------------------------------------------------------------
    # 方法4：分页归档页抓取（新）
    # ------------------------------------------------------------
    def _discover_from_paginated_archive(
        self, base_url: str, link_pattern: str,
        max_pages: int = 50, max_articles: int = 10000,
    ) -> list[str]:
        """从分页的列表页（分类/归档/标签页）逐页抓取文章链接。

        自动跟随"下一页"链接，直到没有更多页或达到上限。

        Args:
            base_url: 起始列表页URL。
            link_pattern: 匹配文章链接的正则。
            max_pages: 最多翻多少页。
            max_articles: 最多收集多少文章URL。

        Returns:
            文章URL列表。
        """
        all_urls: set[str] = set()
        current_url = base_url
        pattern = re.compile(link_pattern)
        page_num = 0

        while current_url and page_num < max_pages and len(all_urls) < max_articles:
            page_num += 1
            try:
                resp = self.session.get(current_url, timeout=20)
                # 编码处理
                for enc in [resp.apparent_encoding, "utf-8", "gb2312", "gbk"]:
                    if enc:
                        try:
                            html = resp.content.decode(enc, errors="replace")
                            break
                        except Exception:
                            continue
                else:
                    html = resp.text

                soup = BeautifulSoup(html, "html.parser")

                # 提取当前页的文章链接
                page_count = 0
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    full_url = urljoin(current_url, href.split("#")[0])
                    if pattern.search(full_url):
                        if full_url not in all_urls:
                            all_urls.add(full_url)
                            page_count += 1

                # 找"下一页"链接
                next_url = None
                next_patterns = [
                    ("a", {"rel": "next"}),
                    ("a", {"class": re.compile(r"next", re.I)}),
                    ("a", {"string": re.compile(r"(下一页|下页|>|next)")}),
                    (".pagination a:last-child", {}),
                    ("link", {"rel": "next"}),
                ]

                for tag, attrs in next_patterns:
                    try:
                        if tag == ".pagination a:last-child":
                            elem = soup.select_one(tag)
                            if elem and elem.get("href"):
                                next_url = urljoin(current_url, elem["href"])
                                break
                        elif tag == "link":
                            elem = soup.find("link", attrs)
                            if elem and elem.get("href"):
                                next_url = urljoin(current_url, elem["href"])
                                break
                        else:
                            for elem in soup.find_all(tag, attrs):
                                href = elem.get("href")
                                if href:
                                    next_url = urljoin(current_url, href)
                                    break
                            if next_url:
                                break
                    except Exception:
                        continue

                if not next_url or next_url == current_url:
                    # 备用1：数字分页 /page/N
                    candidates = [
                        f"{base_url.rstrip('/')}/page/{page_num + 1}",
                        f"{base_url.rstrip('/')}/{page_num + 1}",
                    ]
                    # 备用2：?page=N 参数
                    if "?" in base_url:
                        existing_param = re.search(r"[?&]page=\d+", base_url)
                        if existing_param:
                            candidates.append(
                                re.sub(r"page=\d+", f"page={page_num + 1}", base_url, count=1)
                            )
                        else:
                            candidates.append(f"{base_url}&page={page_num + 1}")
                    else:
                        candidates.append(f"{base_url}?page={page_num + 1}")

                    # 备用3：/pN 格式
                    candidates.append(f"{base_url.rstrip('/')}/p{page_num + 1}")

                    # 逐个试候选URL
                    for cand in candidates:
                        if cand == current_url:
                            continue
                        try:
                            test_resp = self.session.head(cand, timeout=5, allow_redirects=True)
                            if test_resp.status_code < 400:
                                next_url = cand
                                break
                        except Exception:
                            continue

                    if not next_url or next_url == current_url:
                        break

                current_url = next_url
                logger.debug(f"  Archive page {page_num}: {page_count} articles, next={next_url[:80] if next_url else 'none'}")

            except requests.RequestException as e:
                logger.warning(f"  Archive page {page_num} '{current_url[:80]}' failed: {e}")
                break
            except Exception as e:
                logger.warning(f"  Archive page {page_num} parse error: {e}")
                break

        logger.info(f"  Archive '{base_url}': {len(all_urls)} articles across {page_num} pages")
        return list(all_urls)

    # ------------------------------------------------------------
    # 综合发现：遍历所有来源
    # ------------------------------------------------------------
    def discover_for_site(self, site_key: str) -> list[str]:
        """对单个站点执行综合链接发现。

        优先级: RSS > Sitemap > 分页归档 > Homepage

        Args:
            site_key: SITE_PROFILES 中的 key。

        Returns:
            去重的文章URL列表，最多 per_site_limit 条。
        """
        profile = SITE_PROFILES[site_key]
        all_urls: set[str] = set()
        domain = profile["domain"]

        logger.info(f"Discovering links for [{site_key}] {profile['name']}...")

        # 1. RSS feeds (primary)
        for rss_url in profile.get("rss_feeds", []):
            urls = self._discover_from_rss(rss_url)
            for url in urls:
                if domain in url or site_key in url:
                    all_urls.add(url)
            if len(all_urls) >= self.per_site_limit:
                break

        # 2. Sitemaps (fallback)
        if len(all_urls) < self.per_site_limit:
            for sm_url in profile.get("sitemap_urls", []):
                urls = self._discover_from_sitemap(sm_url)
                for url in urls:
                    if domain in url or site_key in url:
                        all_urls.add(url)
                if len(all_urls) >= self.per_site_limit:
                    break

        # 3. 分页归档页（大规模采集主力：翻页抓取分类/列表页）
        if len(all_urls) < self.per_site_limit:
            archive_urls = profile.get("archive_urls", [])
            pattern = profile.get("article_link_pattern", "")
            for archive_url in archive_urls:
                if len(all_urls) >= self.per_site_limit:
                    break
                # 每页25条×200页=5000条URL/归档页
                urls = self._discover_from_paginated_archive(
                    archive_url, pattern,
                    max_pages=200,
                    max_articles=self.per_site_limit - len(all_urls),
                )
                all_urls.update(urls)
                logger.info(f"  [{site_key}] After archive '{archive_url[:60]}': {len(all_urls)} total URLs")

        # 4. 首页抓取 (last resort)
        if len(all_urls) < self.per_site_limit:
            pattern = profile.get("article_link_pattern", "")
            for start_url in profile.get("start_urls", []):
                urls = self._discover_from_homepage(start_url, pattern)
                all_urls.update(urls)
                if len(all_urls) >= self.per_site_limit:
                    break

        url_list = list(all_urls)[:self.per_site_limit]
        logger.info(f"  [{site_key}] Total discovered: {len(url_list)} URLs")
        return url_list

    # ------------------------------------------------------------
    # 批量发现
    # ------------------------------------------------------------
    def discover_all(self, site_keys: Optional[list[str]] = None) -> dict[str, list[str]]:
        """对所有（或指定）站点执行链接发现。

        Args:
            site_keys: 要发现的站点列表。None = 全部。

        Returns:
            {site_key: [url_list], ...}
        """
        if site_keys is None:
            site_keys = SITE_LIST

        result = {}
        for key in site_keys:
            try:
                urls = self.discover_for_site(key)
                result[key] = urls
            except Exception as e:
                logger.error(f"Failed to discover links for [{key}]: {e}")
                result[key] = []

        # 保存到文件
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "per_site_limit": self.per_site_limit,
            "sites": {
                k: {"count": len(v), "urls": v}
                for k, v in result.items()
            },
        }
        with open(DISCOVERED_URLS_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        total = sum(v["count"] for v in output["sites"].values())
        logger.info(f"Link discovery complete: {total:,} URLs from {len(result)} sites")
        logger.info(f"Saved to {DISCOVERED_URLS_FILE}")

        return result


# ================================================================
# 命令行入口
# ================================================================
if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    discoverer = LinkDiscoverer(per_site_limit=20000)

    if len(sys.argv) > 1:
        # 发现指定站点
        site = sys.argv[1]
        if site in SITE_PROFILES:
            urls = discoverer.discover_for_site(site)
            print(f"\n[{site}] {len(urls)} URLs discovered")
            for u in urls[:10]:
                print(f"  {u}")
            if len(urls) > 10:
                print(f"  ... and {len(urls) - 10} more")
        else:
            print(f"Unknown site: {site}")
            print(f"Available: {', '.join(SITE_LIST)}")
    else:
        # 发现所有站点
        result = discoverer.discover_all()
        print(f"\n{'='*60}")
        print(f"Link Discovery Summary")
        print(f"{'='*60}")
        total = 0
        for site, urls in result.items():
            print(f"  {site:15s}  {len(urls):>7d} URLs")
            total += len(urls)
        print(f"{'='*60}")
        print(f"  {'TOTAL':15s}  {total:>7d} URLs")
