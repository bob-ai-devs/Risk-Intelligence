"""Plotly figures shared by the dashboard."""
from __future__ import annotations

import re
from collections import Counter

from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import theme as T
from .taxonomy import BRANCHES, BY_ID

FONT = dict(family="IBM Plex Sans, system-ui, sans-serif", color=T.INK, size=13)
DIVERGING = [[0, T.NEG], [0.5, "#F5F6F8"], [1, T.POS]]


def _base(fig: go.Figure, height: int = 340, **kw) -> go.Figure:
    kw.setdefault("margin", dict(l=10, r=10, t=40, b=10))
    fig.update_layout(height=height, font=FONT, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", **kw)
    return fig


def sentiment_donut(df: pd.DataFrame) -> go.Figure:
    order = ["Positive", "Neutral", "Negative"]
    counts = df["sentiment_label"].value_counts().reindex(order).fillna(0)
    fig = go.Figure(go.Pie(labels=order, values=counts.values, hole=0.62, sort=False,
                           marker=dict(colors=[T.SENT_COLORS[o] for o in order]),
                           textinfo="percent", hovertemplate="%{label}: %{value} headlines<extra></extra>"))
    fig.add_annotation(text=f"<b>{int(counts.sum())}</b><br>headlines", showarrow=False, font=dict(size=15))
    return _base(fig, 300, title="Sentiment mix", legend=dict(orientation="h", y=-0.05))


def sentiment_trend(df: pd.DataFrame) -> go.Figure:
    d = df.dropna(subset=["published"]).copy()
    d["day"] = d["published"].dt.strftime("%Y-%m-%d")
    g = d.groupby("day").agg(n=("id", "size"), avg=("sentiment_score", "mean")).reset_index()
    fig = go.Figure()
    fig.add_bar(x=g["day"], y=g["n"], name="Headlines", marker_color="#F9C7A8", yaxis="y2",
                hovertemplate="%{x}: %{y} headlines<extra></extra>")
    fig.add_scatter(x=g["day"], y=g["avg"], name="Avg sentiment", mode="lines+markers",
                    line=dict(color=T.NAVY, width=3), marker=dict(size=8),
                    hovertemplate="%{x}: %{y:+.2f}<extra></extra>")
    fig.add_hline(y=0, line_dash="dot", line_color=T.NEU)
    return _base(fig, 320, title="Daily sentiment and volume",
                 yaxis=dict(title="Avg sentiment", range=[-1, 1], zeroline=False),
                 yaxis2=dict(title="Headlines", overlaying="y", side="right", showgrid=False),
                 legend=dict(orientation="h", y=-0.15), bargap=0.35)


def publisher_bar(df: pd.DataFrame, top: int = 12) -> go.Figure:
    g = (df.groupby("publisher").agg(n=("id", "size"), avg=("sentiment_score", "mean"))
         .sort_values("n", ascending=False).head(top).iloc[::-1])
    fig = go.Figure(go.Bar(
        x=g["n"], y=g.index, orientation="h", marker=dict(color=g["avg"], colorscale=DIVERGING, cmin=-1, cmax=1,
                                                             colorbar=dict(title="Avg tone", thickness=10)),
        text=[f"{v:+.2f}" for v in g["avg"]], textposition="outside",
        hovertemplate="%{y}: %{x} headlines<extra></extra>"))
    return _base(fig, 360, title="Top publishers (bar colour = average tone)", xaxis_title="Headlines")


def sentiment_hist(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Histogram(x=df["sentiment_score"], nbinsx=20, marker_color=T.NAVY))
    fig.add_vline(x=0, line_dash="dot", line_color=T.ORANGE)
    return _base(fig, 300, title="Distribution of sentiment scores", xaxis=dict(range=[-1, 1], title="Score"),
                 yaxis_title="Headlines")


def type_sentiment(df: pd.DataFrame) -> go.Figure:
    g = df.groupby("publisher_type").agg(n=("id", "size"), avg=("sentiment_score", "mean")).reset_index()
    fig = go.Figure(go.Bar(x=g["publisher_type"], y=g["avg"], marker_color=[T.score_color(v * 100, 8) for v in g["avg"]],
                           text=[f"{n} headlines" for n in g["n"]], textposition="outside",
                           hovertemplate="%{x}: %{y:+.2f}<extra></extra>"))
    return _base(fig, 300, title="Average tone by publisher type", yaxis=dict(range=[-1, 1], zeroline=True))


_STOP = set("""a an the of to in on for and or at by with from as is are was were be been it its this that these those
after amid over under into than more less new says say said will may could would can has have had not no up down out
about per vs via off all get gets also their his her our your you we they he she who what why how when""".split())


def top_terms(df: pd.DataFrame, exclude: list[str], n: int = 15) -> go.Figure:
    ex = {w for e in exclude for w in re.findall(r"[a-z]+", e.lower())}
    words = Counter()
    for t in df["title"]:
        for w in set(re.findall(r"[a-z]{3,}", t.lower())):
            if w not in _STOP and w not in ex:
                words[w] += 1
    items = words.most_common(n)[::-1]
    fig = go.Figure(go.Bar(x=[c for _, c in items], y=[w for w, _ in items], orientation="h", marker_color=T.ORANGE))
    return _base(fig, 360, title="Most frequent headline terms", xaxis_title="Headlines")


# ---------------------------------------------------------------- AI impact
def gauge(score: float, label: str) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score, number=dict(font=dict(size=46, color=T.NAVY)),
        title=dict(text=label, font=dict(size=16)),
        gauge=dict(axis=dict(range=[-100, 100], tickvals=[-100, -50, 0, 50, 100]),
                   bar=dict(color=T.NAVY, thickness=0.25),
                   steps=[dict(range=[-100, -40], color="#F2B8B8"), dict(range=[-40, -15], color="#F8D9D2"),
                          dict(range=[-15, 15], color="#E9EDF2"), dict(range=[15, 40], color="#CDEBDD"),
                          dict(range=[40, 100], color="#A9DCC3")],
                   threshold=dict(line=dict(color=T.ORANGE, width=5), thickness=0.8, value=score))))
    return _base(fig, 280, margin=dict(l=20, r=20, t=60, b=10))


