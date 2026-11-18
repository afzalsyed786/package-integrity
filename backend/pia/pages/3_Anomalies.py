import streamlit as st

from dashboard_common import SEV_COLOR, header, pick_analysis, services, setup

setup("Anomalies")
store, *_ = services()
st.title("Anomalies & Evidence")
a = pick_analysis(store)
header(a)
levels = st.multiselect("Severity", list(SEV_COLOR), default=["critical", "high", "medium", "low"])
for f in [x for x in a["findings"] if x["severity"] in levels]:
    c = SEV_COLOR[f["severity"]]
    anomaly = ' <span class="pia-anomaly">ANOMALY DETECTED</span>' if f["severity"] in ("high", "critical") else ""
    st.markdown(f'<div class="pia-card"><b style="color:{c}">{f["severity"].upper()}</b> · score {f["score"]} · '
                f'confidence {f["confidence"]:.0%}{anomaly}<h4>{f["title"]}</h4>{f["reason"]}<br>'
                f'<code>{f.get("file") or ""}{":" + str(f["line"]) if f.get("line") else ""}</code></div>', unsafe_allow_html=True)
    if f.get("evidence"):
        st.code(f["evidence"])
