import streamlit as st

from dashboard_common import pick_analysis, services, setup, verdict_pill

setup("AI Explanations")
store, _, explainer, _ = services()
st.title("AI Explanations")
st.caption("Optional open-weight model explanation via Groq or OpenRouter. It never changes the deterministic verdict.")
a = pick_analysis(store)
status = explainer.status()
st.markdown(f"Deterministic verdict: {verdict_pill(a['verdict'])} &nbsp; Provider `{status['provider']}` · model `{status['model']}` · "
            f"configured: **{status['configured']}**", unsafe_allow_html=True)
with st.expander("Exact (redacted) data that would be sent"):
    st.json(explainer.build_payload(a))
if st.button("Generate explanation", type="primary"):
    with st.spinner("Asking model…"):
        a["ai_explanation"] = explainer.explain(a)
        store.set_ai_explanation(a["id"], a["ai_explanation"])
if a.get("ai_explanation"):
    e = a["ai_explanation"]
    st.markdown(f"**{e['status']}** · {e['provider']} · {e['model']}")
    st.markdown(e["text"])
    st.caption(e["disclaimer"])
