"""
爬虫编排脚本 — 三阶段执行流程

阶段1: 链接发现 → python crawler/run_crawler.py discover
阶段2: 文章抓取 → python crawler/run_crawler.py crawl
一键执行:     python crawler/run_crawler.py

也可以:
  python crawler/run_crawler.py discover cnblogs    # 只发现指定站点
  python crawler/run_crawler.py crawl cnblogs        # 只抓取指定站点
  python crawler/run_crawler.py list                 # 列出所有站点
"""

import argparse
import sys
import os
import logging
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from crawler.site_profiles import SITE_LIST
from crawler.link_discovery import LinkDiscoverer, DISCOVERED_URLS_FILE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_crawler")


def cmd_list():
    """列出所有可用站点。"""
    from crawler.site_profiles import SITE_PROFILES
    print(f"\n{'='*60}")
    print(f"Available Sites ({len(SITE_LIST)} total)")
    print(f"{'='*60}")
    print(f"{'Key':15s} {'Name':10s} {'Category':8s} {'RSS':5s} {'Sitemap':8s}")
    print(f"{'-'*15} {'-'*10} {'-'*8} {'-'*5} {'-'*8}")
    for key in SITE_LIST:
        p = SITE_PROFILES[key]
        has_rss = "✓" if p.get("rss_feeds") else "✗"
        has_sm = "✓" if p.get("sitemap_urls") else "✗"
        print(f"{key:15s} {p['name']:10s} {p['category']:8s} {has_rss:5s} {has_sm:8s}")
    print(f"{'='*60}")


def cmd_discover(site: str = None, quick: bool = False):
    """阶段1: 链接发现 — 从RSS/Sitemap/首页收集文章URL。"""
    logger.info("=" * 60)
    logger.info("Phase 1: Link Discovery" + (" (Quick Mode)" if quick else ""))
    logger.info("=" * 60)

    # 初始化数据库
    from database.models import init_database
    init_database()

    per_site = 30 if quick else 5000  # quick: ~500 total, normal: 200K target
    discoverer = LinkDiscoverer(per_site_limit=per_site)

    if site:
        # 单个站点
        if site not in SITE_LIST:
            logger.error(f"Unknown site: {site}")
            logger.info(f"Available: {', '.join(SITE_LIST)}")
            return False
        urls = discoverer.discover_for_site(site)
        logger.info(f"\n[{site}] Discovered {len(urls)} URLs")
    else:
        # 所有站点
        result = discoverer.discover_all()
        total = sum(len(v) for v in result.values())
        logger.info(f"\nTotal: {total:,} URLs from {len(result)} sites")

    return True


def cmd_direct(site: str = None, loop: bool = False):
    """DOM直采模式 — 分析列表页DOM结构直接抓取。加 --loop 自动循环到20万。"""
    if loop:
        return _cmd_direct_loop(site)
    _cmd_direct_once(site)


def _cmd_direct_once(site: str = None):
    """单次DOM直采。"""
    logger.info("=" * 60)
    logger.info("Direct DOM Crawling")
    logger.info("=" * 60)

    from database.models import init_database
    init_database()

    cmd = [sys.executable, "-c", f"""
import os, sys
os.environ['SCRAPY_SETTINGS_MODULE'] = 'crawler.settings'
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from database.models import init_database
init_database()
settings = get_project_settings()
settings.set('LOG_LEVEL', 'WARNING')
process = CrawlerProcess(settings)
process.crawl('direct', site={repr(site)})
process.start()
"""]
    subprocess.run(cmd, capture_output=False, cwd=BASE_DIR)


def _cmd_direct_loop(site: str = None, target: int = 200000):
    """循环DOM直采直到达到目标。"""
    logger.info("=" * 60)
    logger.info(f"Direct DOM Crawling (LOOP mode, target={target:,})")
    logger.info("=" * 60)

    from database.connection import get_db_stats

    cycle = 0
    while True:
        cycle += 1
        stats = get_db_stats()
        current = stats["total_pages"]
        logger.info(f"\n--- Direct loop #{cycle}: DB={current:,}/{target:,} ---")

        if current >= target:
            logger.info(f"Target reached!")
            break

        _cmd_direct_once(site)

        new_stats = get_db_stats()
        added = new_stats["total_pages"] - current
        logger.info(f"Loop #{cycle} added {added:,} pages")

        if added < 5 and cycle >= 10:
            logger.info("No new content after 10 cycles, stopping.")
            break

    logger.info(f"Direct loop finished: {get_db_stats()['total_pages']:,} pages")


