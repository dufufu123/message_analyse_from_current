"""
DOM直采站点配置 — 实测验证版

每个站点都经过实际HTTP请求验证：
- 列表页可访问 (200)
- 文章链接正则匹配正确
- 翻页格式确认有效
"""

SITE_CONFIGS = {
    # ================================================================
    # IT之家 — 一页387链接，翻页?page=N
    # ================================================================
    "ithome_direct": {
        "name": "IT之家", "domain": "www.ithome.com", "category": "news",
        "start_urls": [
            "https://www.ithome.com/",
        ],
        "article_pattern": r"/\d+/\d+\.htm",
        "exclude_patterns": [r"/tag/", r"/user/", r"/zt/"],
        "pagination": {"mode": "url_template", "template": "https://www.ithome.com/?page={page}"},
        "selectors": {
            "title": ".post_title::text, h1::text, title::text",
            "body": ".post_content, .article-content, article",
            "date": ".post_time::text, .time::text"
        },
        "max_pages": 200, "max_articles": 20000
    },

    # ================================================================
    # 虎扑 — 一页50链接(bxj-1)，翻页/bxj-N
    # ================================================================
    "hupu_direct": {
        "name": "虎扑", "domain": "bbs.hupu.com", "category": "social",
        "start_urls": [
            "https://bbs.hupu.com/bxj-1",
            "https://bbs.hupu.com/34-1",
        ],
        "article_pattern": r"/\d+\.html",
        "exclude_patterns": [r"/user/", r"/search/", r"/topic/"],
        "pagination": {"mode": "url_template", "template": "{base_url}-{page}"},
        "selectors": {
            "title": ".title::text, h1::text, title::text",
            "body": ".post-content, .topic-content, article",
            "date": ".post-time::text, .time::text"
        },
        "max_pages": 200, "max_articles": 10000
    },

    # ================================================================
    # 钛媒体 — 一页94链接，翻页?page=N
    # ================================================================
    "tmtpost_direct": {
        "name": "钛媒体", "domain": "www.tmtpost.com", "category": "news",
        "start_urls": ["https://www.tmtpost.com/"],
        "article_pattern": r"/\d+\.html",
        "exclude_patterns": [r"/user/", r"/tag/", r"/column/"],
        "pagination": {"mode": "param", "param_name": "page", "first_param_value": "1"},
        "selectors": {
            "title": ".article-title::text, h1::text, title::text",
            "body": ".article-content, .post-content, article",
            "date": ".time::text, .date::text"
        },
        "max_pages": 200, "max_articles": 10000
    },

    # ================================================================
    # 爱范儿 — 一页57链接，翻页?page=N
    # ================================================================
    "ifanr_direct": {
        "name": "爱范儿", "domain": "www.ifanr.com", "category": "news",
        "start_urls": ["https://www.ifanr.com/"],
        "article_pattern": r"/\d+",
        "exclude_patterns": [r"/user/", r"/tag/", r"/author/", r"/apps/", r"share\.php"],
        "pagination": {"mode": "param", "param_name": "page", "first_param_value": "2"},
        "selectors": {
            "title": ".article-title::text, h1::text, title::text",
            "body": ".article-content, .content, article",
            "date": ".time::text, .date::text"
        },
        "max_pages": 200, "max_articles": 10000
    },

    # ================================================================
    # 汽车之家 — 一页69链接，翻页/news/N/
    # ================================================================
    "autohome_direct": {
        "name": "汽车之家", "domain": "www.autohome.com.cn", "category": "review",
        "start_urls": [
            "https://www.autohome.com.cn/news/1/",
        ],
        "article_pattern": r"/news/\d{6}/\d+\.html",
        "exclude_patterns": [],
        "pagination": {"mode": "url_template", "template": "https://www.autohome.com.cn/news/{page}/"},
        "selectors": {
            "title": ".article-title::text, h1::text, title::text",
            "body": ".article-content, .content, article",
            "date": ".time::text"
        },
        "max_pages": 200, "max_articles": 10000
    },

    # ================================================================
    # 人人都是PM — 一页21链接，翻页?page=N
    # ================================================================
    "woshipm_direct": {
        "name": "人人都是PM", "domain": "www.woshipm.com", "category": "blog",
        "start_urls": [
            "https://www.woshipm.com/category/pmd",
        ],
        "article_pattern": r"/\w+/\d+\.html",
        "exclude_patterns": [],
        "pagination": {"mode": "param", "param_name": "page", "first_param_value": "2"},
        "selectors": {
            "title": ".article-title::text, h1::text, title::text",
            "body": ".article-content, .content, article",
            "date": ".time::text, .date::text"
        },
        "max_pages": 200, "max_articles": 10000
    },

    # ================================================================
    # 搜狐新闻 — 一页28链接，CSS翻页
    # ================================================================
    "sohu_direct": {
        "name": "搜狐新闻", "domain": "www.sohu.com", "category": "news",
        "start_urls": [
            "https://www.sohu.com/c/8/1460",
        ],
        "article_pattern": r"/a/\d+_\d+",
        "exclude_patterns": [],
        "pagination": {"mode": "css", "css": "a:contains('下一页'), .page a:last-child"},
        "selectors": {
            "title": ".text-title h1::text, h1::text, title::text",
            "body": ".article, .text-content, article",
            "date": ".time::text, .article-time::text"
        },
        "max_pages": 100, "max_articles": 5000
    },

    # ================================================================
    # 第一财经 — 一页22链接，翻页?page=N
    # ================================================================
    "yicai_direct": {
        "name": "第一财经", "domain": "www.yicai.com", "category": "news",
        "start_urls": [
            "https://www.yicai.com/news/",
        ],
        "article_pattern": r"/news/\d+\.html",
        "exclude_patterns": [],
        "pagination": {"mode": "param", "param_name": "page", "first_param_value": "2"},
        "selectors": {
            "title": ".title::text, h1::text, title::text",
            "body": ".m-text, .article-content, article",
            "date": ".time::text, .date::text"
        },
        "max_pages": 200, "max_articles": 10000
    },
}
