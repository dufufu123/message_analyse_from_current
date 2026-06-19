"""
EDA Visualization module.
Generates static (matplotlib) and interactive (plotly) charts
for the 10 required visualization types.
"""

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for file saving
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud

from config.settings import FIGURES_DIR
from utils.logger import logger

# ---- Font setup for Chinese characters ----
# Try to find a Chinese font; fall back gracefully
_CHINESE_FONT = None
_POSSIBLE_FONTS = [
    "SimHei", "Microsoft YaHei", "WenQuanYi Micro Hei",
    "Noto Sans CJK SC", "Source Han Sans SC", "STHeiti",
    "Arial Unicode MS", "DejaVu Sans",
]

for _font_name in _POSSIBLE_FONTS:
    try:
        fm.findfont(_font_name, fallback_to_default=False)
        _CHINESE_FONT = _font_name
        break
    except Exception:
        continue

if _CHINESE_FONT:
    plt.rcParams["font.family"] = _CHINESE_FONT
    plt.rcParams["font.sans-serif"] = [_CHINESE_FONT]
plt.rcParams["axes.unicode_minus"] = False  # Fix minus sign display

# Ensure output directory exists
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def _save_mpl(filename: str, dpi: int = 150) -> str:
    """Save current matplotlib figure and close."""
    path = FIGURES_DIR / filename
    plt.tight_layout()
    plt.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close()
    return str(path)


# ================================================================
# Plotly (interactive) chart functions — return plotly Figure
# ================================================================

def plot_site_distribution(stats_df: pd.DataFrame) -> go.Figure:
    """Bar chart: page count per source site."""
    fig = px.bar(
        stats_df,
        x="source_site",
        y="count",
        title="各网站页面数量分布",
        labels={"source_site": "来源网站", "count": "页面数量"},
        color="count",
        color_continuous_scale="Viridis",
    )
    fig.update_layout(xaxis_tickangle=-45)
    return fig


