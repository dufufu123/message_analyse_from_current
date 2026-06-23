# 🛡️ 文本内容安全系统(message_analyse_from_current)

> **快速获取最新的网页信息并检测内容安全**

---

## 📐 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Streamlit 交互层 (7页面)                        │
│  首页仪表盘 爬虫控制  EDA可视化  分词对比  敏感性检测  情感分析  有害检测  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│                        业务逻辑层                                    │
│  ┌─────────────────┐ ┌──────────────────┐ ┌────────────────────┐    │
│  │ 分词算法          │ │ 内容分析           │ │ EDA可视化          │    │
│  │① jieba (词典+HMM)│ │ sensitivity.py    │ │ statistics.py     │    │
│  │② MaxMatch (自定义)│ │ AC自动机+5类敏感词  │ │ 10种统计指标       │    │
│  │③ DP Unigram (自定义)│ │ sentiment.py      │ │ visualize.py      │    │
│  │                  │ │ 985词情感词典+否定   │ │ plotly+matplotlib │    │
│  │ comparator.py    │ │ 窗口+程度副词       │ │                   │    │
│  │ preprocessor.py  │ │ harmful_detector.py│ │                   │    │
│  └─────────────────┘ │ 三层过滤(L1正则→    │ └────────────────────┘    │
│                       │ L2关键词→L3规则)    │                           │
│                       │ report.py          │                           │
│                       └────────────────────┘                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│                         数据采集层                                    │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │           5 种采集方式 (65站点)                               │    │
│  │    RSS     Sitemap    归档页翻页   首页抓取   DOM直采翻页     │    │
│  │    (最新)   (全量)     (规模化)    (兜底)   (200页/站)      │    │
│  └──────────────────────────────────────────────────────────────┘    │
│  中间件: UA轮换 / 自动节流 / 重试  |  Pipeline → 批量写入SQLite      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│                        数据存储层                                     │
│                    SQLite + SQLAlchemy                               │
│  web_pages(id, url, title, clean_text, source_site, category,       │
│            seg_jieba, seg_maxmatch, seg_dp,                          │
│            sensitivity_score, sentiment_score, harmful_score,        │
│            sentiment_details, sensitivity_details, harmful_details,  │
│            processed, analysis_seg_source)                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 数据流

```
发现链接 (RSS/Sitemap/归档翻页) → 去重 → 下载文章页 → 清洗正文
                                                      ↓
                                              三种分词: jieba / MaxMatch / DP
                                                      ↓
                                          基于分词的三大分析:
                                          🔍 AC自动机敏感检测
                                          💬 情感词典+否定窗口+程度词
                                          🛡️ 三层过滤有害检测
                                                      ↓
                                           Streamlit 7页面展示
```

---

## 📂 项目文件结构

```
project-trainning-3/
├── app.py                          # Streamlit 主入口
├── requirements.txt                # Python 依赖
├── .gitignore
├── config/
│   ├── settings.py                 # 全局配置
│   ├── sensitive_words.txt         # 敏感词库 (5类140词)
│   ├── negation_words.txt          # 否定词列表
│   └── intensifier_words.txt       # 程度副词+倍率
├── crawler/
│   ├── site_profiles.py            # 站点配置 (RSS/Sitemap/选择器)
│   ├── link_discovery.py           # 链接发现 (RSS→Sitemap→归档→首页)
│   ├── items.py / pipelines.py / middlewares.py / settings.py
│   ├── run_crawler.py              # 编排 (discover/crawl/direct/cycle)
│   ├── direct_sites/configs.py     # DOM直采站点配置 (翻页模板)
│   └── spiders/
│       ├── universal_spider.py     # 通用爬虫 (RSS/归档/首页模式)
│       └── direct_spider.py        # 直采爬虫 (DOM翻页模式)
├── database/
│   ├── models.py                   # WebPage ORM (分析字段+详情JSON)
│   ├── connection.py               # 查询辅助
│   └── models.py                   # WebPage ORM
├── segmentation/                   # 三种分词算法
│   ├── preprocessor.py             # 文本预处理
│   ├── algorithm_jieba.py          # ① jieba (词典DAG+HMM)
│   ├── algorithm_max_match.py      # ② FMM/BMM/BiMM (自定义)
│   ├── algorithm_dp.py             # ③ DP最短路径 (自定义)
│   ├── comparator.py               # 三算法对比评估器
│   └── stopwords.txt
├── analysis/                       # 内容分析模块
│   ├── lexicon_loader.py           # 情感词典加载器
│   ├── sentiment.py                # 情感分析 (985词词典+否定窗口+程度)
│   ├── sensitivity.py              # 敏感性检测 (AC自动机+5类)
│   ├── harmful_detector.py         # 有害检测 (三层过滤)
│   └── report.py                   # 批量处理管道
├── eda/
│   ├── statistics.py               # 统计分析
│   └── visualize.py                # plotly+matplotlib 可视化
├── pages/                          # Streamlit 6页面
│   ├── 01_🕷️_爬虫控制.py
│   ├── 02_📊_EDA可视化.py
│   ├── 03_✂️_分词对比.py
│   ├── 04_🔍_敏感性检测.py
│   ├── 05_💬_情感分析.py
│   └── 06_🛡️_有害信息检测.py
├── utils/
│   ├── logger.py / text_cleaner.py
└── data/
    ├── lexicon/sentiment_lexicon.tsv  # 情感词典 (git追踪)
    ├── raw/ / processed/ / models/ / figures/ (git忽略)
```

