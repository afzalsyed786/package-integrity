import streamlit as st

from dashboard_common import header, services, setup

setup("Analyze")
store, analyzer, _, _ = services()
st.title("Analyze Package")
with st.form("analyze"):
    c1, c2, c3 = st.columns([1, 3, 1])
    eco = c1.selectbox("Ecosystem", ["pypi", "npm"])
    name = c2.text_input("Package name", placeholder="six")
    version = c3.text_input("Version", placeholder="latest")
    go = st.form_submit_button("Run analysis", type="primary")

if go and name.strip():
    bar = st.progress(0, text="Starting")
    try:
        result = analyzer.analyze(eco, name.strip(), version.strip() or None, lambda stage, pct, msg: bar.progress(pct, text=msg))
        st.session_state["selected_analysis"] = result["id"]
        header(result)
        st.success("Saved. Open File Comparison / Anomalies pages for details.")
    except Exception as e:  # show any engine error to the user instead of crashing the page
        st.error(f"Analysis failed: {e}")
