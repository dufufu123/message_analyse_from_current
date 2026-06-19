"""
Streamlit 应用主入口 — 文本内容安全系统

启动命令：
    streamlit run app.py

页面结构 (Strealit 自动识别 pages/ 目录)：
    00_🏠_首页仪表盘
    01_🕷️_爬虫控制
    02_📊_EDA可视化
    03_✂️_分词对比
    04_🔍_敏感性检测
    05_💬_情感分析
    06_🛡️_有害信息检测
"""

import streamlit as st

from config.settings import STREAMLIT_TITLE, STREAMLIT_LAYOUT

# Page config — MUST be the first st command
st.set_page_config(
    page_title=STREAMLIT_TITLE,
    page_icon="🛡️",
    layout=STREAMLIT_LAYOUT,
    initial_sidebar_state="expanded",
)

# ---- Sidebar ----
with st.sidebar:
    st.title("📋 文本内容安全系统")
    st.markdown("---")
    st.markdown("### 🔬 实验1：文本内容安全系统")
    st.markdown(
        """
        **功能模块**：
        - 🕷️ 爬虫数据采集
        - 📊 EDA数据可视化
        - ✂️ 三种分词算法
        - 🔍 文本敏感性检测
        - 💬 情感倾向分析
        - 🛡️ 有害信息检测
        """
    )
    st.markdown("---")
    st.markdown("*工程实训3 · 信息内容安全方向*")

# ---- Main page ----
st.title("🛡️ 文本内容安全系统")
st.markdown("### Text Content Security System")

# Stats overview
try:
    from database.connection import get_db_stats
    stats = get_db_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📄 总页面数", f"{stats['total_pages']:,}")
    with col2:
        st.metric("✂️ 已分词", f"{stats['segmented_count']:,}")
    with col3:
        st.metric("🔍 已分析", f"{stats['analyzed_count']:,}")
    with col4:
        st.metric("⚠️ 有害内容", f"{stats['harmful_count']:,}")

    st.markdown("---")

    col5, col6, col7 = st.columns(3)
    with col5:
        st.metric("😊 正面情感", f"{stats['positive_count']:,}")
    with col6:
        st.metric("😐 中性情感", f"{stats['neutral_count']:,}")
    with col7:
        st.metric("😞 负面情感", f"{stats['negative_count']:,}")

except Exception as e:
    st.warning(f"数据库暂无数据或尚未初始化: {e}")
    st.info("请先运行爬虫采集数据，或使用侧边栏导航到各功能页面。")

st.markdown("---")
st.markdown("### 🚀 快速导航")

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.page_link("pages/02_📊_EDA可视化.py", label="📊 EDA可视化", icon="📊")
    st.page_link("pages/03_✂️_分词对比.py", label="✂️ 分词对比", icon="✂️")
with col_b:
    st.page_link("pages/04_🔍_敏感性检测.py", label="🔍 敏感性检测", icon="🔍")
    st.page_link("pages/05_💬_情感分析.py", label="💬 情感分析", icon="💬")
with col_c:
    st.page_link("pages/06_🛡️_有害信息检测.py", label="🛡️ 有害信息检测", icon="🛡️")
    st.page_link("pages/01_🕷️_爬虫控制.py", label="🕷️ 爬虫控制", icon="🕷️")

st.markdown("---")
st.markdown(
    """
    ### 📖 关于本系统

    本系统为**工程实训3**实验1的实现成果，包含以下核心功能：

    1. **爬虫系统** — 基于Scrapy框架，从10+网站采集20万+网页数据
    2. **分词算法** — 实现3种中文分词算法（jieba、最大匹配FMM/BMM/BiMM、DP最短路径）
    3. **内容分析** — 文本敏感性检测、情感倾向分析、有害信息快速检测
    4. **交互应用** — 基于Streamlit的Web交互界面

    请使用侧边栏导航到各功能页面进行数据探索和分析。
    """
)
