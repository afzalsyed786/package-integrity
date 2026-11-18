"""Shared helpers for the Streamlit dashboard (same engine as the CLI and API)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from pia.config import get_settings  # noqa: E402
from pia.database.sqlite_store import SQLiteStore  # noqa: E402
from pia.engine.analyzer import Analyzer  # noqa: E402
from pia.services.explanation import ExplanationService  # noqa: E402
from pia.services.watch import WatchService  # noqa: E402

VERDICT_COLOR = {"Clean": "#10B981", "Suspicious": "#EF4444", "Inconclusive": "#EAB308"}
SEV_COLOR = {"critical": "#EF4444", "high": "#F97316", "medium": "#EAB308", "low": "#38BDF8", "info": "#8EA0C0"}
STATUS_COLOR = {"identical": "#10B981", "modified": "#F97316", "package_only": "#EF4444", "expected": "#38BDF8", "repo_only": "#8EA0C0"}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=JetBrains+Mono&display=swap');
html, body, [class*="css"], .stApp { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background: #070B14; color: #F4F7FC; }
section[data-testid="stSidebar"] { background: #0A101D; border-right: 1px solid #1E2C47; }
div[data-testid="stMetric"] { background: #0D1424; border: 1px solid #1E2C47; border-radius: 12px; padding: 16px; }
code, pre { font-family: 'JetBrains Mono', monospace !important; }
.pia-pill { display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px; font-weight:600; border:1px solid; }
.pia-anomaly { background: rgba(245,239,230,.1); border:1px solid rgba(245,239,230,.5); color:#FDFBF7; padding:1px 8px; border-radius:999px; font-size:10px; letter-spacing:.12em; }
.pia-card { background:#0D1424; border:1px solid #1E2C47; border-radius:12px; padding:18px; margin-bottom:12px; }
</style>
"""


def setup(title: str):
    st.set_page_config(page_title=f"PIA · {title}", page_icon="🛡", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.sidebar.markdown("### PIA\nPackage Integrity Analyzer")
    st.sidebar.caption("Untrusted content is never executed. Verdicts are deterministic.")


@st.cache_resource
def services():
    settings = get_settings()
    store = SQLiteStore(settings.sqlite_path)
    analyzer = Analyzer(settings, store=store)
    return store, analyzer, ExplanationService(settings), WatchService(store, analyzer)


def verdict_pill(v: str) -> str:
    c = VERDICT_COLOR.get(v, "#8EA0C0")
    return f'<span class="pia-pill" style="color:{c};border-color:{c};background:{c}22">{v}</span>'


def analyses_frame(rows) -> pd.DataFrame:
    return pd.DataFrame([{"id": r["id"], "package": f"{r['ecosystem']}:{r['package']}@{r['version']}", "verdict": r["verdict"],
                          "risk": r["risk_score"], "synthetic": r.get("synthetic"), "tag": (r.get("source") or {}).get("status"),
                          "analyzed": r["created_at"][:19]} for r in rows])


def pick_analysis(store, key="analysis"):
    rows = store.list_analyses(limit=200)
    if not rows:
        st.info("No analyses yet — run one on the Analyze page or in the Demo Lab.")
        st.stop()
    labels = {f"{r['verdict']:<12} {r['ecosystem']}:{r['package']}@{r['version']}{' (synthetic)' if r.get('synthetic') else ''} · {r['id']}": r["id"] for r in rows}
    preselect = st.session_state.get("selected_analysis")
    idx = next((i for i, v in enumerate(labels.values()) if v == preselect), 0)
    choice = st.selectbox("Analysis", list(labels), index=idx, key=key)
    st.session_state["selected_analysis"] = labels[choice]
    return store.get_analysis(labels[choice])


def header(a):
    st.markdown(f"## {a['ecosystem']}:{a['package']}@{a['version']} &nbsp; {verdict_pill(a['verdict'])}"
                + (' &nbsp;<span class="pia-anomaly">SYNTHETIC · NOT REAL MALWARE</span>' if a.get("synthetic") else ""), unsafe_allow_html=True)
    cols = st.columns(5)
    cols[0].metric("Risk score", a["risk_score"])
    cols[1].metric("Findings", len(a["findings"]))
    cols[2].metric("Tag status", (a.get("source") or {}).get("status", "—"))
    cols[3].metric("Coverage", f"{a.get('coverage', 0):.0%}")
    cols[4].metric("Files", len(a["files"]))
    for r in a["verdict_reasons"]:
        st.markdown(f"- {r}")
