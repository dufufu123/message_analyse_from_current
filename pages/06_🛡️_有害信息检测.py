"""
Page: Harmful Content Detection (有害信息检测)
"""

import json
import streamlit as st
import pandas as pd
import plotly.express as px

from database.models import WebPage, get_session
from sqlalchemy import func
from analysis.harmful_detector import HarmfulDetector
from segmentation.algorithm_jieba import JiebaSegmenter

st.set_page_config(page_title="有害信息检测", page_icon="🛡️", layout="wide")

st.title("🛡️ 有害信息快速检测")
st.markdown("三层过滤架构：正则模式 → AC自动机 → 上下文规则评分")

# ---- Sidebar ----
with st.sidebar:
    st.markdown("### 🔧 筛选条件")
    show_harmful_only = st.checkbox("仅显示有害内容", value=True)
    categories = st.multiselect(
        "有害类别",
        ["porn", "gambling", "fraud", "violence", "spam"],
        default=["porn", "gambling", "fraud", "violence", "spam"],
        format_func=lambda x: {
            "porn": "色情", "gambling": "赌博", "fraud": "欺诈",
            "violence": "暴力", "spam": "垃圾推广",
        }[x],
    )
    limit = st.slider("显示记录数", 10, 500, 100, 10)

# Load data
import random

@st.cache_data
def load_harmful_data(harmful_only: bool, categories: list[str], limit: int):
    """Load harmful pages with progressive batch fetching.

    Strategy: fetch from DB in batches → filter by category in Python →
    accumulate until we have enough results. This avoids loading all
    ~200K rows into memory when only 100 are needed.
    """
    BATCH_SIZE = 2000          # rows per DB fetch
    MAX_SCAN = 50000           # safety cap: don't scan endlessly

    result = []
    offset = 0

    with get_session() as session:
        while len(result) < limit and offset < MAX_SCAN:
            query = (
                session.query(WebPage)
                .filter(WebPage.processed >= 2)
            )
            if harmful_only:
                query = query.filter(WebPage.harmful_is_harmful == 1)
            batch = (
                query.order_by(WebPage.harmful_score.desc())
                .offset(offset)
                .limit(BATCH_SIZE)
                .all()
            )

            if not batch:
                break  # no more rows in DB

            for p in batch:
                flags = p.get_harmful_flags()
                if categories and not any(f in categories for f in flags):
                    continue
                result.append(p)
                if len(result) >= limit:
                    return result  # early exit — got enough

            offset += BATCH_SIZE

    return result

pages = load_harmful_data(show_harmful_only, categories, limit)

st.markdown(f"**找到 {len(pages)} 条记录**")

# ---- Summary ----
st.markdown("### 📊 有害内容概览")
col1, col2, col3, col4 = st.columns(4)

try:
    from database.connection import get_db_stats
    from eda.statistics import harmful_site_stats
    import pandas as pd

    stats = get_db_stats()
    with col1:
        st.metric("总分析页面", f"{stats['analyzed_count']:,}")
    with col2:
        st.metric("有害内容", f"{stats['harmful_count']:,}")
    with col3:
        rate = stats['harmful_count'] / max(stats['analyzed_count'], 1) * 100
        st.metric("有害比例", f"{rate:.2f}%")
    with col4:
        st.metric("安全内容", f"{stats['analyzed_count'] - stats['harmful_count']:,}")
except Exception as e:
    st.warning(f"统计数据加载失败: {e}")

# ---- Harmful by type ----
st.markdown("### 📋 检测结果明细")

if pages:
    rows = []
    for p in pages:
        flags = p.get_harmful_flags()
        rows.append({
            "ID": p.id,
            "标题": p.title[:80] if p.title else "",
            "来源": p.source_site,
            "有害分数": p.harmful_score,
            "有害标签": ", ".join(flags) if flags else "无",
            "文本长度": p.text_length,
        })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, width="stretch", hide_index=True)

        # Export
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 导出CSV", csv, "harmful_content.csv", "text/csv",
            key="download_csv",
        )
    else:
        st.info("暂无匹配的有害内容。")

    # ---- Detail View ----
    st.markdown("---")
    st.markdown("### 🔎 详情查看")
    if df is not None and not df.empty:
        selected_id = st.number_input(
            "输入记录ID查看详情", min_value=1, max_value=1000000,
            value=int(df.iloc[0]["ID"]) if len(df) > 0 else 1
        )

        with get_session() as session:
            page = session.query(WebPage).filter(WebPage.id == selected_id).first()

        if page:
            st.markdown(f"**URL**: {page.url}")
            st.markdown(f"**标题**: {page.title}")
            st.markdown(f"**有害分数**: {page.harmful_score}")
            st.markdown(f"**有害标签**: {', '.join(page.get_harmful_flags()) if page.get_harmful_flags() else '无'}")

            with st.expander("查看文本内容"):
                st.text(page.clean_text[:5000] if page.clean_text else "(无内容)")

            # 读取数据库已有的分析结果
            with st.expander("查看检测详情"):
                if page.harmful_details:
                    detail = json.loads(page.harmful_details)
                    st.markdown(f"**分数**: {detail['score']}, **有害**: {'⚠️ 是' if detail['is_harmful'] else '✅ 否'}")
                    if detail.get("layer1_matches"):
                        st.markdown("**Layer 1 (正则) 匹配**:")
                        st.dataframe(pd.DataFrame(detail["layer1_matches"]), width="stretch")
                    if detail.get("layer2_matches"):
                        st.markdown("**Layer 2 (关键词) 匹配**:")
                        st.dataframe(pd.DataFrame(detail["layer2_matches"]), width="stretch")
                    if detail.get("details"):
                        st.markdown(f"**Layer 3 (规则)**: {detail['details']}")
                else:
                    st.info("无详情数据")

# ---- Real-time Demo ----
st.markdown("---")
st.markdown("### 🧪 实时有害信息检测")
demo_text = st.text_area(
    "输入文本进行有害信息检测：",
    value="加微信免费领取，兼职刷单日赚1000，月入过万不是梦！限时优惠速抢。银行卡号6222021234567890，电话13812345678",
    height=100,
)

if st.button("🛡️ 检测有害信息", type="primary") and demo_text:
    # Step 1: Segment the input text (required by HarmfulDetector)
    segmenter = JiebaSegmenter(mode="accurate")
    tokens = segmenter.segment(demo_text)

    # Step 2: Run harmful detection on tokens + raw_text
    detector = HarmfulDetector()
    result = detector.detect(tokens, raw_text=demo_text)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("有害分数", f"{result.score:.3f}")
    with col2:
        st.metric("是否有害", "⚠️ 是" if result.is_harmful else "✅ 否")
    with col3:
        st.metric("有害类别", ", ".join(result.flags) if result.flags else "无")

    with st.expander("查看分词结果"):
        st.text(" | ".join(tokens))

    if result.layer1_matches:
        st.markdown("**Layer 1 — 正则模式匹配**:")
        st.dataframe(pd.DataFrame(result.layer1_matches), width="stretch", hide_index=True)
    if result.layer2_matches:
        st.markdown("**Layer 2 — AC自动机关键词匹配**:")
        st.dataframe(pd.DataFrame(result.layer2_matches), width="stretch", hide_index=True)
    if result.details:
        st.markdown(f"**Layer 3 — 上下文规则**: {result.details}")
