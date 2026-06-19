"""
有害信息快速检测模块（重写版）

三层过滤架构 + 分词token输入：

Layer 1 — 正则表达式（原始文本，匹配手机号/URL等字符级模式）
Layer 2 — AC自动机关键词（token边界匹配，用哨兵符连接）
Layer 3 — 上下文规则评分（结合L1+L2结果）
"""

import re
from dataclasses import dataclass, field

import ahocorasick

from config.settings import HARMFUL_THRESHOLD
from utils.logger import logger

# ================================================================
# Layer 1: Regex patterns (same as before, runs on raw text)
# ================================================================
REGEX_PATTERNS = {
    "url_link": {
        "pattern": re.compile(r"https?://[^\s]{4,}", re.IGNORECASE),
        "weight": 0.3, "label": "推广链接",
    },
    "phone_cn": {
        "pattern": re.compile(r"1[3-9]\d{9}"),
        "weight": 0.5, "label": "手机号码",
    },
    "qq_number": {
        "pattern": re.compile(r"[Qq]{2}[：:\s]*\d{5,11}"),
        "weight": 0.3, "label": "QQ号码",
    },
    "wechat_id": {
        "pattern": re.compile(r"(微信|v信|薇信|VX|wx|WX)[：:\s]*[a-zA-Z0-9_\-一-鿿]{3,20}"),
        "weight": 0.3, "label": "微信号",
    },
    "bank_card": {
        "pattern": re.compile(r"\d{16,19}"),
        "weight": 0.4, "label": "银行卡号",
    },
    "spam_words": {
        "pattern": re.compile(r"(加[Qq薇微]|免费领取|点击下载|立即注册|限时优惠|名额有限)"),
        "weight": 0.4, "label": "垃圾推广",
    },
}

# ================================================================
# Layer 2: Harmful keywords (expanded)
# ================================================================
HARMFUL_KEYWORDS = {
    "porn": {
        "words": [
            "成人视频","激情裸聊","色情直播","在线看片","福利视频",
            "一夜情","约炮","招嫖","卖淫","裸聊","国产AV","成人网站",
            "情色","黄色视频","三级片","色情","淫秽","色诱","裸体",
            "艳照","偷拍","走光","激情视频","淫荡","乱伦","强奸",
            "猥亵","性爱","自慰","偷情","援交","性工作者",
        ],
        "weight": 0.8,
    },
    "gambling": {
        "words": [
            "真人赌场","在线赌博","六合彩","时时彩","百家乐",
            "赌球","外围投注","老虎机","博彩平台","网上赌场",
            "澳门赌场","赌博网站","体育博彩","赌场","博彩","赌",
            "棋牌赌博","扑克赌博","轮盘赌","押注","赌资","赌马",
            "百家乐","龙虎斗","骰宝","德州扑克赌博",
        ],
        "weight": 0.8,
    },
    "fraud": {
        "words": [
            "兼职刷单","日赚","月入过万","躺赚","轻松赚钱",
            "套现","代办信用卡","无抵押贷款","高利贷",
            "杀猪盘","电信诈骗","中奖信息","恭喜中奖",
            "免费领取","限时领取","不转不是","转发到",
            "刷单","诈骗","骗局","传销","非法集资","庞氏骗局",
            "钓鱼网站","虚假广告","假冒","仿冒","伪劣",
            "代开发票","信用卡套现","套路贷",
            "冒充公检法","洗钱","黑产","恶意营销","诱导消费",
        ],
        "weight": 0.7,
    },
    "violence": {
        "words": [
            "雇凶杀人","买凶","杀手","枪支","弹药","砍人","施暴",
            "打人视频","暴力视频","杀人","砍人","枪击","爆炸",
            "恐怖袭击","恐怖分子","绑架","勒索","纵火","投毒",
            "斩首","虐杀","酷刑","肢解","血腥","凶杀","碎尸",
            "屠殺","暴行","行凶","斗殴","黑帮","暗杀",
        ],
        "weight": 0.8,
    },
    "spam_marketing": {
        "words": [
            "加微信","加QQ群","进群","免费课程","限量免费",
            "名额有限","手慢无","速抢","点击购买","立即下单",
            "限时抢购","优惠券","满减","包邮","秒杀",
        ],
        "weight": 0.4,
    },
}


@dataclass
class HarmfulResult:
    score: float = 0.0
    is_harmful: bool = False
    flags: list[str] = field(default_factory=list)
    layer1_matches: list[dict] = field(default_factory=list)
    layer2_matches: list[dict] = field(default_factory=list)
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "score": self.score, "is_harmful": self.is_harmful,
            "flags": self.flags, "layer1_matches": self.layer1_matches,
            "layer2_matches": self.layer2_matches, "details": self.details,
        }


