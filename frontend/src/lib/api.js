import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const api = axios.create({ baseURL: API });
export const fetcher = (url) => api.get(url).then((r) => r.data);

export const errMsg = (e) => e?.response?.data?.detail || e?.message || "Request failed";

export const VERDICT_STYLE = {
  Clean: { color: "#10B981", bg: "rgba(16,185,129,0.12)", border: "rgba(16,185,129,0.4)" },
  Suspicious: { color: "#EF4444", bg: "rgba(239,68,68,0.12)", border: "rgba(239,68,68,0.45)" },
  Inconclusive: { color: "#EAB308", bg: "rgba(234,179,8,0.12)", border: "rgba(234,179,8,0.4)" },
};

export const SEVERITY_STYLE = {
  critical: { color: "#EF4444", bg: "rgba(239,68,68,0.14)" },
  high: { color: "#F97316", bg: "rgba(249,115,22,0.14)" },
  medium: { color: "#EAB308", bg: "rgba(234,179,8,0.12)" },
  low: { color: "#38BDF8", bg: "rgba(56,189,248,0.12)" },
  info: { color: "#8EA0C0", bg: "rgba(142,160,192,0.12)" },
};

export const STATUS_STYLE = {
  identical: { label: "Identical", color: "#10B981" },
  modified: { label: "Modified", color: "#F97316" },
  package_only: { label: "Package-only", color: "#EF4444" },
  expected: { label: "Expected", color: "#38BDF8" },
  repo_only: { label: "Repo-only", color: "#8EA0C0" },
};

export const fmtDate = (iso) => (iso ? new Date(iso).toLocaleString() : "—");
export const fmtBytes = (n) => (n == null ? "—" : n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`);
