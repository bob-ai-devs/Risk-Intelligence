# Bank News Risk Intelligence

Streamlit dashboard that pulls up to 100 headlines per week for a bank, scores each with a RoBERTa
sentiment model, and uses Gemini Flash-Lite to estimate the impact of the headlines you tick on
14 risk areas, each tagged Pillar 1, 2, 3 or Beyond Basel and on the bank overall.
Styled in Bank of Baroda orange and deep blue.

## Features
- Company text input, look-back window (1 to 30 days, default 7), up to 100 headlines
- Publisher multiselect with presets (trusted only, exclude blogs/social), plus tone, risk-area and text filters
- RoBERTa tone score per headline (CardiffNLP or financial DistilRoBERTa), falls back to a keyword scorer if the model cannot load
- Dashboard: KPIs, sentiment mix, daily trend, publisher and publisher-type views, frequent terms, risk-area keyword scan, top positive and negative headlines
- Checkbox selection with quick picks (10 most negative, 10 most positive, 10 newest)
- Gemini impact analysis: overall gauge and summary, drivers and watchlist, radar and bar by risk area, per-area reasoning with linked headlines, headline-by-area heatmap, tone-versus-impact chart
- Downloads: filtered headlines (CSV), analysis (JSON), headline impacts (CSV)
- Demo mode with synthetic headlines for offline use

## Run locally
```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # add GEMINI_API_KEY
streamlit run app.py
```

## Deploy on Streamlit Cloud
Push to GitHub, create the app with `app.py` as the entry point, and add `GEMINI_API_KEY`
(and optionally `NEWSAPI_KEY`) under Settings > Secrets. The first run downloads the RoBERTa model (about 0.5 GB).

## Layout
```
app.py                  UI and flow
core/news.py            Google News / NewsAPI fetch, de-dup, publisher classification, demo data
core/sentiment.py       RoBERTa scoring with fallback
core/prescan.py         keyword triage of risk areas
core/gemini_analyzer.py prompt, call, JSON validation
core/taxonomy.py        the 14 risk areas and their metrics
core/charts.py          Plotly figures
core/theme.py           colours and CSS
tests/test_app.py       headless smoke test (demo data, mocked Gemini)
```

## Notes
- Headline text only goes to Gemini. Output is direction and reasoning, not recomputed ratios.
- RoBERTa measures tone, not business impact. The tone-versus-impact chart shows disagreements.
- Publisher labels are keyword rules; edit the lists in `core/news.py` to suit your own source policy.
- Model name defaults to `gemini-flash-lite-latest` and can be changed in the sidebar.
