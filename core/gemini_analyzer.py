"""Gemini Flash-Lite impact analysis across the bank risk framework."""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from .taxonomy import BRANCHES, BY_ID, IDS

DEFAULT_MODEL = "gemini-flash-lite-latest"
MAX_HEADLINES = 40

MATERIALITY = ["none", "low", "medium", "high"]


class GeminiError(RuntimeError):
    pass


def overall_label(score: float) -> str:
    if score >= 40:
        return "Strongly positive"
    if score >= 15:
        return "Positive"
    if score > -15:
        return "Neutral or mixed"
    if score > -40:
        return "Negative"
    return "Strongly negative"


def build_prompt(company: str, items: list[dict]) -> str:
    branch_lines = "\n".join(
        f"- {b.id} | {b.name} ({b.group}) | metrics: {'; '.join(b.metrics)}" for b in BRANCHES
    )
    news_lines = "\n".join(
        f"[{it['n']}] {it['date']} | {it['publisher']} | {it['title']} | tone model: {it['label']} ({it['score']:+.2f})"
        for it in items
    )
    return f"""You are a senior credit and regulatory risk analyst covering Indian banks (RBI Basel III framework).
Assess how the news headlines below affect the risk profile of: {company}.

RISK FRAMEWORK (use these exact ids):
{branch_lines}

HEADLINES (headline text only; you have not read the articles):
{news_lines}

RULES
1. Judge impact on {company}, not tone. A positive-sounding headline about a rival can hurt {company}; a negative-sounding
   sector headline may barely touch it. The tone score is only a hint from a sentiment model.
2. Scores run from -100 (severe damage) to +100 (major strengthening). Be calibrated: one ordinary headline rarely
   justifies more than +/-25 on a branch. Reserve +/-60 or more for events such as RBI business restrictions, large
   fraud or default, rating changes, or major capital raises.
3. Headlines that repeat the same event count once. Say so in the reasoning when you merge them.
4. Headlines that do not name {company} (sector, macro, peers) apply with lower relevance. Explain how it reaches {company}.
5. Headlines can only hint at ratios. Never invent figures. Describe direction, transmission channel and uncertainty.
6. If the headlines show no real signal for a branch, set direction "none", score 0 and a short reason.
7. overall.score reflects the weighted, de-duplicated picture. It is not a plain average.
8. Keep each reasoning to 1 or 2 sentences. Cite headline numbers in headline_ids.

OUTPUT: return only JSON with this exact shape.
{{
  "overall": {{
    "score": <int -100..100>, "label": "<text>", "confidence": <int 0..100>,
    "time_horizon": "<e.g. immediate, 1-2 quarters, 1 year>",
    "summary": "<3 to 4 sentences>",
    "positive_drivers": ["<short>", "..."], "negative_drivers": ["<short>", "..."],
    "watchlist": ["<what to monitor next>", "..."]
  }},
  "branches": [
    {{"id": "<branch id>", "score": <int -100..100>, "direction": "positive|negative|neutral|none",
      "confidence": <int 0..100>, "affected_metrics": ["<metric names from the framework>"],
      "reasoning": "<why>", "headline_ids": [<ints>]}}
  ],
  "headlines": [
    {{"n": <int>, "relevance": <int 0..100>, "materiality": "none|low|medium|high", "net_impact": <int -100..100>,
      "impacts": [{{"branch": "<branch id>", "score": <int -100..100>}}], "why": "<one sentence>"}}
  ]
}}
Include all {len(BRANCHES)} branches, and one entry per headline (at most 3 impacts each)."""


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        a, b = text.find("{"), text.rfind("}")
        if a != -1 and b > a:
            return json.loads(text[a:b + 1])
        raise


def _clip(v: Any, lo: int, hi: int, default: int = 0) -> int:
    try:
        return int(max(lo, min(hi, round(float(v)))))
    except (TypeError, ValueError):
        return default


def _strs(v: Any, cap: int = 6) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if str(x).strip()][:cap]


