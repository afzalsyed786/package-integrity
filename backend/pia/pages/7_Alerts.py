import streamlit as st

from dashboard_common import services, setup

setup("Alerts")
store, *_ = services()
st.title("Alerts")
if st.button("Mark all read"):
    store.mark_all_alerts_read()
COL = {"critical": "#EF4444", "warning": "#F97316", "info": "#38BDF8"}
alerts = store.list_alerts(limit=200)
if not alerts:
    st.info("No alerts yet. Alerts are raised by watch mode.")
for al in alerts:
    new = "" if al.get("read") else ' <span class="pia-anomaly">NEW</span>'
    st.markdown(f'<div class="pia-card" style="border-left:3px solid {COL.get(al["severity"], "#38BDF8")}"><b>{al["title"]}</b>{new}<br>'
                f'{al.get("message", "")}<br><small>{al["created_at"][:19]}</small></div>', unsafe_allow_html=True)
