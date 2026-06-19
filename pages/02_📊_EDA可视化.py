"""
Page: EDA Interactive Visualization (EDA可视化)
"""

import streamlit as st
import pandas as pd

from eda.statistics import (
    load_dataframe, site_distribution, category_distribution,
    text_length_stats, text_length_by_source, publish_time_trend,
    publish_hour_distribution, sentiment_distribution,
    harmful_site_stats, missing_values_report,
)
from eda.visualize import (
    plot_site_distribution, plot_category_pie, plot_text_length_histogram,
    plot_text_length_by_source, plot_time_trend, plot_publish_hour,
    plot_sentiment_pie, plot_harmful_by_site, plot_site_category_heatmap,
)
from database.connection import get_db_stats

st.set_page_config(page_title="EDA可视化", page_icon="📊", layout="wide")

st.title("📊 EDA 数据可视化")
st.markdown("探索性数据分析 — 了解数据分布与特征")

# ---- Sidebar filters ----
with st.sidebar:
    st.markdown("### 🔧 筛选条件")
    sample_size = st.slider("最大加载记录数", 1000, 200000, 50000, 1000)

# Load data
@st.cache_data(ttl=300)
def load_data(sample_size: int):
    return load_dataframe(sample_size)

with st.spinner("正在加载数据..."):
    df = load_data(sample_size)

if df.empty:
    st.warning("暂无数据。请先运行爬虫采集数据。")
    st.stop()

st.markdown(f"**已加载 {len(df):,} 条记录**")

# ---- Row 1: Site & Category Distribution ----
st.markdown("### 📋 数据分布概况")
col1, col2 = st.columns(2)

with col1:
    site_df = site_distribution(df)
    st.plotly_chart(plot_site_distribution(site_df), width="stretch")

with col2:
    cat_df = category_distribution(df)
    st.plotly_chart(plot_category_pie(cat_df), width="stretch")

# ---- Row 2: Text Length ----
st.markdown("---")
st.markdown("### 📏 文本长度分析")
col1, col2 = st.columns(2)

with col1:
    st.plotly_chart(plot_text_length_histogram(df), width="stretch")
    stats = text_length_stats(df)
    st.markdown(f"均值: **{stats.get('mean', 0):.0f}** | "
                f"中位数: **{stats.get('50%', 0):.0f}** | "
                f"标准差: **{stats.get('std', 0):.0f}**")

with col2:
    len_by_src = text_length_by_source(df)
    st.plotly_chart(plot_text_length_by_source(len_by_src), width="stretch")

# ---- Row 3: Time Analysis ----
if "publish_time" in df.columns and df["publish_time"].notna().any():
    st.markdown("---")
    st.markdown("### ⏰ 时间分析")
    col1, col2 = st.columns(2)

    with col1:
        trend_df = publish_time_trend(df)
        if not trend_df.empty:
            st.plotly_chart(plot_time_trend(trend_df), width="stretch")

    with col2:
        hour_df = publish_hour_distribution(df)
        if not hour_df.empty:
            st.plotly_chart(plot_publish_hour(hour_df), width="stretch")

# ---- Row 4: Cross Analysis ----
st.markdown("---")
st.markdown("### 🔀 交叉分析")
col1, col2 = st.columns(2)

with col1:
    try:
        st.plotly_chart(plot_site_category_heatmap(df), width="stretch")
    except Exception as e:
        st.warning(f"热力图生成失败: {e}")

with col2:
    try:
        sent_df = sentiment_distribution(df)
        st.plotly_chart(plot_sentiment_pie(df), width="stretch")
    except Exception as e:
        st.warning(f"情感分布图生成失败: {e}")

# ---- Row 5: Harmful by Site ----
st.markdown("---")
st.markdown("### ⚠️ 有害内容分析")
try:
    harmful_df = harmful_site_stats(df)
    st.plotly_chart(plot_harmful_by_site(harmful_df), width="stretch")
except Exception as e:
    st.warning(f"有害内容分析失败: {e}")

# ---- Missing Values ----
st.markdown("---")
st.markdown("### 🔍 数据质量")
missing_df = missing_values_report(df)
st.dataframe(missing_df, width="stretch", hide_index=True)

# ---- Raw Data Preview ----
st.markdown("---")
st.markdown("### 📝 原始数据预览")
st.dataframe(df.head(100), width="stretch")