def normalize(raw: dict, n_items: int) -> dict:
    ov = raw.get("overall") or {}
    score = _clip(ov.get("score"), -100, 100)
    overall = {
        "score": score,
        "label": overall_label(score),
        "confidence": _clip(ov.get("confidence"), 0, 100),
        "time_horizon": str(ov.get("time_horizon") or "Not stated"),
        "summary": str(ov.get("summary") or "No summary returned."),
        "positive_drivers": _strs(ov.get("positive_drivers")),
        "negative_drivers": _strs(ov.get("negative_drivers")),
        "watchlist": _strs(ov.get("watchlist")),
    }

    got = {}
    for b in raw.get("branches") or []:
        if isinstance(b, dict) and b.get("id") in BY_ID:
            got[b["id"]] = b
    branches = []
    for bid in IDS:
        b = got.get(bid, {})
        sc = _clip(b.get("score"), -100, 100)
        direction = str(b.get("direction") or "none").lower()
        if direction not in ("positive", "negative", "neutral", "none"):
            direction = "none"
        if not b:
            direction = "none"
        if direction != "none":
            direction = "positive" if sc >= 5 else "negative" if sc <= -5 else "neutral"
        else:
            sc = 0
        ids = [i for i in (b.get("headline_ids") or []) if isinstance(i, int) and 1 <= i <= n_items]
        branches.append({
            "id": bid, "score": sc, "direction": direction,
            "confidence": _clip(b.get("confidence"), 0, 100),
            "affected_metrics": _strs(b.get("affected_metrics"), 8),
            "reasoning": str(b.get("reasoning") or "No relevant signal in the selected headlines."),
            "headline_ids": ids,
        })

    headlines = []
    for h in raw.get("headlines") or []:
        if not isinstance(h, dict):
            continue
        n = h.get("n")
        if not isinstance(n, int) or not 1 <= n <= n_items:
            continue
        mat = str(h.get("materiality") or "none").lower()
        impacts = []
        for im in (h.get("impacts") or [])[:3]:
            if isinstance(im, dict) and im.get("branch") in BY_ID:
                impacts.append({"branch": im["branch"], "score": _clip(im.get("score"), -100, 100)})
        headlines.append({
            "n": n, "relevance": _clip(h.get("relevance"), 0, 100),
            "materiality": mat if mat in MATERIALITY else "none",
            "net_impact": _clip(h.get("net_impact"), -100, 100),
            "impacts": impacts, "why": str(h.get("why") or ""),
        })
    return {"overall": overall, "branches": branches, "headlines": headlines}


def analyze(api_key: str, model: str, company: str, items: list[dict],
            temperature: float = 0.2) -> dict:
    """items: [{n, date, publisher, title, label, score}] (n is 1-based)."""
    if not api_key:
        raise GeminiError("Add a Gemini API key in the sidebar or in Streamlit secrets.")
    if not items:
        raise GeminiError("Select at least one headline.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise GeminiError("Install the google-genai package (see requirements.txt).") from e

    client = genai.Client(api_key=api_key)
    prompt = build_prompt(company, items)
    cfg = types.GenerateContentConfig(
        temperature=temperature, response_mime_type="application/json", max_output_tokens=8192)

    last_err: Exception | None = None
    for attempt in range(2):
        try:
            resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
            raw = _extract_json(resp.text)
            result = normalize(raw, len(items))
            result["meta"] = {"model": model, "company": company, "n_headlines": len(items),
                              "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            return result
        except json.JSONDecodeError as e:
            last_err = e
            prompt += "\n\nYour previous reply was not valid JSON. Return only the JSON object."
        except Exception as e:
            msg = str(e)
            if any(k in msg.lower() for k in ("api key", "permission", "unauthenticated", "401", "403")):
                raise GeminiError("Gemini rejected the API key. Check that it is valid and has access to this model.") from e
            if "404" in msg or "not found" in msg.lower():
                raise GeminiError(f"Model '{model}' was not found. Change the model name in the sidebar.") from e
            if "429" in msg or "quota" in msg.lower():
                raise GeminiError("Gemini rate limit or quota reached. Wait a minute and try again.") from e
            last_err = e
    raise GeminiError(f"Gemini did not return a usable answer: {last_err}")
