"""
Page: Segmentation Algorithm Comparison (分词对比) — Rewritten with per-article detail view
"""

import json
import streamlit as st
import pandas as pd

from segmentation.algorithm_jieba import JiebaSegmenter
from segmentation.algorithm_max_match import MaxMatchSegmenter
from segmentation.algorithm_dp import DPUnigramSegmenter

st.set_page_config(page_title="分词对比", page_icon="✂️", layout="wide")

st.title("✂️ 分词算法对比")
st.markdown("三种中文分词算法的实时对比与数据库文章详情")

# ---- Algorithm Introduction (collapsed) ----
with st.expander("📖 三种分词算法简介", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        ### 🔵 jieba 分词
        **原理**: 前缀词典 → DAG → 动态规划最优路径 → HMM处理未登录词
        **特点**: 工业级成熟方案，速度快
        """)
    with col2:
        st.markdown("""
        ### 🟢 最大匹配 (自定义)
        **原理**: 贪心策略，每次匹配词典中最长词条
        **变体**: FMM(前向) / BMM(后向) / BiMM(双向)
        **词典**: jieba词典(~500K词)
        """)
    with col3:
        st.markdown("""
        ### 🟣 DP最短路径 (自定义)
        **原理**: Unigram语言模型 + 动态规划全局最优解
        **公式**: cost(w) = -log(P(w))
        **优势**: 全局最优，非贪心
        """)

st.markdown("---")

# ================================================================
# Section 1: Live Demo
# ================================================================
st.markdown("### 🔬 实时分词演示")

user_text = st.text_area(
    "输入中文文本进行分词测试：",
    value="文本内容安全系统是工程实训的重要课题，需要实现爬虫采集和分词算法以及情感分析。",
    height=80,
)

col_mode1, col_mode2 = st.columns(2)
with col_mode1:
    jieba_mode = st.selectbox("jieba 模式", ["accurate", "full", "search"],
        format_func=lambda x: {"accurate":"精确模式","full":"全模式","search":"搜索模式"}[x])
with col_mode2:
    mm_strategy = st.selectbox("最大匹配 策略", ["bimm","fmm","bmm"],
        format_func=lambda x: {"fmm":"FMM前向","bmm":"BMM后向","bimm":"BiMM双向"}[x])

if st.button("🔍 开始分词", type="primary") and user_text:
    with st.spinner("分词中..."):
        seg1 = JiebaSegmenter(mode=jieba_mode)
        seg2 = MaxMatchSegmenter(strategy=mm_strategy)
        seg3 = DPUnigramSegmenter()
        t1, t2, t3 = seg1.segment(user_text), seg2.segment(user_text), seg3.segment(user_text)

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown(f"**🔵 jieba ({jieba_mode})** — {len(t1)} 词")
            st.code(" / ".join(t1), language="text")
        with col_b:
            st.markdown(f"**🟢 最大匹配 ({mm_strategy})** — {len(t2)} 词")
            st.code(" / ".join(t2), language="text")
        with col_c:
            st.markdown(f"**🟣 DP最短路径** — {len(t3)} 词")
            st.code(" / ".join(t3), language="text")

        comp = []
        for name, tokens in [("jieba",t1),("maxmatch",t2),("dp_unigram",t3)]:
            avg_len = sum(len(t)for t in tokens)/len(tokens) if tokens else 0
            comp.append({
                "算法":name,"词数":len(tokens),"平均词长":round(avg_len,2),
                "单字词":sum(1 for t in tokens if len(t)==1),
                "最长词":max(tokens,key=len)if tokens else"",
            })
        st.dataframe(pd.DataFrame(comp), width="stretch", hide_index=True)

st.markdown("---")

# ================================================================
# Section 2: DB Article Browser with Token Detail View
# ================================================================
st.markdown("### 📂 已分词文章浏览")

@st.cache_data(ttl=30)
def load_articles(limit=200):
    from database.models import WebPage, get_session
    with get_session() as session:
        return (
            session.query(WebPage)
            .filter(WebPage.processed >= 1)
            .order_by(WebPage.id)
            .limit(limit)
            .all()
        )

@st.cache_data(ttl=30)
def load_article_detail(page_id: int):
    from database.models import WebPage, get_session
    with get_session() as session:
        return session.query(WebPage).filter(WebPage.id == page_id).first()

pages = load_articles(200)

if not pages:
    st.info("暂无已分词数据。请先运行爬虫和分析管道。")
    st.stop()

# Build summary table
rows = []
for p in pages:
    rows.append({
        "ID": p.id,
        "标题": (p.title or "")[:60],
        "来源": p.source_site,
        "文本长度": p.text_length,
        "jieba词数": len(json.loads(p.seg_jieba)) if p.seg_jieba else 0,
        "maxmatch词数": len(json.loads(p.seg_maxmatch)) if p.seg_maxmatch else 0,
        "dp词数": len(json.loads(p.seg_dp)) if p.seg_dp else 0,
        "情感": {"positive":"😊","negative":"😞","neutral":"😐"}.get(p.sentiment_label, "😐"),
        "情感分": p.sentiment_score,
    })

df = pd.DataFrame(rows)

# Selection column
st.markdown("点击行选择文章 → 下方显示三种分词结果对比")
event = st.dataframe(
    df, width="stretch", hide_index=True,
    column_config={"ID": st.column_config.NumberColumn(width="small")},
    selection_mode="single-row",
    on_select="rerun",
    key="article_table",
)

# Get selected row
selected_rows = event.selection.rows if hasattr(event, 'selection') else []
selected_id = None
if selected_rows:
    selected_id = int(df.iloc[selected_rows[0]]["ID"])

# ---- Detail Panel ----
if selected_id:
    page = load_article_detail(selected_id)
    if page:
        st.markdown("---")
        st.markdown(f"### 📄 文章 #{page.id} 详情")

        # Meta info
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.metric("文本长度", f"{page.text_length:,}")
        with col_m2:
            st.metric("来源", page.source_site)
        with col_m3:
            label_map = {"positive":"😊正面","negative":"😞负面","neutral":"😐中性"}
            st.metric("情感", label_map.get(page.sentiment_label, "N/A"))
        with col_m4:
            st.metric("敏感性", f"{page.sensitivity_score:.3f}")

        # Title
        st.markdown(f"**标题**: {page.title}")

        # ---- Three-column token comparison ----
        st.markdown("#### ✂️ 分词结果对比")

        t_jieba = json.loads(page.seg_jieba) if page.seg_jieba else []
        t_maxmatch = json.loads(page.seg_maxmatch) if page.seg_maxmatch else []
        t_dp = json.loads(page.seg_dp) if page.seg_dp else []

        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown(f"**🔵 jieba** — {len(t_jieba)} 词")
            st.markdown(
                '<div style="max-height:400px;overflow-y:auto;background:#f0f5ff;'
                'padding:10px;border-radius:5px;font-size:14px;line-height:2;">'
                + " &nbsp;".join(t_jieba) + '</div>',
                unsafe_allow_html=True,
            )

        with c2:
            st.markdown(f"**🟢 最大匹配 BiMM** — {len(t_maxmatch)} 词")
            st.markdown(
                '<div style="max-height:400px;overflow-y:auto;background:#f0fff0;'
                'padding:10px;border-radius:5px;font-size:14px;line-height:2;">'
                + " &nbsp;".join(t_maxmatch) + '</div>',
                unsafe_allow_html=True,
            )

        with c3:
            st.markdown(f"**🟣 DP最短路径** — {len(t_dp)} 词")
            st.markdown(
                '<div style="max-height:400px;overflow-y:auto;background:#faf0ff;'
                'padding:10px;border-radius:5px;font-size:14px;line-height:2;">'
                + " &nbsp;".join(t_dp) + '</div>',
                unsafe_allow_html=True,
            )

        # ---- Analysis Scores ----
        st.markdown("#### 📊 分析结果")
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.metric("敏感性分数", f"{page.sensitivity_score:.3f}",
                      delta="敏感" if page.sensitivity_score > 0.05 else "安全")
        with col_s2:
            emoji = {"positive":"😊","negative":"😞","neutral":"😐"}.get(page.sentiment_label,"")
            st.metric("情感分数", f"{page.sentiment_score:+.3f}", delta=f"{emoji} {page.sentiment_label}")
        with col_s3:
            st.metric("有害分数", f"{page.harmful_score:.3f}",
                      delta="⚠️ 有害" if page.harmful_is_harmful else "✅ 安全")

        # Text preview
        with st.expander("查看原始文本"):
            st.text(page.clean_text[:3000] if page.clean_text else "(无内容)")

        # Sentiment detail
        with st.expander("查看情感分析详情"):
            if page.sentiment_details:
                detail = json.loads(page.sentiment_details)
                st.json(detail)
            else:
                st.info("暂无详情")

st.markdown("---")
st.caption("提示: 点击表格中的行选择文章，下方自动显示分词对比详情")
