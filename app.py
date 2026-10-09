"""Bank News Risk Intelligence: weekly headlines -> RoBERTa tone -> Gemini risk-framework impact."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from core import charts as C
from core import theme as T
from core.gemini_analyzer import DEFAULT_MODEL, MAX_HEADLINES, GeminiError, analyze
from core.news import (IST, T_BLOG, T_TRUSTED, TYPE_ICON, demo_df, fetch_google_news, fetch_newsapi,
                       mentions_company)
from core.prescan import scan
from core.sentiment import MODEL_OPTIONS, cached_score
from core.taxonomy import BRANCHES, BY_ID, GROUPS

st.set_page_config(page_title="Bank News Risk Intelligence", page_icon="🏦", layout="wide")
T.inject_css()
ss = st.session_state

for k, v in {"raw_df": None, "selected_ids": set(), "editor_ver": 0, "analysis": None, "history": [],
             "company": "", "terms": [], "is_demo": False, "sent_method": "", "fetched_at": None}.items():
    ss.setdefault(k, v)

hero_slot = st.empty()


def render_hero(company_name: str, sub: str) -> None:
    hero_slot.markdown(
        f'<div class="hero"><div><h1>Bank News Risk Intelligence</h1>'
        f'<p>Weekly headlines, RoBERTa tone, and Gemini impact across the Basel III and RBI risk framework</p></div>'
        f'<div class="co"><b>{T.esc(company_name or "Choose a bank")}</b><span>{T.esc(sub)}</span></div></div>',
        unsafe_allow_html=True)


def hero_sub() -> str:
    sub = f"Fetched {ss.fetched_at:%d %b %Y, %H:%M} IST" if ss.fetched_at else "No data loaded yet"
    return sub + (" (demo data)" if ss.is_demo else "")


render_hero(ss.company, hero_sub())   # drawn first on every run so it never disappears

TONE_ICON = {"Positive": "🟢 Positive", "Neutral": "⚪ Neutral", "Negative": "🔴 Negative"}


def secret(name: str) -> str:
    try:
        v = st.secrets.get(name)
    except Exception:
        v = None
    return v or os.environ.get(name, "")


@st.cache_data(ttl=900, show_spinner=False)
def cached_fetch(provider: str, company: str, days: int, max_items: int, _key: str) -> pd.DataFrame:
    if provider.startswith("NewsAPI"):
        return fetch_newsapi(company, days, max_items, _key)
    return fetch_google_news(company, days, max_items)


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("### Search")
    company = st.text_input("Company or bank", value="Bank of Baroda")
    aliases = st.text_input("Also match these names", value="BoB, Baroda Bank",
                            help="Comma-separated. Used by the 'names the bank' filter.")
    days = st.slider("Look back (days)", 1, 30, 7)
    max_items = st.slider("Max headlines", 20, 100, 100, step=10)
    provider = st.selectbox("News source", ["Google News (no key needed)", "NewsAPI.org (needs key)"])
    newsapi_key = ""
    if provider.startswith("NewsAPI"):
        newsapi_key = secret("NEWSAPI_KEY") or st.text_input("NewsAPI key", type="password")
    demo = st.toggle("Use demo data (offline, synthetic)", value=False,
                     help="Synthetic headlines so you can try every feature without internet or keys.")

    st.markdown("### Models")
    sent_label = st.selectbox("Sentiment model (RoBERTa)", list(MODEL_OPTIONS), index=1)
    gem_secret = secret("GEMINI_API_KEY")
    if gem_secret:
        st.success("Gemini key loaded from secrets")
        gem_key = gem_secret
    else:
        gem_key = st.text_input("Gemini API key", type="password")
    gem_model = st.text_input("Gemini model", value=DEFAULT_MODEL)
    temperature = st.slider("Gemini temperature", 0.0, 1.0, 0.2, 0.05)

    fetch_clicked = st.button("Fetch and score news", type="primary", width="stretch")

if fetch_clicked:
    if not company.strip():
        st.sidebar.error("Enter a company name first.")
    else:
        render_hero(company.strip(), "Fetching and scoring headlines...")
        with st.status("Working on it", expanded=True) as status:
            try:
                st.write("Fetching headlines")
                df = (demo_df(company.strip(), days) if demo else
                      cached_fetch(provider, company.strip(), days, max_items, newsapi_key))
                if df.empty:
                    status.update(label="No headlines found", state="error")
                    st.warning("No headlines matched. Try a wider look-back window or another spelling.")
                else:
                    st.write(f"Scoring {len(df)} headlines with RoBERTa (the first run downloads the model)")
                    sdf, method = cached_score(tuple(df["title"]), MODEL_OPTIONS[sent_label])
                    df = pd.concat([df.reset_index(drop=True), sdf.reset_index(drop=True)], axis=1)
                    df["areas"] = df["title"].map(scan)
                    ss.update(raw_df=df, company=company.strip(), is_demo=demo, sent_method=method,
                              terms=[company.strip()] + [a.strip() for a in aliases.split(",") if a.strip()],
                              fetched_at=datetime.now(IST), selected_ids=set(), analysis=None)
                    ss.editor_ver += 1
                    ss.pub_sel = [p for p, t in df.groupby("publisher")["publisher_type"].first().items()
                                  if t != T_BLOG]
                    status.update(label=f"Loaded {len(df)} headlines", state="complete", expanded=False)
            except Exception as e:
                status.update(label="Could not fetch news", state="error")
                st.error(f"{type(e).__name__}: {e}")
        render_hero(ss.company, hero_sub())

raw: pd.DataFrame | None = ss.raw_df
if raw is None:
    c1, c2, c3 = st.columns(3)
    for col, (h, b) in zip((c1, c2, c3), [
        ("1. Fetch", "Type a bank in the sidebar and press Fetch. The app pulls up to 100 headlines from the last week."),
        ("2. Filter", "Pick the publishers you trust, drop blogs and social posts, and keep only headlines that name the bank."),
        ("3. Assess", f"Tick headlines and let Gemini score the impact on {len(BRANCHES)} risk areas and on the bank overall.")]):
        col.markdown(f'<div class="panel"><h4>{h}</h4>{T.esc(b)}</div>', unsafe_allow_html=True)
    st.info("No Gemini key or internet? Switch on demo data in the sidebar to explore every feature.")
    st.stop()

# ----------------------------------------------------------- source control
stats = (raw.groupby("publisher").agg(n=("id", "size"), type=("publisher_type", "first"),
                                      avg=("sentiment_score", "mean"))
         .sort_values(["n", "avg"], ascending=[False, False]))
options = list(stats.index)
ss.pub_sel = [p for p in ss.get("pub_sel", options) if p in options]


def set_pubs(names):
    ss.pub_sel = list(names)


def fmt_pub(p: str) -> str:
    r = stats.loc[p]
    return f"{TYPE_ICON[r['type']]} {p} ({int(r['n'])})"


with st.container(border=True):
    T.section("Source control")
    st.caption("✅ trusted mainstream  📄 press release  ✍️ blog or social  📰 other. "
               "Blogs and social posts start unticked.")
    b1, b2, b3, b4, _ = st.columns([1.2, 1.4, 1, 1, 3])
    b1.button("Trusted only", on_click=set_pubs, args=(list(stats.index[stats["type"] == T_TRUSTED]),),
              width="stretch")
    b2.button("Exclude blogs and social", on_click=set_pubs, args=(list(stats.index[stats["type"] != T_BLOG]),),
              width="stretch")
    b3.button("Select all", on_click=set_pubs, args=(options,), width="stretch")
    b4.button("Clear", on_click=set_pubs, args=([],), width="stretch")
    st.multiselect("Publishers to include", options, key="pub_sel", format_func=fmt_pub)

    f1, f2, f3, f4 = st.columns([1.6, 1.6, 2, 2])
    only_mention = f1.checkbox("Only headlines that name the bank", value=True)
    tone_filter = f2.multiselect("Tone", ["Positive", "Neutral", "Negative"],
                                 default=["Positive", "Neutral", "Negative"])
    area_filter = f3.multiselect("Risk area (keyword scan)", [b.id for b in BRANCHES],
                                 format_func=lambda i: f"{BY_ID[i].icon} {BY_ID[i].tagged_short}")
    query = f4.text_input("Search headlines", placeholder="e.g. NPA, RBI, fraud")

if len(ss.pub_sel) == 0 and len(tone_filter) == 0:
    st.warning("Select at least one publisher and at least one tone / sentiment")
elif len(ss.pub_sel) == 0:
    st.warning("Select at least one publisher")
elif len(tone_filter) == 0:
    st.warning("Select at least one tone / sentiment")

elif len(ss.pub_sel) > 0 and len(tone_filter) > 0:
    flt = raw[raw["publisher"].isin(ss.pub_sel) & raw["sentiment_label"].isin(tone_filter)].copy()
    if only_mention:
        flt = flt[flt["title"].map(lambda t: mentions_company(t, ss.terms))]
    if area_filter:
        flt = flt[flt["areas"].map(lambda a: any(x in a for x in area_filter))]
    if query.strip():
        flt = flt[flt["title"].str.contains(query.strip(), case=False, regex=False)]
    flt = flt.reset_index(drop=True)
    st.caption(f"Showing {len(flt)} of {len(raw)} fetched headlines from {flt['publisher'].nunique()} publishers.")
    
    if ss.sent_method.startswith("Keyword fallback"):
        st.warning(f"{ss.sent_method}. Install `transformers` and `torch` (see requirements.txt) to use RoBERTa.")
    
    tab_over, tab_head, tab_ai, tab_fw, tab_about = st.tabs(
        ["Overview", "Headlines and selection", "AI impact analysis", "Risk framework", "About"])
    
    # ----------------------------------------------------------------- overview
    with tab_over:
        if flt.empty:
            st.info("No headlines match the current filters. Add publishers or loosen the filters above.")
        else:
            avg = flt["sentiment_score"].mean()
            pos_share = (flt["sentiment_label"] == "Positive").mean() * 100
            neg_share = (flt["sentiment_label"] == "Negative").mean() * 100
            trusted_share = (flt["publisher_type"] == T_TRUSTED).mean() * 100
            cutoff = datetime.now(IST) - timedelta(hours=48)
            recent, older = flt[flt["published"] >= cutoff], flt[flt["published"] < cutoff]
            shift = (f"{recent['sentiment_score'].mean() - older['sentiment_score'].mean():+.2f}"
                     if len(recent) and len(older) else "n/a")
            k = st.columns(6)
            k[0].markdown(T.kpi("Headlines", len(flt), f"of {len(raw)} fetched"), unsafe_allow_html=True)
            k[1].markdown(T.kpi("Average tone", f"{avg:+.2f}", "-1 negative, +1 positive",
                                "g" if avg > 0.05 else "r" if avg < -0.05 else ""), unsafe_allow_html=True)
            k[2].markdown(T.kpi("Positive", f"{pos_share:.0f}%", "of shown headlines", "g"), unsafe_allow_html=True)
            k[3].markdown(T.kpi("Negative", f"{neg_share:.0f}%", "of shown headlines", "r"), unsafe_allow_html=True)
            k[4].markdown(T.kpi("Tone shift, last 48h", shift, "versus earlier headlines", "o"), unsafe_allow_html=True)
            k[5].markdown(T.kpi("Trusted sources", f"{trusted_share:.0f}%", f"{flt['publisher'].nunique()} publishers", "o"),
                          unsafe_allow_html=True)
            st.write("")
    
            r1a, r1b = st.columns([1, 2])
            r1a.plotly_chart(C.sentiment_donut(flt))
            r1b.plotly_chart(C.sentiment_trend(flt))
    
            r2a, r2b = st.columns(2)
            r2a.plotly_chart(C.publisher_bar(flt))
            r2b.plotly_chart(C.top_terms(flt, ss.terms))
    
            r3a, r3b, r3c = st.columns(3)
            r3a.plotly_chart(C.sentiment_hist(flt))
            r3b.plotly_chart(C.type_sentiment(flt))
            counts = {b.id: int(flt["areas"].map(lambda a, i=b.id: i in a).sum()) for b in BRANCHES}
            cdf = pd.DataFrame({"area": [f"{BY_ID[i].icon} {BY_ID[i].tagged_short}" for i in counts], "n": list(counts.values())})
            cdf = cdf.sort_values("n")
            import plotly.graph_objects as go
            fig = go.Figure(go.Bar(x=cdf["n"], y=cdf["area"], orientation="h", marker_color=T.NAVY))
            r3c.plotly_chart(C._base(fig, 300, title="Risk areas in the news (keyword scan)", margin=dict(l=10, r=10, t=40, b=10)))
    
            lc, rc = st.columns(2)
            for col, title, d in ((lc, "Most positive headlines", flt.nlargest(5, "sentiment_score")),
                                  (rc, "Most negative headlines", flt.nsmallest(5, "sentiment_score"))):
                body = "".join(
                    f'<div class="hl"><a href="{T.esc(r.url)}" target="_blank">{T.esc(r.title)}</a><br>'
                    f'<small>{T.esc(r.publisher)} ({r.published.strftime('%d-%b-%Y')}), tone {r.sentiment_score:+.2f}</small></div>' for r in d.itertuples())
                col.markdown(f'<div class="card"><h4>{title}</h4>{body}</div>', unsafe_allow_html=True)
    
    # ----------------------------------------------------------------- headlines
    with tab_head:
        if flt.empty:
            st.info("No headlines match the current filters.")
        else:
            def set_sel(ids):
                ss.selected_ids = set(ids)
                ss.editor_ver += 1
    
            sort_by = st.radio("Sort", ["Newest", "Most negative", "Most positive", "Publisher"], horizontal=True)
            view = {"Newest": flt.sort_values("published", ascending=False),
                    "Most negative": flt.sort_values("sentiment_score"),
                    "Most positive": flt.sort_values("sentiment_score", ascending=False),
                    "Publisher": flt.sort_values(["publisher", "published"], ascending=[True, False])}[sort_by]
            a = st.columns([1.2, 1, 1.3, 1.3, 1.3, 2])
            a[0].button("Select all shown", on_click=set_sel, args=(tuple(view["id"]),), width="stretch")
            a[1].button("Clear", on_click=set_sel, args=((),), width="stretch", key="clr_sel")
            a[2].button("10 most negative", on_click=set_sel, args=(tuple(flt.nsmallest(10, "sentiment_score")["id"]),),
                        width="stretch")
            a[3].button("10 most positive", on_click=set_sel, args=(tuple(flt.nlargest(10, "sentiment_score")["id"]),),
                        width="stretch")
            a[4].button("10 newest", on_click=set_sel, args=(tuple(flt.sort_values("published", ascending=False).head(10)["id"]),),
                        width="stretch")
            info = a[5].empty()
    
            table = pd.DataFrame({
                "Select": view["id"].isin(ss.selected_ids).values,
                "Published": view["published"].dt.strftime("%d %b, %H:%M").values,
                "Publisher": view["publisher"].values,
                "Type": [f"{TYPE_ICON[t]} {t}" for t in view["publisher_type"]],
                "Headline": view["title"].values,
                "Tone": [TONE_ICON[t] for t in view["sentiment_label"]],
                "Score": view["sentiment_score"].values,
                "Areas": [", ".join(BY_ID[i].tagged_short for i in a_) for a_ in view["areas"]],
                "Link": view["url"].values,
            }, index=view.index)
            edited = st.data_editor(
                table, key=f"editor_{ss.editor_ver}", hide_index=True, height=560,
                disabled=[c for c in table.columns if c != "Select"],
                column_config={
                    "Select": st.column_config.CheckboxColumn("Pick", width="small"),
                    "Published": st.column_config.TextColumn(width="small"),
                    "Headline": st.column_config.TextColumn(width="large"),
                    "Score": st.column_config.NumberColumn(format="%+.2f", width="small"),
                    "Link": st.column_config.LinkColumn("Open", display_text="Open", width="small"),
                })
            chosen = set(view.loc[edited.index[edited["Select"]], "id"])
            ss.selected_ids = (ss.selected_ids - set(view["id"])) | chosen
            n_sel = len(ss.selected_ids & set(flt["id"]))
            info.markdown(f"**{n_sel}** selected. Open the AI impact tab to analyse them.")
            st.download_button("Download shown headlines (CSV)",
                               flt.drop(columns=["areas"]).to_csv(index=False).encode("utf-8"),
                               file_name=f"{ss.company.replace(' ', '_')}_headlines.csv", mime="text/csv")
    
    # --------------------------------------------------------------------- AI tab
    with tab_ai:
        sel = flt[flt["id"].isin(ss.selected_ids)].sort_values("published", ascending=False).reset_index(drop=True)
        left, right = st.columns([3, 1])
        left.markdown(f"**{len(sel)}** headlines selected for **{T.esc(ss.company)}**. "
                      f"Gemini reads up to {MAX_HEADLINES} at a time (newest first).")
        run = right.button("Analyse impact with Gemini", type="primary", width="stretch", disabled=len(sel) == 0)
        if len(sel) == 0:
            st.info("Tick headlines in the Headlines tab first. Mixing positive and negative stories gives the fairest picture.")
        elif not gem_key:
            st.warning("Add a Gemini API key in the sidebar (or GEMINI_API_KEY in Streamlit secrets) to run the analysis.")
        if len(sel) > MAX_HEADLINES:
            st.caption(f"Only the {MAX_HEADLINES} newest of your {len(sel)} picks will be sent.")
    
        if run and len(sel):
            use = sel.head(MAX_HEADLINES).copy()
            use["n"] = range(1, len(use) + 1)
            items = [{"n": int(r.n), "date": r.published.strftime("%Y-%m-%d") if pd.notna(r.published) else "n/a",
                      "publisher": r.publisher, "title": r.title, "label": r.sentiment_label,
                      "score": float(r.sentiment_score)} for r in use.itertuples()]
            try:
                with st.spinner("Gemini is assessing the headlines against the risk framework"):
                    res = analyze(gem_key, gem_model.strip() or DEFAULT_MODEL, ss.company, items, temperature)
                ss.analysis = {"result": res, "items": use[["n", "id", "title", "publisher", "url", "published",
                                                             "sentiment_label", "sentiment_score"]].copy()}
                ss.history.insert(0, {"Time": res["meta"]["generated_at"], "Company": ss.company,
                                      "Headlines": len(items), "Overall": res["overall"]["score"],
                                      "Label": res["overall"]["label"]})
            except GeminiError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Unexpected error: {type(e).__name__}: {e}")
    
        if ss.analysis:
            res, idf = ss.analysis["result"], ss.analysis["items"]
            ov = res["overall"]
            T.section("Overall impact on the bank")
            g1, g2 = st.columns([1, 2])
            g1.plotly_chart(C.gauge(ov["score"], ov["label"]))
            g2.markdown(
                f'<div class="panel"><h4>{T.badge(ov["label"], T.score_color(ov["score"], 15))} &nbsp; '
                f'confidence {ov["confidence"]}%, horizon: {T.esc(ov["time_horizon"])}</h4>'
                f'<p style="margin:8px 0 0">{T.esc(ov["summary"])}</p></div>', unsafe_allow_html=True)
            d1, d2, d3 = st.columns(3)
            d1.markdown(f'<div class="card"><h4>Supporting the bank</h4>{T.bullets(ov["positive_drivers"])}</div>',
                        unsafe_allow_html=True)
            d2.markdown(f'<div class="card"><h4>Hurting the bank</h4>{T.bullets(ov["negative_drivers"])}</div>',
                        unsafe_allow_html=True)
            d3.markdown(f'<div class="card"><h4>Watch next</h4>{T.bullets(ov["watchlist"])}</div>',
                        unsafe_allow_html=True)
    
            T.section("Impact by risk area")
            c1, c2 = st.columns(2)
            c1.plotly_chart(C.branch_radar(res["branches"]))
            c2.plotly_chart(C.branch_bars(res["branches"]))
    
            titles = dict(zip(idf["n"], idf["title"]))
            links = dict(zip(idf["n"], idf["url"]))
            by_branch = {b["id"]: b for b in res["branches"]}
            for grp in GROUPS:
                st.markdown(f"**{grp}**")
                for br in [b for b in BRANCHES if b.group == grp]:
                    d = by_branch[br.id]
                    tag = f"{d['score']:+d}" if d["direction"] != "none" else "no signal"
                    with st.expander(f"{br.icon} {br.label}: {tag}", expanded=abs(d["score"]) >= 30):
                        if d["direction"] == "none":
                            st.caption(d["reasoning"])
                            continue
                        st.markdown(T.badge(d["direction"].title(), T.score_color(d["score"])) +
                                    f' &nbsp; confidence {d["confidence"]}%', unsafe_allow_html=True)
                        st.write(d["reasoning"])
                        if d["affected_metrics"]:
                            st.markdown("".join(f'<span class="pill">{T.esc(m)}</span>' for m in d["affected_metrics"]),
                                        unsafe_allow_html=True)
                        if d["headline_ids"]:
                            st.markdown("".join(
                                f'<div class="hl"><a href="{T.esc(links.get(n, "#"))}" target="_blank">'
                                f'#{n} {T.esc(titles.get(n, ""))}</a></div>' for n in d["headline_ids"]),
                                unsafe_allow_html=True)
    
            T.section("Headline by headline")
            hm = C.impact_heatmap(res, titles)
            if hm:
                st.plotly_chart(hm)
            hd = pd.DataFrame(res["headlines"])
            if not hd.empty:
                hd = hd.merge(idf, on="n", how="left")
                hd["areas"] = hd["impacts"].map(lambda im: ", ".join(BY_ID[i["branch"]].tagged_short for i in im))
                st.plotly_chart(C.tone_vs_impact(hd))
                show = hd.assign(abs_i=hd["net_impact"].abs()).sort_values("abs_i", ascending=False)
                st.dataframe(show[["n", "title", "publisher", "relevance", "materiality", "net_impact",
                                   "sentiment_score", "areas", "why"]].rename(columns={
                    "n": "#", "title": "Headline", "publisher": "Publisher", "relevance": "Relevance",
                    "materiality": "Materiality", "net_impact": "Impact", "sentiment_score": "Tone",
                    "areas": "Areas hit", "why": "Why"}), hide_index=True, height=420,
                    column_config={"Impact": st.column_config.NumberColumn(format="%+d"),
                                   "Tone": st.column_config.NumberColumn(format="%+.2f"),
                                   "Relevance": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d")})
                st.caption("A gap between tone and impact is the point: an upbeat headline can still carry risk, "
                           "and a gloomy sector story may barely touch this bank.")
    
            e1, e2 = st.columns(2)
            payload = {"analysis": res, "headlines": idf.assign(published=idf["published"].astype(str)).to_dict("records")}
            e1.download_button("Download analysis (JSON)", json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
                               file_name=f"{ss.company.replace(' ', '_')}_impact.json", mime="application/json",
                               width="stretch")
            if not hd.empty:
                e2.download_button("Download headline impacts (CSV)",
                                   hd.drop(columns=["impacts"]).to_csv(index=False).encode("utf-8"),
                                   file_name=f"{ss.company.replace(' ', '_')}_impact.csv", mime="text/csv",
                                   width="stretch")
            st.caption(f"Model {res['meta']['model']}, generated {res['meta']['generated_at']}. "
                       "Assessment is based on headline text only and is not investment advice.")
    
        if ss.history:
            with st.expander("Analysis history (this session)"):
                st.dataframe(pd.DataFrame(ss.history), hide_index=True)
    
    # ---------------------------------------------------------------- framework
    with tab_fw:
        st.markdown(f"Every Gemini assessment is scored against these {len(BRANCHES)} areas. Each is tagged with its Basel pillar, "
                    "or **Beyond Basel** where it comes from RBI and Indian practice instead. "
                    "**Signal** tells you how much a headline alone can reveal.")
        for grp in GROUPS:
            T.section(grp)
            cols = st.columns(2)
            for i, br in enumerate([b for b in BRANCHES if b.group == grp]):
                pills = "".join(f'<span class="pill">{T.esc(m)}</span>' for m in br.metrics)
                sig = T.badge(f"{br.signal} signal", T.ORANGE if br.signal == "Direct" else T.NAVY)
                cols[i % 2].markdown(
                    f'<div class="card" style="margin-bottom:12px"><h4>{br.icon} {T.esc(br.label)} &nbsp; {sig}</h4>'
                    f'<small style="color:{T.MUTED}">{T.esc(br.signal_note)}</small><br>{pills}</div>',
                    unsafe_allow_html=True)
    
    # -------------------------------------------------------------------- about
    with tab_about:
        st.markdown(f"""
    **How it works**
    
    1. Headlines for the last *N* days come from Google News (or NewsAPI) and are de-duplicated.
    2. Publishers are tagged as trusted, press release, blog or social, or other. You choose which to keep.
    3. A RoBERTa model scores each headline: positive minus negative probability, from -1 to +1.
    4. You tick headlines. `{DEFAULT_MODEL}` rates their impact on {len(BRANCHES)} risk areas and on the bank overall, from -100 to +100.
    
    **Read the results with care**
    
    - RoBERTa measures *tone*, not business impact. The tone-versus-impact chart shows where the two disagree.
    - Gemini sees headline text only. It gives direction and reasoning, not recalculated ratios such as CRAR or GNPA.
    - Google News returns at most about 100 items per query. Publisher labels come from keyword rules, so check unfamiliar names.
    - Thresholds in the source circular date from 2014. Check current RBI Master Directions before relying on any number.
    - This tool supports research. It is not investment or credit advice.
    
    **Secrets (Streamlit Cloud or local)**: add `GEMINI_API_KEY` and, optionally, `NEWSAPI_KEY` in `.streamlit/secrets.toml`.
    """)
        if ss.sent_method:
            st.caption(f"Sentiment engine in use: {ss.sent_method}")