class HarmfulDetector:
    """三层有害信息检测器。

    detect(tokens, raw_text) — tokens用于Layer2词边界匹配，raw_text用于Layer1正则。
    """

    SENTINEL = "\x00"

    def __init__(self):
        self._layer2_automaton = None
        self._layer2_meta: dict[int, dict] = {}
        self._init_layer2()
        total_kw = sum(len(v["words"]) for v in HARMFUL_KEYWORDS.values())
        logger.info(f"HarmfulDetector: {len(REGEX_PATTERNS)} regex + {total_kw} keywords")

    def _init_layer2(self):
        self._layer2_automaton = ahocorasick.Automaton()
        word_id = 0
        for category, data in HARMFUL_KEYWORDS.items():
            for word in data["words"]:
                self._layer2_automaton.add_word(word, (word_id, word))
                self._layer2_meta[word_id] = {
                    "word": word, "category": category, "weight": data["weight"],
                }
                word_id += 1
        self._layer2_automaton.make_automaton()

    def _layer1_detect(self, raw_text: str) -> tuple[list[dict], float]:
        matches, total = [], 0.0
        for name, config in REGEX_PATTERNS.items():
            found = config["pattern"].findall(raw_text)
            if found:
                count = min(len(found), 5)
                contrib = config["weight"] * count
                total += contrib
                matches.append({
                    "type": name, "label": config["label"],
                    "count": len(found), "weight": config["weight"],
                    "contribution": round(contrib, 3), "samples": found[:3],
                })
        return matches, min(1.0, total / 3.0)

    def _layer2_detect(self, tokens: list[str]) -> tuple[list[dict], float]:
        scan_text = self.SENTINEL + self.SENTINEL.join(tokens) + self.SENTINEL
        matches_raw: dict[int, dict] = {}
        for end_idx, (word_id, word) in self._layer2_automaton.iter(scan_text):
            # 词边界验证
            start = end_idx - len(word) + 1
            if start > 0 and scan_text[start - 1] != self.SENTINEL:
                continue
            if end_idx < len(scan_text) - 1 and scan_text[end_idx + 1] != self.SENTINEL:
                continue

            if word_id in matches_raw:
                matches_raw[word_id]["count"] += 1
            else:
                meta = self._layer2_meta.get(word_id, {})
                matches_raw[word_id] = {
                    "word": word, "category": meta.get("category", "unknown"),
                    "weight": meta.get("weight", 0.5), "count": 1,
                }

        total, matches = 0.0, []
        for m in matches_raw.values():
            count_capped = min(m["count"], 5)
            contrib = m["weight"] * count_capped * 0.15
            total += contrib
            matches.append({**m, "contribution": round(contrib, 3)})
        return matches, min(1.0, total)

    def _layer3_context(self, l1_matches, l2_matches, l1_score, l2_score):
        l1_types = {m["type"] for m in l1_matches}
        l2_cats = {m["category"] for m in l2_matches}
        flags, rules, bonus = [], [], 0.0

        if "gambling" in l2_cats and ("phone_cn" in l1_types or "qq_number" in l1_types or "wechat_id" in l1_types):
            bonus += 0.3; flags.append("gambling"); rules.append("赌博+联系方式")
        if "fraud" in l2_cats and "bank_card" in l1_types:
            bonus += 0.3; flags.append("fraud"); rules.append("欺诈+银行卡")
        if "fraud" in l2_cats and ("phone_cn" in l1_types or "qq_number" in l1_types):
            bonus += 0.2
            if "fraud" not in flags: flags.append("fraud")
            rules.append("欺诈+联系方式")
        if "porn" in l2_cats and ("phone_cn" in l1_types or "qq_number" in l1_types or "wechat_id" in l1_types or "url_link" in l1_types):
            bonus += 0.25; flags.append("porn"); rules.append("色情+联系方式")
        if "spam_marketing" in l2_cats and len(l1_matches) >= 2:
            bonus += 0.15
            if "spam" not in flags: flags.append("spam")
            rules.append("多条推广")
        if "violence" in l2_cats:
            bonus += 0.2; flags.append("violence"); rules.append("暴力关键词")

        final_score = min(1.0, l1_score * 0.3 + l2_score * 0.4 + bonus * 0.3)
        return final_score, flags, "; ".join(rules) if rules else ""

    def detect(self, tokens: list[str], raw_text: str = "") -> HarmfulResult:
        """对分词token列表进行有害信息检测。

        Args:
            tokens: 分词后的token列表。
            raw_text: 原始文本（用于Layer1正则匹配），可选。
        """
        if not tokens or len(tokens) < 3:
            return HarmfulResult()

        l1_matches, l1_score = self._layer1_detect(raw_text or "".join(tokens))
        l2_matches, l2_score = self._layer2_detect(tokens)
        final_score, flags, details = self._layer3_context(l1_matches, l2_matches, l1_score, l2_score)

        return HarmfulResult(
            score=round(final_score, 4),
            is_harmful=final_score >= HARMFUL_THRESHOLD,
            flags=flags, layer1_matches=l1_matches,
            layer2_matches=l2_matches, details=details,
        )

    def batch_detect(self, token_lists: list[list[str]], raw_texts: list[str] = None) -> list[HarmfulResult]:
        if raw_texts is None:
            raw_texts = [""] * len(token_lists)
        return [self.detect(tokens, raw) for tokens, raw in zip(token_lists, raw_texts)]
