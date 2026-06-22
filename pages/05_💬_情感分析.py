"""
Page: Sentiment Analysis (情感分析)
"""

import json
import streamlit as st
import pandas as pd
import plotly.express as px

from database.models import WebPage, get_session
from sqlalchemy import func
from analysis.sentiment import SentimentAnalyzer
from segmentation.algorithm_jieba import JiebaSegmenter

st.set_page_config(page_title="情感分析", page_icon="💬", layout="wide")

st.title("💬 文本情感分析")
st.markdown("基于SnowNLP + 情感词典的中文情感倾向分析")

# ---- Sidebar filters ----
with st.sidebar:
    st.markdown("### 🔧 筛选条件")
    sentiment_filter = st.selectbox(
        "情感倾向",
        ["全部", "positive", "negative", "neutral"],
        format_func=lambda x: {
            "全部": "全部", "positive": "😊 正面", "negative": "😞 负面", "neutral": "😐 中性"
        }[x],
    )
    limit = st.slider("显示记录数", 10, 500, 100, 10)

# Load data
import random

@st.cache_data
def load_sentiment_data(sentiment_filter: str, limit: int):
    with get_session() as session:
        query = session.query(WebPage).filter(WebPage.processed >= 2)
        if sentiment_filter != "全部":
            query = query.filter(WebPage.sentiment_label == sentiment_filter)
        return query.order_by(WebPage.id).limit(limit).all()

pages = load_sentiment_data(sentiment_filter, limit)

# ---- Distribution Chart ----
st.markdown("### 📊 情感分布")

@st.cache_data(ttl=300)
def load_sentiment_distribution():
    with get_session() as session:
        from sqlalchemy import func
        # 只统计前50000条的分布（避免全表200K扫描）
        subq = session.query(WebPage.sentiment_label, WebPage.sentiment_score).filter(
            WebPage.processed >= 2
        ).limit(50000).subquery()
        results = (
            session.query(
                subq.c.sentiment_label,
                func.count(subq.c.sentiment_label),
                func.avg(subq.c.sentiment_score),
            )
            .group_by(subq.c.sentiment_label)
            .all()
        )
    return results

dist = load_sentiment_distribution()
if dist:
    dist_data = []
    for label, count, avg_score in dist:
        dist_data.append({
            "情感": {"positive": "😊 正面", "negative": "😞 负面", "neutral": "😐 中性"}.get(label, label),
            "数量": count,
            "平均分数": round(float(avg_score or 0), 3),
        })
    dist_df = pd.DataFrame(dist_data)

    col1, col2 = st.columns(2)
    with col1:
        fig = px.pie(dist_df, names="情感", values="数量", title="情感倾向分布",
                      color_discrete_sequence=["#00CC96", "#EF553B", "#636EFA"])
        st.plotly_chart(fig, width="stretch")
    with col2:
        fig = px.bar(dist_df, x="情感", y="数量", title="情感统计",
                      color="情感", color_discrete_sequence=["#00CC96", "#EF553B", "#636EFA"])
        st.plotly_chart(fig, width="stretch")

# ---- Results Table ----
st.markdown("---")
st.markdown("### 📋 分析结果")
if pages:
    rows = []
    for p in pages:
        rows.append({
            "ID": p.id,
            "标题": p.title[:80] if p.title else "",
            "来源": p.source_site,
            "情感分数": p.sentiment_score,
            "情感标签": {"positive": "😊 正面", "negative": "😞 负面", "neutral": "😐 中性"}.get(p.sentiment_label, p.sentiment_label),
            "文本长度": p.text_length,
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
else:
    st.info("暂无分析数据。请先运行分析处理。")

# ---- Real-time Demo ----
st.markdown("---")
st.markdown("### 🧪 实时情感分析")
demo_text = st.text_area(
    "输入文本进行情感分析：",
    value="这个产品非常好用，我很喜欢，强烈推荐给大家！",
    height=100,
)

if st.button("💬 分析情感", type="primary") and demo_text:
    # Step 1: Segment the input text (required by SentimentAnalyzer)
    segmenter = JiebaSegmenter(mode="accurate")
    tokens = segmenter.segment(demo_text)

    # Step 2: Run sentiment analysis on tokens
    analyzer = SentimentAnalyzer()
    result = analyzer.analyze(tokens)

    col1, col2, col3 = st.columns(3)
    emoji = {"positive": "😊", "negative": "😞", "neutral": "😐"}
    with col1:
        st.metric("情感标签", f"{emoji.get(result.label, '')} {result.label}")
    with col2:
        st.metric("情感分数", f"{result.score:.4f}")
    with col3:
        st.metric("置信度", f"{result.confidence:.4f}")
    st.markdown(f"**分析方法**: {result.method}")

    with st.expander("查看分词结果"):
        st.text(" | ".join(tokens))
