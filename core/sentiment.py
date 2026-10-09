"""RoBERTa-based headline sentiment with a clearly-labelled lexicon fallback."""
from __future__ import annotations

import re
from typing import List, Tuple

import pandas as pd
import streamlit as st

MODEL_OPTIONS = {
    "RoBERTa base: CardiffNLP (general, 3-class)": "cardiffnlp/twitter-roberta-base-sentiment-latest",
    "DistilRoBERTa: financial news (3-class)": "mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis",
    "FinBERT: financial news (3-class)": "ProsusAI/finbert",
}

POS_WORDS = {
    "profit", "surge", "rise", "rises", "gain", "gains", "growth", "grows", "strong", "record", "upgrade",
    "upgrades", "upgraded", "improves", "improve", "improved", "beats", "beat", "raises", "boost", "robust",
    "high", "low npa", "falls to", "approves", "dividend", "stable", "wins", "win", "rally", "recovery",
}
NEG_WORDS = {
    "fraud", "penalty", "penalties", "probe", "slide", "slides", "falls", "fall", "loss", "losses", "default",
    "defaults", "downgrade", "downgraded", "resigns", "resign", "outage", "cyber", "restricts", "restriction",
    "ban", "slippages", "stress", "weak", "pressure", "concern", "concerns", "warn", "warns", "crisis",
    "irregularities", "scam", "raid", "fine", "fined", "plunge", "plunges", "drop", "drops", "risk",
}


def _lexicon(texts: List[str]) -> pd.DataFrame:
    rows = []
    for t in texts:
        words = re.findall(r"[a-z]+", t.lower())
        pos = sum(w in POS_WORDS for w in words)
        neg = sum(w in NEG_WORDS for w in words)
        total = pos + neg
        score = 0.0 if total == 0 else (pos - neg) / (total + 1)
        p_pos = max(score, 0.0)
        p_neg = max(-score, 0.0)
        rows.append({"p_pos": p_pos, "p_neu": 1 - p_pos - p_neg, "p_neg": p_neg})
    return pd.DataFrame(rows)


@st.cache_resource(show_spinner=False)
def _get_pipeline(model_id: str):
    from transformers import pipeline  # imported lazily: heavy dependency

    return pipeline("text-classification", model=model_id, top_k=None,
                    truncation=True, max_length=128, device=-1)


def _to_probs(items: list) -> dict:
    p = {"p_pos": 0.0, "p_neu": 0.0, "p_neg": 0.0}
    for d in items:
        lab = str(d["label"]).lower()
        if "neg" in lab or lab == "label_0":
            p["p_neg"] += float(d["score"])
        elif "pos" in lab or lab == "label_2":
            p["p_pos"] += float(d["score"])
        else:
            p["p_neu"] += float(d["score"])
    return p


def _finish(probs: pd.DataFrame) -> pd.DataFrame:
    out = probs.copy()
    out["sentiment_score"] = (out["p_pos"] - out["p_neg"]).round(4)
    labels = out[["p_pos", "p_neu", "p_neg"]].idxmax(axis=1).map(
        {"p_pos": "Positive", "p_neu": "Neutral", "p_neg": "Negative"})
    out["sentiment_label"] = labels
    out["sentiment_conf"] = out[["p_pos", "p_neu", "p_neg"]].max(axis=1).round(4)
    return out[["sentiment_label", "sentiment_score", "sentiment_conf", "p_pos", "p_neu", "p_neg"]]


def score_headlines(texts: Tuple[str, ...], model_id: str, batch_size: int = 32) -> Tuple[pd.DataFrame, str]:
    """Return (DataFrame aligned to `texts`, method description)."""
    texts = list(texts)
    if not texts:
        return _finish(pd.DataFrame(columns=["p_pos", "p_neu", "p_neg"])), "empty"
    try:
        pipe = _get_pipeline(model_id)
        rows = []
        for i in range(0, len(texts), batch_size):
            for out in pipe(texts[i:i + batch_size]):
                rows.append(_to_probs(out))
        return _finish(pd.DataFrame(rows)), f"RoBERTa model: {model_id}"
    except Exception as e:  # model missing, no internet, torch not installed...
        return _finish(_lexicon(texts)), f"Keyword fallback (RoBERTa unavailable: {type(e).__name__}: {str(e)[:120]})"


@st.cache_data(show_spinner=False, ttl=3600)
def cached_score(texts: Tuple[str, ...], model_id: str) -> Tuple[pd.DataFrame, str]:
    return score_headlines(texts, model_id)