---

## 🔬 三种分词算法对比

| # | 算法 | 原理 | 实现 | 特点 |
|---|------|------|------|------|
| ① | **jieba** | 词典DAG + 动态规划 + HMM | 开源库封装 | 工业级，速度快 |
| ② | **MaxMatch** | FMM/BMM/BiMM 贪心最大匹配 | **自定义 ~260行** | 三种变体对比，答辩亮点 |
| ③ | **DP Unigram** | Unigram概率 + DP最短路径 | **自定义 ~230行** | 全局最优解 |

---

## 💬 情感分析算法

```
输入: token列表 (jieba分词)
输出: 情感极性 (-1~+1) + 置信度

对于每个情感词 token:
  1. 从985词词典查 base_polarity
  2. 否定窗口 [i-3, i-1] → 奇数个否定词 → polarity × (-0.7)
  3. 程度窗口 [i-2, i-1] → 累乘强度系数 (0.2~3.0)
  4. 汇总: score = tanh(Σ adjusted_polarity / sqrt(n+1))
```

---

## 🚀 快速开始

### 依赖安装

```bash
pip install -r requirements.txt
python -c "from database.models import init_database; init_database()"
```

### 运行爬虫

#### 一键命令

| 模式 | 命令 | 说明 |
|------|------|------|
| 🔄 全流程 | `python crawler/run_crawler.py` | discover + crawl 一键执行 |
| 🧪 快速测试 | `python crawler/run_crawler.py --quick` | 每站~30条URL，1-2分钟验证流程 |
| 🚀 循环采集 | `python crawler/run_crawler.py cycle` | 自动循环发现+抓取，直到20万条目标 |
| ⚡ 快速循环 | `python crawler/run_crawler.py cycle --quick` | 快速循环模式，5000条目标 |

#### 分步命令

| 阶段 | 命令 | 说明 |
|------|------|------|
| 📡 发现链接（全站） | `python crawler/run_crawler.py discover` | RSS → Sitemap → 归档页 → 首页，四种方式覆盖65站点 |
| 📡 发现链接（指定站） | `python crawler/run_crawler.py discover cnblogs` | 只发现 cnblogs 的链接 |
| 🕷️ 抓取文章（全站） | `python crawler/run_crawler.py crawl` | 从 discovered_urls.json 加载URL，通用爬虫抓取 |
| 🕷️ 抓取文章（指定站） | `python crawler/run_crawler.py crawl cnblogs` | 只抓取 cnblogs 的文章 |
| 🔍 DOM直采 | `python crawler/run_crawler.py direct` | 翻页直采模式（单次），适合列表页站点 |
| 🔍 DOM直采（指定站） | `python crawler/run_crawler.py direct cnblogs` | 只直采 cnblogs |
| ♾️ 直采循环 | `python crawler/run_crawler.py direct --loop` | 直采模式自动循环到20万 |
| 📋 站点列表 | `python crawler/run_crawler.py list` | 查看65个站点配置（RSS/Sitemap/类别） |

### 数据库查询

```bash
# 查看数据库整体统计
python -c "from database.connection import get_db_stats; import json; print(json.dumps(get_db_stats(), indent=2))"

# 查看各来源站点分布
python -c "from database.connection import get_source_site_stats; print(get_source_site_stats())"
```

### 分析管道

```bash
# 处理全部未分析页面（分词 → 敏感 → 情感 → 有害）
python -c "from analysis.report import BatchProcessor; BatchProcessor().process_all()"

# 限制处理数量（测试用）
python -c "from analysis.report import BatchProcessor; BatchProcessor().process_all(max_pages=500)"

# 生成汇总报告
python -c "from analysis.report import generate_summary_report; import json; print(json.dumps(generate_summary_report(), ensure_ascii=False, indent=2))"
```

