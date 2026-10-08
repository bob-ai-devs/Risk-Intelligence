import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from streamlit.testing.v1 import AppTest
import core.gemini_analyzer as ga
from core.taxonomy import IDS

def fake_analyze(key, model, company, items, temperature=0.2):
    raw = {"overall": {"score": -22, "confidence": 66, "summary": "Mixed picture.", "positive_drivers": ["Strong profit"],
                       "negative_drivers": ["RBI penalty"], "watchlist": ["Next results"], "time_horizon": "1-2 quarters"},
           "branches": [{"id": i, "score": (-30 if k % 2 else 20), "direction": "negative" if k % 2 else "positive",
                         "confidence": 60, "affected_metrics": ["GNPA"], "reasoning": "Because.", "headline_ids": [1]}
                        for k, i in enumerate(IDS[:8])],
           "headlines": [{"n": it["n"], "relevance": 80, "materiality": "medium", "net_impact": -10 * (it["n"] % 4),
                          "impacts": [{"branch": IDS[it["n"] % 8], "score": -20}], "why": "Test."} for it in items]}
    res = ga.normalize(raw, len(items))
    res["meta"] = {"model": model, "company": company, "n_headlines": len(items), "generated_at": "2026-10-08 12:00:00"}
    return res

import importlib
ga.analyze = fake_analyze

at = AppTest.from_file("../app.py", default_timeout=90)
at.run()
assert not at.exception, at.exception
at.sidebar.toggle[0].set_value(True)
[b for b in at.sidebar.button if "Fetch" in b.label][0].click()
at.run()
assert not at.exception, at.exception
df = at.session_state.raw_df
print("rows", len(df), "pubs", df.publisher.nunique(), "method:", at.session_state.sent_method[:60])
print("pub_sel", len(at.session_state.pub_sel))
print("tabs", [t.label for t in at.tabs])
# pick 12 ids
ids = list(df.id[:12])
at.session_state.selected_ids = set(ids)
at.session_state.editor_ver += 1
at.sidebar.text_input[-1].set_value("fake-key") if False else None
at.run()
assert not at.exception, at.exception
# set gemini key
for ti in at.sidebar.text_input:
    if ti.label == "Gemini API key": ti.set_value("fake")
at.run()
btn = [b for b in at.button if "Analyse" in b.label][0]
btn.click(); at.run()
assert not at.exception, at.exception
print("analysis stored:", bool(at.session_state.analysis), at.session_state.analysis["result"]["overall"]["label"])
print("errors:", [e.value for e in at.error])
print("markdown count", len(at.markdown), "dataframes", len(at.dataframe))

# hero banner must be the first main element on every run, including after fetch
assert "hero" in at.main.markdown[0].value, "hero missing"
print("hero first:", True)
labels = [e.label for e in at.expander]
print([l for l in labels if "Pillar" in l or "Beyond" in l][:14])
