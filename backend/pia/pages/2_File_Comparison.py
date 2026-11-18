import pandas as pd
import streamlit as st

from dashboard_common import STATUS_COLOR, header, pick_analysis, services, setup

setup("File Comparison")
store, *_ = services()
st.title("File Comparison")
a = pick_analysis(store)
header(a)

files = a["files"] + [{"id": None, "path": p, "status": "repo_only", "kind": "", "risk_score": 0, "has_detail": False} for p in a.get("repo_only", [])]
status = st.multiselect("Status", list(STATUS_COLOR), default=["package_only", "modified", "expected"])
shown = [f for f in files if f["status"] in status]
st.dataframe(pd.DataFrame([{k: f.get(k) for k in ("path", "status", "kind", "risk_score", "expected_reason")} for f in shown]),
             use_container_width=True, hide_index=True)

detail_files = [f for f in shown if f.get("has_detail")]
if detail_files:
    f = next(x for x in detail_files if x["path"] == st.selectbox("Side-by-side view", [x["path"] for x in detail_files]))
    if f.get("expected_reason"):
        st.info(f"Expected difference: {f['expected_reason']}")
    d = store.get_file_detail(a["id"], f["id"])
    if d["mode"] == "diff":
        df = pd.DataFrame(d["rows"], columns=["change", "pkg line", "published package", "repo line", "repository source"])
        st.dataframe(df.style.apply(lambda r: ["background-color: #3b1d10" if r["change"] in ("changed", "pkg_only") else ""] * len(r), axis=1),
                     use_container_width=True, hide_index=True, height=520)
    else:
        st.code("\n".join(d["lines"]), language="python" if f["path"].endswith(".py") else "javascript", line_numbers=True)