def branch_radar(branches: list[dict]) -> go.Figure:
    names = [BY_ID[b["id"]].tagged_short for b in branches]
    vals = [b["score"] for b in branches]
    fig = go.Figure(go.Scatterpolar(r=vals + vals[:1], theta=names + names[:1], fill="toself",
                                    fillcolor="rgba(242,107,33,0.25)", line=dict(color=T.ORANGE, width=3),
                                    hovertemplate="%{theta}: %{r:+d}<extra></extra>"))
    fig.update_layout(polar=dict(radialaxis=dict(range=[-100, 100], tickvals=[-100, -50, 0, 50, 100],
                                                 gridcolor=T.LINE), angularaxis=dict(gridcolor=T.LINE)),
                      showlegend=False)
    return _base(fig, 520, title="Impact footprint across the framework", margin=dict(l=130, r=130, t=60, b=40))


def branch_bars(branches: list[dict]) -> go.Figure:
    b = sorted(branches, key=lambda x: x["score"])
    fig = go.Figure(go.Bar(
        x=[x["score"] for x in b], y=[BY_ID[x["id"]].label for x in b], orientation="h",
        marker_color=[T.score_color(x["score"]) if x["direction"] != "none" else "#D5DAE1" for x in b],
        text=[f"{x['score']:+d}" if x["direction"] != "none" else "no signal" for x in b], textposition="outside",
        hovertemplate="%{y}: %{x:+d}<extra></extra>"))
    fig.add_vline(x=0, line_color=T.INK, line_width=1)
    return _base(fig, 520, title="Impact by risk area (negative to positive)",
                 xaxis=dict(range=[-110, 110], title="Impact score"), margin=dict(l=10, r=50, t=40, b=10))


def impact_heatmap(analysis: dict, titles: dict[int, str]) -> Optional[go.Figure]:
    rows = [h for h in analysis["headlines"] if h["impacts"]]
    if not rows:
        return None
    cols = [b.id for b in BRANCHES]
    z = np.full((len(rows), len(cols)), np.nan)
    for i, h in enumerate(rows):
        for im in h["impacts"]:
            z[i, cols.index(im["branch"])] = im["score"]
    ylabels = [f"#{h['n']} {titles.get(h['n'], '')[:55]}" for h in rows]
    fig = go.Figure(go.Heatmap(z=z, x=[BY_ID[c].tagged_short for c in cols], y=ylabels, colorscale=DIVERGING,
                               zmid=0, zmin=-100, zmax=100, xgap=2, ygap=2, hoverongaps=False,
                               colorbar=dict(title="Impact", thickness=10)))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(tickangle=-40)
    return _base(fig, max(320, 26 * len(rows) + 230), title="Which headline hits which branch",
                 margin=dict(l=10, r=10, t=40, b=150))


def tone_vs_impact(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=df["sentiment_score"], y=df["net_impact"], mode="markers+text", text=df["n"].astype(str),
        textposition="top center",
        marker=dict(size=8 + df["relevance"] / 8, color=df["net_impact"], colorscale=DIVERGING, cmin=-100, cmax=100,
                    line=dict(color=T.NAVY, width=1)),
        customdata=df[["title", "relevance"]].values,
        hovertemplate="%{customdata[0]}<br>Tone %{x:+.2f}, impact %{y:+d}, relevance %{customdata[1]}<extra></extra>"))
    fig.add_hline(y=0, line_dash="dot", line_color=T.NEU)
    fig.add_vline(x=0, line_dash="dot", line_color=T.NEU)
    return _base(fig, 380, title="Tone (RoBERTa) vs business impact (Gemini). Marker size = relevance",
                 xaxis=dict(title="Headline tone", range=[-1.05, 1.05]),
                 yaxis=dict(title="Impact on the bank", range=[-105, 105]))
