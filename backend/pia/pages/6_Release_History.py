import pandas as pd
import streamlit as st

from dashboard_common import analyses_frame, services, setup

setup("Release History")
store, *_ = services()
st.title("Release History")
items = store.list_watch()
if items:
    target = st.selectbox("Watched package", [i["id"] for i in items])
    eco, name = target.split(":", 1)
    rel = store.list_releases(eco, name)
    if rel:
        st.dataframe(pd.DataFrame(rel)[[c for c in ("version", "published_at", "status", "verdict", "risk_score", "analysis_id") if c in pd.DataFrame(rel)]],
                     use_container_width=True, hide_index=True)
else:
    st.info("No watched packages yet.")
st.subheader("Analysis history")
st.dataframe(analyses_frame(store.list_analyses(limit=500)), use_container_width=True, hide_index=True)