def plot_category_pie(stats_df: pd.DataFrame) -> go.Figure:
    """Pie chart: category distribution."""
    fig = px.pie(
        stats_df,
        names="category",
        values="count",
        title="网页类别分布",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    return fig


def plot_text_length_histogram(df: pd.DataFrame, bins: int = 50) -> go.Figure:
    """Histogram: text length distribution."""
    fig = px.histogram(
        df,
        x="text_length",
        nbins=bins,
        title="文本长度分布",
        labels={"text_length": "文本长度（字符数）", "count": "频数"},
        color_discrete_sequence=["#636EFA"],
        marginal="box",
    )
    return fig


def plot_text_length_by_source(stats_df: pd.DataFrame) -> go.Figure:
    """Grouped bar: mean text length per source site."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=stats_df["source_site"],
        y=stats_df["mean"],
        name="平均长度",
        error_y={"type": "data", "array": stats_df["std"], "visible": True},
        marker_color="#636EFA",
    ))
    fig.update_layout(
        title="各网站平均文本长度",
        xaxis_title="来源网站",
        yaxis_title="平均文本长度（字符）",
        xaxis_tickangle=-45,
    )
    return fig


def plot_time_trend(trend_df: pd.DataFrame) -> go.Figure:
    """Line chart: articles published over time."""
    fig = px.line(
        trend_df,
        x="date",
        y="count",
        title="文章发布时间趋势",
        labels={"date": "日期", "count": "文章数量"},
    )
    return fig


def plot_publish_hour(hour_df: pd.DataFrame) -> go.Figure:
    """Bar chart: publish hour distribution."""
    fig = px.bar(
        hour_df,
        x="hour",
        y="count",
        title="发布时段分布 (24小时)",
        labels={"hour": "小时", "count": "文章数量"},
        color="count",
    )
    return fig


def plot_word_frequency(freq_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar: top word frequencies."""
    fig = px.bar(
        freq_df.head(30),
        y="word",
        x="count",
        orientation="h",
        title="高频词汇 Top 30",
        labels={"word": "词汇", "count": "出现次数"},
        color="count",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return fig


def plot_site_category_heatmap(df: pd.DataFrame) -> go.Figure:
    """Heatmap: source_site × category cross-tab."""
    ct = pd.crosstab(df["source_site"], df["category"])
    fig = px.imshow(
        ct,
        title="网站-类别热力图",
        labels={"x": "类别", "y": "来源网站", "color": "页面数"},
        color_continuous_scale="YlOrRd",
        text_auto=True,
    )
    return fig


def plot_sentiment_pie(df: pd.DataFrame) -> go.Figure:
    """Pie chart: sentiment label distribution."""
    counts = df["sentiment_label"].value_counts().reset_index()
    counts.columns = ["label", "count"]
    fig = px.pie(
        counts,
        names="label",
        values="count",
        title="情感倾向分布",
        color_discrete_sequence=px.colors.qualitative.Set1,
    )
    return fig


def plot_harmful_by_site(stats_df: pd.DataFrame) -> go.Figure:
    """Bar chart: harmful content rate by site."""
    fig = px.bar(
        stats_df,
        x="source_site",
        y="harmful_rate",
        title="各网站有害内容比例",
        labels={"source_site": "来源网站", "harmful_rate": "有害比例"},
        color="harmful_rate",
        color_continuous_scale="Reds",
    )
    fig.update_layout(xaxis_tickangle=-45)
    return fig


# ================================================================
# Matplotlib (static) chart functions — save to file, return path
# ================================================================

def save_wordcloud_image(freq_df: pd.DataFrame) -> str:
    """Generate and save a Chinese word cloud image.

    Args:
        freq_df: DataFrame with 'word' and 'count' columns.

    Returns:
        Path to the saved PNG image.
    """
    word_freq = dict(zip(freq_df["word"], freq_df["count"]))

    # Use a font that supports Chinese if available
    font_path = None
    for fp in [
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]:
        if os.path.exists(fp):
            font_path = fp
            break

    wc_kwargs = {
        "width": 1200,
        "height": 800,
        "background_color": "white",
        "max_words": 200,
        "collocations": False,
    }
    if font_path:
        wc_kwargs["font_path"] = font_path

    wc = WordCloud(**wc_kwargs)
    wc.generate_from_frequencies(word_freq)

    path = FIGURES_DIR / "wordcloud.png"
    wc.to_file(str(path))
    logger.info(f"Word cloud saved to {path}")
    return str(path)


def save_text_length_histogram(df: pd.DataFrame, bins: int = 50) -> str:
    """Save static histogram of text lengths."""
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(df["text_length"].dropna(), bins=bins, color="#636EFA", alpha=0.8, edgecolor="white")
    ax.set_title("文本长度分布", fontsize=14)
    ax.set_xlabel("文本长度（字符数）")
    ax.set_ylabel("频数")
    return _save_mpl("text_length_hist.png")


def save_site_pie(stats_df: pd.DataFrame) -> str:
    """Save static pie chart for site distribution."""
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.pie(
        stats_df["count"],
        labels=stats_df["source_site"],
        autopct="%1.1f%%",
        startangle=140,
    )
    ax.set_title("各网站页面占比", fontsize=14)
    return _save_mpl("site_pie.png")


def save_missing_heatmap(missing_df: pd.DataFrame) -> str:
    """Save static heatmap for missing values."""
    fig, ax = plt.subplots(figsize=(10, 4))
    missing_nonzero = missing_df[missing_df["missing_count"] > 0]
    if missing_nonzero.empty:
        ax.text(0.5, 0.5, "无缺失数据", ha="center", va="center", fontsize=16)
    else:
        bars = ax.barh(missing_nonzero["column"], missing_nonzero["missing_pct"], color="#EF553B")
        ax.set_xlabel("缺失比例 (%)")
        ax.set_title("各字段缺失值比例", fontsize=14)
        ax.invert_yaxis()
    return _save_mpl("missing_heatmap.png")


def save_sentiment_bar(df: pd.DataFrame) -> str:
    """Save static bar chart for sentiment distribution."""
    counts = df["sentiment_label"].value_counts()
    fig, ax = plt.subplots(figsize=(8, 6))
    colors = {"positive": "#00CC96", "negative": "#EF553B", "neutral": "#636EFA"}
    bar_colors = [colors.get(label, "#AB63FA") for label in counts.index]
    ax.bar(counts.index, counts.values, color=bar_colors, edgecolor="white")
    ax.set_title("情感倾向统计", fontsize=14)
    ax.set_xlabel("情感倾向")
    ax.set_ylabel("数量")
    return _save_mpl("sentiment_bar.png")


def generate_all_static_charts(df: pd.DataFrame, freq_df: pd.DataFrame | None = None):
    """Generate all required static charts.

    Args:
        df: Full data DataFrame.
        freq_df: Optional word frequency DataFrame for word cloud.
    """
    logger.info("Generating static EDA charts...")
    try:
        save_text_length_histogram(df)
    except Exception as e:
        logger.warning(f"text_length_hist failed: {e}")

    try:
        site_stats = df.groupby("source_site").size().reset_index(name="count")
        save_site_pie(site_stats)
    except Exception as e:
        logger.warning(f"site_pie failed: {e}")

    try:
        from eda.statistics import missing_values_report
        missing_df = missing_values_report(df)
        save_missing_heatmap(missing_df)
    except Exception as e:
        logger.warning(f"missing_heatmap failed: {e}")

    try:
        save_sentiment_bar(df)
    except Exception as e:
        logger.warning(f"sentiment_bar failed: {e}")

    if freq_df is not None and not freq_df.empty:
        try:
            save_wordcloud_image(freq_df)
        except Exception as e:
            logger.warning(f"wordcloud failed: {e}")

    logger.info(f"Static charts saved to {FIGURES_DIR}")
