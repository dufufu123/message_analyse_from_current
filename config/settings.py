# ============================================================
# Global Configuration
# ============================================================

import os
from pathlib import Path

# ---- Paths ----
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
MODELS_DIR = DATA_DIR / "models"
FIGURES_DIR = DATA_DIR / "figures"

# ---- Database ----
DATABASE_PATH = BASE_DIR / "data" / "text_security.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# ---- Crawler Settings ----
CRAWLER_SETTINGS = {
    "concurrent_requests": 16,
    "download_delay": 0.5,
    "randomize_download_delay": True,
    "user_agent_rotate": True,
    "obey_robots_txt": True,
    "autothrottle_enabled": True,
    "autothrottle_start_delay": 1,
    "autothrottle_max_delay": 10,
    "target_pages_per_site": 20000,   # ~20K pages per site × 10 sites = 200K
    "retry_times": 3,
    "download_timeout": 15,
}

# ---- Segmentation Settings ----
SEGMENTATION_MAX_WORD_LEN = 5  # Max word length for max-match algorithms
PAUSE_WORDS_FILE = BASE_DIR / "segmentation" / "stopwords.txt"
SENSITIVE_WORDS_FILE = BASE_DIR / "config" / "sensitive_words.txt"

# ---- Analysis Settings ----
SENSITIVITY_CATEGORIES = {
    "politics": {"weight": 1.0, "label": "政治敏感"},
    "pornography": {"weight": 1.0, "label": "色情内容"},
    "violence": {"weight": 0.8, "label": "暴力内容"},
    "gambling": {"weight": 0.8, "label": "赌博信息"},
    "fraud": {"weight": 0.9, "label": "欺诈信息"},
}

SENTIMENT_THRESHOLDS = {
    "negative_max": 0.35,   # < 0.35 → negative
    "positive_min": 0.65,   # > 0.65 → positive
}

HARMFUL_THRESHOLD = 0.3  # Score > 0.3 → flagged as harmful

# ---- EDA Settings ----
EDA_SAMPLE_SIZE = 100000  # Max records to load for EDA visualization

# ---- Streamlit Settings ----
STREAMLIT_TITLE = "文本内容安全系统"
STREAMLIT_LAYOUT = "wide"

# ---- Logging ----
LOG_LEVEL = "INFO"
LOG_FILE = BASE_DIR / "app.log"
