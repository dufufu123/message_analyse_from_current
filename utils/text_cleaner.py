"""
Text cleaning and normalization utilities for Chinese web text.
"""

import re
import html


def clean_html(raw_html: str) -> str:
    """Strip HTML tags and decode entities, returning plain text.

    Args:
        raw_html: Raw HTML string.

    Returns:
        Cleaned plain text with HTML removed.
    """
    # Remove <script> and <style> blocks (including inline content)
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode HTML entities like &amp; &nbsp; &#x...;
    text = html.unescape(text)
    return text


def normalize_whitespace(text: str) -> str:
    """Collapse multiple whitespace chars into a single space, strip leading/trailing.

    Args:
        text: Input text.

    Returns:
        Whitespace-normalized text.
    """
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_punctuation(text: str) -> str:
    """Convert full-width punctuation to half-width where appropriate,
    and normalize Chinese punctuation variants.

    Args:
        text: Input text (Chinese or mixed).

    Returns:
        Text with normalized punctuation.
    """
    # Full-width digits → half-width
    full_to_half = str.maketrans(
        "０１２３４５６７８９ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
        "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    )
    text = text.translate(full_to_half)
    return text


def remove_noise(text: str) -> str:
    """Remove common web noise: URLs, email addresses, excessive numbers/symbols.

    Args:
        text: Input text.

    Returns:
        Cleaned text.
    """
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove email addresses
    text = re.sub(r"\S+@\S+", "", text)
    # Remove lines that are mostly non-Chinese (navigation menus, footers, etc.)
    lines = text.split("\n")
    filtered_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Count Chinese characters
        chinese_chars = len(re.findall(r"[一-鿿]", line))
        total_chars = len(line.replace(" ", ""))
        if total_chars == 0:
            continue
        # Keep lines with >10 chars or >30% Chinese content
        if total_chars > 10 or (total_chars > 0 and chinese_chars / total_chars > 0.3):
            filtered_lines.append(line)
    return "\n".join(filtered_lines)


def clean_text(raw_html: str) -> str:
    """Full text cleaning pipeline: HTML → plain text → normalize → de-noise.

    Args:
        raw_html: Raw HTML content.

    Returns:
        Clean, normalized Chinese plain text ready for segmentation.
    """
    text = clean_html(raw_html)
    text = normalize_whitespace(text)
    text = normalize_punctuation(text)
    text = remove_noise(text)
    return text
