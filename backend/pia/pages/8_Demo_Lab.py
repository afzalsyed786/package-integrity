import json

import streamlit as st

from dashboard_common import header, services, setup

setup("Demo Lab")
store, analyzer, _, _ = services()
st.title("Demo Lab")
st.warning("Synthetic samples are fabricated, inert demonstrations — NOT real malware. Real releases are downloaded live.")

st.subheader("Synthetic tampered samples")
cols = st.columns(3)
run = None
for col, s in zip(cols, analyzer.adapters["synthetic"].samples()):
    with col:
        st.markdown(f'<div class="pia-card"><span class="pia-anomaly">{s["label"]}</span><h4>{s["title"]}</h4>'
                    f'<code>{s["package"]}@{s["version"]}</code><p>{s["description"]}</p></div>', unsafe_allow_html=True)
        if st.button("Analyze", key=s["package"]):
            run = ("synthetic", s["package"], None)

st.subheader("Real releases")
real = json.loads((analyzer.s.samples_dir / "real_releases.json").read_text())
cols = st.columns(len(real))
for col, r in zip(cols, real):
    with col:
        st.markdown(f'<div class="pia-card"><b>{r["ecosystem"]}:{r["name"]}@{r["version"]}</b><p>{r["note"]}</p></div>', unsafe_allow_html=True)
        if st.button("Analyze", key=f"real-{r['name']}"):
            run = (r["ecosystem"], r["name"], r["version"])

if run:
    bar = st.progress(0)
    result = analyzer.analyze(*run, progress=lambda stage, pct, msg: bar.progress(pct, text=msg))
    st.session_state["selected_analysis"] = result["id"]
    header(result)