### 启动Web应用

```bash
streamlit run app.py
```

浏览器打开 `http://localhost:8501`

7个页面：首页仪表盘 → 爬虫控制 → EDA可视化 → 分词对比 → 敏感性检测 → 情感分析 → 有害信息检测

---

## 🧪 快速测试 (Python Console)

### 分词

```python
from segmentation.algorithm_jieba import JiebaSegmenter
from segmentation.algorithm_max_match import MaxMatchSegmenter
from segmentation.algorithm_dp import DPUnigramSegmenter

t = '文本内容安全系统是工程实训的重要课题'
print('/'.join(JiebaSegmenter().segment(t)))
print('/'.join(MaxMatchSegmenter().segment(t)))
print('/'.join(DPUnigramSegmenter().segment(t)))

# 批量分词
jieba = JiebaSegmenter()
print(jieba.batch_segment(['今天天气真好', '我们在学习Python编程']))
```

### 情感分析 (基于分词token)

```python
from analysis.sentiment import SentimentAnalyzer
from segmentation.algorithm_jieba import JiebaSegmenter

seg = JiebaSegmenter()
analyzer = SentimentAnalyzer()

# 单条分析 — 必须先分词
tokens = seg.segment('这个产品非常好用，我很喜欢')
result = analyzer.analyze(tokens)
print(result.label, result.score, result.confidence)

# 批量分析
texts = ['这个产品非常好用', '服务太差了，非常失望']
tokens_list = seg.batch_segment(texts)
results = analyzer.batch_analyze(tokens_list)
for r in results:
    print(r.label, r.score)
```

### 敏感性检测 (基于分词token)

```python
from analysis.sensitivity import SensitivityDetector
from segmentation.algorithm_jieba import JiebaSegmenter

seg = JiebaSegmenter()
detector = SensitivityDetector()

# 单条检测 — 必须先分词
tokens = seg.segment('提供各种赌博服务，加QQ投注六合彩')
result = detector.detect(tokens)
print(result.score, result.flags, result.matched_words)

# 批量检测
tokens_list = seg.batch_segment(['提供赌博服务', '正常新闻内容'])
results = detector.batch_detect(tokens_list)
```

### 有害信息检测 (基于分词token + 原始文本)

```python
from analysis.harmful_detector import HarmfulDetector
from segmentation.algorithm_jieba import JiebaSegmenter

seg = JiebaSegmenter()
detector = HarmfulDetector()

text = '加微信免费领取，兼职刷单日赚1000，银行卡号6222021234567890'
tokens = seg.segment(text)
result = detector.detect(tokens, raw_text=text)
print(result.score, result.is_harmful, result.flags)
print('Layer1(正则):', result.layer1_matches)
print('Layer2(关键词):', result.layer2_matches)
```

### EDA 统计

```python
from eda.statistics import load_dataframe, site_distribution, word_frequency_from_seg

df = load_dataframe()
print(site_distribution(df))
print(word_frequency_from_seg(df, algorithm='jieba', top_n=20))
```

---

## 📊 技术栈

| 模块 | 技术 | 详细 |
|------|------|------|
| 爬虫 | Scrapy + RSS + DOM直采 | 65站点，5种发现方式，并发采集+去重 |
| 数据库 | SQLite + SQLAlchemy | 零配置单文件 |
| 分词 | jieba / 自定义MaxMatch / 自定义DP | 三种方法论完全不同 |
| 情感分析 | 词情感词典 + 否定窗口 + 程度副词 | 基于分词token的词边界匹配 |
| 敏感检测 | pyahocorasick (AC自动机) | O(n+m+z) 词边界匹配 |
| 有害检测 | 三层过滤 (正则→AC→规则) | 200K记录数分钟完成 |
| 可视化 | Plotly + Matplotlib + WordCloud | 交互+静态双轨 |
| Web应用 | Streamlit 1.58 | 纯Python零前端 |

---

## 🎯 需求对照

| 实验要求 | 实现情况 |
|----------|----------|
| 爬虫10+网站，20万+网页，EDA | ✅ 65站点，双模式爬虫(通用+直采)，10种EDA图表 |
| 3种分词算法 + 预处理 | ✅ jieba + 自定义MaxMatch(FMM/BMM/BiMM) + 自定义DP最短路径 |
| 敏感性检测 + 情感分析 + 有害检测 + 交互应用 | ✅ AC自动机(词边界) + 情感词典(985词+否定+程度) + 三层过滤 + Streamlit 7页面 |
