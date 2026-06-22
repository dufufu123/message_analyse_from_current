"""
Page: Crawler Control Panel (爬虫控制面板)
"""

import streamlit as st
import pandas as pd

from database.connection import get_source_site_stats
from crawler.site_profiles import SITE_LIST, SITE_PROFILES

st.set_page_config(page_title="爬虫控制", page_icon="🕷️", layout="wide")

st.title("🕷️ 爬虫控制面板")
st.markdown("监控和管理数据采集流程")

# ---- Site Stats ----
st.markdown("### 📊 数据采集概况")

try:
    stats = get_source_site_stats()
    if stats:
        df = pd.DataFrame(stats)
        df.columns = ["来源网站", "页面数量"]

        col1, col2 = st.columns([2, 1])
        with col1:
            st.bar_chart(df.set_index("来源网站"), width='stretch')
        with col2:
            st.dataframe(df, width='stretch', hide_index=True)
    else:
        st.info("暂无采集数据。请运行爬虫开始数据采集。")
except Exception as e:
    st.warning(f"加载统计数据失败: {e}")

# ---- Spider Control ----
st.markdown("---")
st.markdown("### 🚀 爬虫管理")

st.info(
    "⚠️ **注意**：爬虫运行需要网络连接，且应遵守目标网站的 robots.txt 规范。\n\n"
    "推荐使用命令行启动爬虫：\n"
    "```bash\n"
    "python crawler/run_crawler.py          # 运行所有爬虫\n"
    "python crawler/run_crawler.py --list   # 列出所有爬虫\n"
    "python crawler/run_crawler.py sina_news  # 运行指定爬虫\n"
    "```"
)

col1, col2 = st.columns(2)
with col1:
    st.markdown("#### 可用站点列表")
    spider_df = pd.DataFrame({
        "序号": range(1, len(SITE_LIST) + 1),
        "站点Key": SITE_LIST,
        "站点名称": [SITE_PROFILES[k]["name"] for k in SITE_LIST],
        "类别": [SITE_PROFILES[k]["category"] for k in SITE_LIST],
        "链接来源": [
            "RSS" if SITE_PROFILES[k].get("rss_feeds") else ""
            + (" + Sitemap" if SITE_PROFILES[k].get("sitemap_urls") else "")
            + (" + 首页" if SITE_PROFILES[k].get("start_urls") else "")
            for k in SITE_LIST
        ],
        "目标页数": [20000] * len(SITE_LIST),
    })
    st.dataframe(spider_df, width='stretch', hide_index=True)

with col2:
    st.markdown("#### 爬虫配置")
    st.json({
        "并发请求数": 16,
        "下载延迟": "0.5s",
        "自动节流": True,
        "遵守robots.txt": True,
        "每站目标页数": 20000,
        "数据库": "SQLite",
    })

# ---- Database Stats ----
st.markdown("---")
st.markdown("### 💾 数据库信息")
try:
    from database.models import get_engine, WebPage
    from sqlalchemy import func
    from database.models import get_session

    with get_session() as session:
        total = session.query(func.count(WebPage.id)).scalar() or 0
        segmented = session.query(func.count(WebPage.id)).filter(WebPage.processed >= 1).scalar() or 0
        analyzed = session.query(func.count(WebPage.id)).filter(WebPage.processed >= 2).scalar() or 0

    col1, col2, col3 = st.columns(3)
    col1.metric("总记录数", f"{total:,}")
    col2.metric("已分词", f"{segmented:,}")
    col3.metric("已分析", f"{analyzed:,}")

    if total > 0:
        progress = analyzed / total if total > 0 else 0
        st.progress(progress, text=f"分析进度: {progress:.1%}")
except Exception as e:
    st.error(f"数据库连接失败: {e}")
