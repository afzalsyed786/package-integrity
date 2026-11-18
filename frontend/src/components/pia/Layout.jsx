import { NavLink, Outlet } from "react-router-dom";
import useSWR from "swr";
import { LayoutDashboard, ShieldAlert, GitCompare, FileWarning, Sparkles, Eye, History, BellRing, FlaskConical, Shield } from "lucide-react";
import { fetcher } from "../../lib/api";

const NAV = [
  { to: "/", label: "Security Overview", icon: LayoutDashboard, id: "overview", end: true },
  { to: "/analyze", label: "Analyze Package", icon: ShieldAlert, id: "analyzer" },
  { to: "/comparison", label: "File Comparison", icon: GitCompare, id: "file-diff" },
  { to: "/anomalies", label: "Anomalies & Evidence", icon: FileWarning, id: "findings" },
  { to: "/ai", label: "AI Explanations", icon: Sparkles, id: "ai-explain" },
  { to: "/watchlist", label: "Watchlist", icon: Eye, id: "watchlist" },
  { to: "/history", label: "Release History", icon: History, id: "history" },
  { to: "/alerts", label: "Alerts", icon: BellRing, id: "alerts" },
  { to: "/lab", label: "Demo Lab", icon: FlaskConical, id: "demo-samples" },
];

const NavItem = ({ item, badge }) => (
  <NavLink
    to={item.to}
    end={item.end}
    data-testid={`nav-tab-${item.id}`}
    className={({ isActive }) =>
      `group flex items-center gap-3 whitespace-nowrap rounded-lg px-3 py-2 text-sm transition-colors duration-150 ${
        isActive ? "bg-[#121D33] text-white shadow-[inset_2px_0_0_#38BDF8]" : "text-slate-400 hover:bg-[#0F1829] hover:text-slate-200"
      }`
    }
  >
    <item.icon className="h-4 w-4 shrink-0" />
    <span className="flex-1">{item.label}</span>
    {badge > 0 && <span data-testid="nav-alert-count" className="rounded-full bg-red-500/20 px-1.5 font-mono text-[10px] text-red-300">{badge}</span>}
  </NavLink>
);

export default function Layout() {
  const { data: stats } = useSWR("/stats", fetcher, { refreshInterval: 15000 });
  const unread = stats?.unread_alerts || 0;
  return (
    <div className="min-h-screen bg-[#070B14] pia-grid-bg text-slate-200">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r border-[#1E2C47] bg-[#070B14]/95 backdrop-blur-xl md:flex">
        <div className="flex items-center gap-3 px-5 py-6">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-sky-400/40 bg-sky-400/10">
            <Shield className="h-5 w-5 text-sky-300" />
          </div>
          <div>
            <div className="font-display text-lg font-extrabold leading-none tracking-tight text-white">PIA</div>
            <div className="mt-1 text-[10px] uppercase tracking-[0.2em] text-slate-500">Package Integrity</div>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-1 px-3">
          {NAV.map((n) => <NavItem key={n.to} item={n} badge={n.id === "alerts" ? unread : 0} />)}
        </nav>
        <div className="m-3 rounded-lg border border-[#1E2C47] p-3 text-[11px] leading-relaxed text-slate-500">
          Untrusted content is never executed, imported or installed. Verdicts come from deterministic rules only.
        </div>
      </aside>
      <div className="sticky top-0 z-30 flex gap-1 overflow-x-auto border-b border-[#1E2C47] bg-[#070B14]/90 p-2 backdrop-blur-xl md:hidden">
        {NAV.map((n) => <NavItem key={n.to} item={n} badge={n.id === "alerts" ? unread : 0} />)}
      </div>
      <main className="md:pl-64">
        <div className="mx-auto max-w-[1500px] px-4 py-8 sm:px-8 lg:px-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export const PageHeader = ({ eyebrow, title, children, actions }) => (
  <div className="fade-up mb-8 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
    <div>
      {eyebrow && <div className="mb-2 font-mono text-[11px] uppercase tracking-[0.22em] text-sky-300/80">{eyebrow}</div>}
      <h1 className="font-display text-3xl font-extrabold tracking-tight text-white sm:text-4xl">{title}</h1>
      {children && <p className="mt-2 max-w-2xl text-sm text-slate-400 sm:text-base">{children}</p>}
    </div>
    {actions}
  </div>
);