def cmd_crawl(site: str = None, max_pages: int = None):
    """阶段2: 文章抓取 — 用Scrapy爬取已发现URL的正文内容。"""
    logger.info("=" * 60)
    logger.info("Phase 2: Article Crawling")
    logger.info("=" * 60)

    # 检查URL文件是否存在
    if not os.path.exists(DISCOVERED_URLS_FILE):
        logger.error(f"URL file not found: {DISCOVERED_URLS_FILE}")
        logger.error("Please run link discovery first: python crawler/run_crawler.py discover")
        return

    # 初始化数据库
    from database.models import init_database
    init_database()

    os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "crawler.settings")

    # 用子进程跑 Scrapy，避免 ReactorNotRestartable 问题
    cmd = [sys.executable, "-c", f"""
import os, sys
os.environ['SCRAPY_SETTINGS_MODULE'] = 'crawler.settings'
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from database.models import init_database
init_database()
settings = get_project_settings()
settings.set('LOG_LEVEL', 'WARNING')
process = CrawlerProcess(settings)
process.crawl('universal', site={repr(site)}, max_pages={max_pages or 20000})
process.start()
"""]
    result = subprocess.run(cmd, capture_output=False, cwd=BASE_DIR)
    if result.returncode != 0:
        logger.error(f"Crawl subprocess exited with code {result.returncode}")


def cmd_cycle(target: int = 200000, max_cycles: int = 50):
    """循环采集：反复 discover → crawl 直到达到目标条数。

    每轮都重新发现链接（RSS/Sitemap会更新，归档页翻到新页面），
    已经入库的URL自动跳过（UNIQUE约束），只抓新内容。
    """
    logger.info("=" * 60)
    logger.info(f"Cycle Mode: target={target:,} pages, max_cycles={max_cycles}")
    logger.info("=" * 60)

    from database.connection import get_db_stats

    for cycle in range(1, max_cycles + 1):
        stats = get_db_stats()
        current = stats["total_pages"]
        logger.info(f"\n{'#'*60}")
        logger.info(f"# CYCLE {cycle}/{max_cycles} | DB: {current:,} / {target:,} pages")
        logger.info(f"{'#'*60}")

        if current >= target:
            logger.info(f"Target reached! {current:,} >= {target:,}")
            break

        # 阶段1：链接发现
        if not cmd_discover(quick=False):
            logger.error("Link discovery failed, stopping")
            break

        # 阶段2：文章抓取（RSS模式 + DOM直采模式，双管齐下）
        cmd_crawl()
        cmd_direct()

        # 检查本轮增量
        new_stats = get_db_stats()
        added = new_stats["total_pages"] - current
        logger.info(f"Cycle {cycle} added {added:,} pages (total: {new_stats['total_pages']:,})")

        if added == 0:
            logger.warning("No new pages added this cycle. URLs may be exhausted.")
            # 再试几轮，如果连续3轮没增量就停
            dry_cycles = getattr(cmd_cycle, '_dry_cycles', 0) + 1
            cmd_cycle._dry_cycles = dry_cycles
            if dry_cycles >= 3:
                logger.info("3 consecutive dry cycles, stopping.")
                break
        else:
            cmd_cycle._dry_cycles = 0

    final = get_db_stats()["total_pages"]
    logger.info(f"\nCycle mode finished: {final:,} pages collected")
cmd_cycle._dry_cycles = 0


cmd_cycle._dry_cycles = 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Text Content Security Crawler — RSS/Universal Architecture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python crawler/run_crawler.py list                    # List all sites
  python crawler/run_crawler.py discover                # Discover links from all sites
  python crawler/run_crawler.py discover cnblogs        # Discover links from cnblogs only
  python crawler/run_crawler.py crawl                   # Crawl articles from all discovered URLs
  python crawler/run_crawler.py crawl cnblogs           # Crawl cnblogs articles only
  python crawler/run_crawler.py                         # Full pipeline (discover + crawl)
        """,
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=["list", "discover", "crawl", "direct", "all", "cycle"],
        help="Command to execute (default: all = discover + crawl; cycle = loop until target)",
    )
    parser.add_argument(
        "site",
        nargs="?",
        default=None,
        help=f"Target site key (e.g., cnblogs, 36kr). Available: {', '.join(SITE_LIST)}",
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Quick test mode: ~30 URLs per site (~500 total), fast for development testing",
    )
    parser.add_argument(
        "--loop", "-l",
        action="store_true",
        help="Loop mode (for direct): keep running until 200K target reached",
    )

    args = parser.parse_args()

    if args.command == "list":
        cmd_list()
    elif args.command == "discover":
        cmd_discover(args.site, quick=args.quick)
    elif args.command == "crawl":
        cmd_crawl(args.site)
    elif args.command == "all":
        cmd_discover(args.site, quick=args.quick)
        cmd_crawl(args.site)
    elif args.command == "direct":
        cmd_direct(args.site, loop=args.loop)
    elif args.command == "cycle":
        if args.quick:
            cmd_cycle(target=5000, max_cycles=5)
        else:
            cmd_cycle(target=200000, max_cycles=50)
    else:
        parser.print_help()
