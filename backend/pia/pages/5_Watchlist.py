import pandas as pd
import streamlit as st

from dashboard_common import services, setup

setup("Watchlist")
store, _, _, watch = services()
st.title("Watchlist")
st.caption("Registry polling with caching, retries, rate limiting and release de-duplication. New versions are analysed automatically.")
with st.form("watch"):
    c1, c2, c3 = st.columns([1, 3, 1])
    eco = c1.selectbox("Ecosystem", ["npm", "pypi"])
    name = c2.text_input("Package")
    interval = c3.selectbox("Interval (min)", [15, 60, 360, 1440], index=1)
    if st.form_submit_button("Watch") and name.strip():
        try:
            watch.add(eco, name.strip(), interval)
            st.success(f"Watching {name}")
        except Exception as e:  # registry/validation errors shown inline
            st.error(str(e))

if st.button("Run due checks now"):
    with st.spinner("Polling registries…"):
        st.write(watch.run_due())
items = store.list_watch()
if items:
    st.dataframe(pd.DataFrame(items)[["id", "interval_minutes", "latest_version", "known_versions", "last_checked", "next_check", "last_error"]],
                 use_container_width=True, hide_index=True)
    target = st.selectbox("Item", [i["id"] for i in items])
    c1, c2, c3 = st.columns(3)
    if c1.button("Check now"):
        with st.spinner("Checking…"):
            st.json(watch.check(target))
    if c2.button("Demo: replay latest release"):
        v = watch.rewind(target)
        with st.spinner(f"Rediscovering {v}…"):
            st.json(watch.check(target))
    if c3.button("Remove"):
        store.delete_watch(target)
        st.rerun()
