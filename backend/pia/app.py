"""PIA Streamlit dashboard — Overview. Run: streamlit run pia/app.py"""
import plotly.express as px
import streamlit as st

from dashboard_common import SEV_COLOR, VERDICT_COLOR, analyses_frame, services, setup

setup("Overview")
store, analyzer, _, _ = services()
s = store.stats()

st.title("Security Overview")
st.caption("Exact published artifacts compared with their tagged source. No package code is ever executed.")
c = st.columns(6)
c[0].metric("Analyses", s["total_analyses"])
c[1].metric("Suspicious", s["verdicts"]["Suspicious"])
c[2].metric("Clean", s["verdicts"]["Clean"])
c[3].metric("Inconclusive", s["verdicts"]["Inconclusive"])
c[4].metric("Watched", s["watch_count"])
c[5].metric("Unread alerts", s["unread_alerts"])

if not s["total_analyses"]:
    st.info("No analyses yet. Open **Demo Lab** or **Analyze** in the sidebar.")
    st.stop()

layout = dict(paper_bgcolor="#0D1424", plot_bgcolor="#0D1424", font_color="#F4F7FC", margin=dict(l=10, r=10, t=40, b=10))
left, right = st.columns([1, 2])
vd = [{"verdict": k, "count": v} for k, v in s["verdicts"].items()]
left.plotly_chart(px.pie(vd, names="verdict", values="count", hole=0.6, color="verdict", color_discrete_map=VERDICT_COLOR,
                         title="Verdict distribution").update_layout(**layout), use_container_width=True)
right.plotly_chart(px.area(s["risk_trend"], x="label", y="risk", title="Risk score by analysis", range_y=[0, 100])
                   .update_traces(line_color="#F97316").update_layout(**layout), use_container_width=True)
l2, r2 = st.columns(2)
sev = [{"severity": k, "count": s["severities"].get(k, 0)} for k in SEV_COLOR]
l2.plotly_chart(px.bar(sev, x="severity", y="count", color="severity", color_discrete_map=SEV_COLOR, title="Findings by severity")
                .update_layout(**layout, showlegend=False), use_container_width=True)
cat = sorted(({"category": k, "count": v} for k, v in s["categories"].items()), key=lambda d: d["count"])
r2.plotly_chart(px.bar(cat, x="count", y="category", orientation="h", title="Anomaly categories").update_traces(marker_color="#F5EFE6")
                .update_layout(**layout), use_container_width=True)
st.subheader("Recent analyses")
st.dataframe(analyses_frame(s["recent"]), use_container_width=True, hide_index=True)
