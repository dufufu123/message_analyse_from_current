"""
Page: Sensitivity Detection (敏感性检测)
"""

import json
import streamlit as st
import pandas as pd

from database.models import WebPage, get_session
from sqlalchemy import func
from analysis.sensitivity import SensitivityDetector

st.set_page_config(page_title="敏感性检测", page_icon="🔍", layout="wide")

st.title("🔍 文本敏感性检测")
st.markdown("基于AC自动机的多模式匹配敏感性检测")

# ---- Sidebar filters ----
with st.sidebar:
    st.markdown("### 🔧 筛选条件")
    min_score = st.slider("最低敏感性分数", 0.0, 1.0, 0.0, 0.01)
    categories = st.multiselect(
        "敏感类别",
        ["politics", "pornography", "violence", "gambling", "fraud"],
        default=["politics", "pornography", "violence", "gambling", "fraud"],
        format_func=lambda x: {
            "politics": "政治敏感", "pornography": "色情内容",
            "violence": "暴力内容", "gambling": "赌博信息", "fraud": "欺诈信息",
        }[x],
    )
    limit = st.slider("显示记录数", 10, 500, 100, 10)

# Load data
import random

@st.cache_data
def load_sensitive_data(min_score: float, categories: list[str], limit: int):
    with get_session() as session:
        return (
            session.query(WebPage)
            .filter(WebPage.processed >= 2, WebPage.sensitivity_score >= min_score)
            .order_by(WebPage.id)
            .limit(limit)
            .all()
        )

pages = load_sensitive_data(min_score, categories, limit)

if not pages:
    st.info("暂无匹配的敏感内容记录。请先运行分析处理或调整筛选条件。")
    st.stop()

st.markdown(f"**找到 {len(pages)} 条记录** (最低分数: {min_score})")

# ---- Summary Stats ----
st.markdown("### 📊 敏感内容概览")
col1, col2, col3 = st.columns(3)
scores = [p.sensitivity_score for p in pages]
with col1:
    st.metric("平均敏感性分数", f"{sum(scores)/len(scores):.3f}" if scores else "N/A")
with col2:
    st.metric("最高敏感性分数", f"{max(scores):.3f}" if scores else "N/A")
with col3:
    flagged = sum(1 for p in pages if p.sensitivity_score > 0.05)
    st.metric("标记为敏感", f"{flagged} ({flagged/len(pages)*100:.1f}%)" if pages else "N/A")

# ---- Results Table ----
st.markdown("### 📋 检测结果")
rows = []
for p in pages:
    flags = p.get_sensitivity_flags()
    # Filter by selected categories
    if categories and not any(f in categories for f in flags):
        continue
    rows.append({
        "ID": p.id,
        "标题": p.title[:80] if p.title else "",
        "来源": p.source_site,
        "敏感性分数": p.sensitivity_score,
        "敏感类别": ", ".join(flags) if flags else "无",
        "文本长度": p.text_length,
    })

if rows:
    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)

    # ---- Detail View ----
    st.markdown("---")
    st.markdown("### 🔎 详情查看")
    selected_id = st.number_input("输入记录ID查看详情", min_value=1, max_value=1000000, value=int(df.iloc[0]["ID"]) if not df.empty else 1)

    with get_session() as session:
        page = session.query(WebPage).filter(WebPage.id == selected_id).first()

    if page:
        st.markdown(f"**URL**: {page.url}")
        st.markdown(f"**标题**: {page.title}")
        st.markdown(f"**敏感性分数**: {page.sensitivity_score}")
        st.markdown(f"**敏感类别**: {', '.join(page.get_sensitivity_flags()) if page.get_sensitivity_flags() else '无'}")

        with st.expander("查看文本内容"):
            st.text(page.clean_text[:5000] if page.clean_text else "(无内容)")

        # 读取数据库已有的分析结果（不重新跑分析）
        with st.expander("查看匹配的敏感词"):
            if page.sensitivity_details:
                detail = json.loads(page.sensitivity_details)
                if detail.get("matched_words"):
                    st.dataframe(pd.DataFrame(detail["matched_words"]), width="stretch")
                else:
                    st.info("未检测到敏感词")
            else:
                st.info("无详情数据")
    else:
        st.error(f"未找到ID为 {selected_id} 的记录")

# ---- Batch Detection Demo ----
st.markdown("---")
st.markdown("### 🧪 实时检测演示")
demo_text = st.text_area(
    "输入文本进行敏感性检测：",
    value="提供各种赌博服务，加QQ12345678，在线投注六合彩。",
    height=100,
)

if st.button("🔍 检测敏感性", type="primary") and demo_text:
    detector = SensitivityDetector()
    result = detector.detect(demo_text)
    st.markdown(f"**敏感性分数**: {result.score}")
    st.markdown(f"**是否敏感**: {'⚠️ 是' if result.is_sensitive else '✅ 否'}")
    if result.flags:
        st.markdown(f"**敏感类别**: {', '.join(result.flags)}")
    if result.matched_words:
        st.markdown("**匹配的敏感词**:")
        st.dataframe(pd.DataFrame(result.matched_words), width="stretch")
