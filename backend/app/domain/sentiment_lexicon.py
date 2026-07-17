"""輕量中文財經新聞情緒分類（詞典 net-score 法，免 LLM 成本）。

用途：news_metadata.sentiment 在 ingestion 時分類（原本 100% 未計算 → 99.7% unknown，
情緒分佈圖恆空）。這是「市場情緒概況」的粗略指標（非交易訊號；真正的深度情緒面分析由
分析流程的 SentimentAnalyst LLM 負責）。

設計取捨（保守優先，寧可 neutral 也不要 confident-but-wrong）：
- 標題含明確利多/利空關鍵詞才給 positive/negative；訊號互相抵銷或無訊號 → neutral。
- 先處理少數「反轉語」（止跌、跌深反彈、不看好…）避免被單一字誤導。
- 只看標題 + 摘要；回 (label, score)，label ∈ positive/neutral/negative，score ∈ [-1,1]。

⚠️ 這是關鍵詞近似，不是語意模型；當「概況」用途足夠，但個別標題可能誤判。
"""

from __future__ import annotations

# 反轉語：先移除，避免其中的單字（如「跌」）被當成反向訊號
# （例：「止跌」「跌深反彈」是偏正面，「不看好」是偏負面）。
_POSITIVE_PHRASES = ("止跌", "跌深反彈", "跌深買盤", "低接", "逢低", "轉盈", "轉虧為盈", "扭虧")
_NEGATIVE_PHRASES = ("不看好", "不樂觀", "漲多拉回", "漲多回檔", "獲利了結", "利多出盡", "由盈轉虧")

# 利多關鍵詞（含權重：強訊號 2、一般 1）
_POSITIVE = {
    2: (
        "大漲",
        "飆",
        "漲停",
        "創新高",
        "新高",
        "大賺",
        "獲利創新高",
        "營收創新高",
        "優於預期",
        "超乎預期",
        "看俏",
    ),
    1: (
        "漲",
        "攻",
        "走高",
        "上揚",
        "走揚",
        "反彈",
        "回升",
        "翻紅",
        "成長",
        "增溫",
        "獲利",
        "大幅成長",
        "看好",
        "樂觀",
        "加碼",
        "買超",
        "調升",
        "上調",
        "受惠",
        "利多",
        "突破",
        "強勢",
        "熱賣",
        "暢旺",
        "亮眼",
        "締造",
        "奪",
        "拿下",
        "回溫",
        "轉強",
        "看增",
    ),
}
# 利空關鍵詞
_NEGATIVE = {
    2: (
        "大跌",
        "崩",
        "暴跌",
        "重挫",
        "跌停",
        "破底",
        "新低",
        "鉅額虧損",
        "不如預期",
        "低於預期",
        "示警",
    ),
    1: (
        "跌",
        "挫",
        "摔",
        "殺",
        "走低",
        "下跌",
        "下滑",
        "下修",
        "衰退",
        "虧損",
        "賠",
        "看壞",
        "悲觀",
        "減碼",
        "賣超",
        "調降",
        "下調",
        "利空",
        "警訊",
        "疲弱",
        "疲軟",
        "遜色",
        "摜壓",
        "認賠",
        "停損",
        "違約",
        "跳票",
        "減資",
        "示弱",
        "承壓",
        "拉回",
        "回檔",
    ),
}

# score 門檻：|net| 低於此值視為 neutral（避免弱訊號硬分類）
_THRESHOLD = 1


def _count_weighted(text: str, groups: dict[int, tuple[str, ...]]) -> int:
    total = 0
    for weight, words in groups.items():
        for w in words:
            if w in text:
                total += weight
    return total


def classify_sentiment(title: str | None, summary: str | None = None) -> tuple[str, float | None]:
    """回 (label, score)。label ∈ positive/neutral/negative；無標題 → (unknown, None)。

    score ∈ [-1, 1]（正=偏多、負=偏空），可寫入 sentiment_score 供前端/分析參考。
    """
    title = (title or "").strip()
    if not title:
        return ("unknown", None)
    text = title + " " + (summary or "")

    # 反轉語：各給固定方向分，並從文本移除以免內含單字被反向計分
    phrase_score = 0
    for p in _POSITIVE_PHRASES:
        if p in text:
            phrase_score += 2
            text = text.replace(p, "")
    for p in _NEGATIVE_PHRASES:
        if p in text:
            phrase_score -= 2
            text = text.replace(p, "")

    pos = _count_weighted(text, _POSITIVE)
    neg = _count_weighted(text, _NEGATIVE)
    net = pos - neg + phrase_score

    if net >= _THRESHOLD:
        label = "positive"
    elif net <= -_THRESHOLD:
        label = "negative"
    else:
        label = "neutral"

    # 標準化 score：以總訊號強度為分母，夾限 [-1,1]
    denom = pos + neg + abs(phrase_score)
    score = max(-1.0, min(1.0, net / denom)) if denom > 0 else 0.0
    return (label, round(score, 4))


__all__ = ["classify_sentiment"]
