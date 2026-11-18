import useSWR from "swr";
import { Link } from "react-router-dom";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, AreaChart, Area, CartesianGrid } from "recharts";
import { Activity, ShieldAlert, ShieldCheck, ShieldQuestion, Eye, BellRing } from "lucide-react";
import { fetcher, VERDICT_STYLE, SEVERITY_STYLE } from "../lib/api";
import { PageHeader } from "../components/pia/Layout";
import AnalysesTable from "../components/pia/AnalysesTable";
import AnalyzeForm from "../components/pia/AnalyzeForm";
import { Empty } from "../components/pia/Badges";

const tooltipStyle = { background: "#121D33", border: "1px solid #2E436B", borderRadius: 8, fontSize: 12, color: "#F4F7FC" };

const Stat = ({ icon: Icon, label, value, color = "#F4F7FC", testId, delay }) => (
  <div data-testid={testId} className="pia-card pia-card-hover fade-up p-6" style={{ animationDelay: `${delay}ms` }}>
    <div className="flex items-center justify-between">
      <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{label}</span>
      <Icon className="h-4 w-4" style={{ color }} />
    </div>
    <div className="mt-4 font-display text-4xl font-extrabold" style={{ color }}>{value}</div>
  </div>
);

const ChartCard = ({ title, children, className = "" }) => (
  <div className={`pia-card p-6 ${className}`}>
    <div className="mb-4 font-display text-lg font-bold text-white">{title}</div>
    <div className="h-60">{children}</div>
  </div>
);

export default function Overview() {
  const { data: s } = useSWR("/stats", fetcher, { refreshInterval: 10000 });
  if (!s) return <div className="text-slate-400">Loading…</div>;
  const verdictData = Object.entries(s.verdicts).map(([k, v]) => ({ name: k, value: v }));
  const sevData = ["critical", "high", "medium", "low", "info"].map((k) => ({ name: k, value: s.severities[k] || 0 }));
  const catData = Object.entries(s.categories).map(([k, v]) => ({ name: k, value: v })).sort((a, b) => b.value - a.value);

  return (
    <div>
      <PageHeader eyebrow="Supply-chain integrity · PyPI · npm" title="Security Overview">
        Every verdict below comes from comparing the exact published artifact with its tagged source — no package code is ever executed.
      </PageHeader>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        <Stat icon={Activity} label="Analyses" value={s.total_analyses} testId="stat-total-analyses" delay={0} />
        <Stat icon={ShieldAlert} label="Suspicious" value={s.verdicts.Suspicious} color={VERDICT_STYLE.Suspicious.color} testId="stat-suspicious" delay={40} />
        <Stat icon={ShieldCheck} label="Clean" value={s.verdicts.Clean} color={VERDICT_STYLE.Clean.color} testId="stat-clean" delay={80} />
        <Stat icon={ShieldQuestion} label="Inconclusive" value={s.verdicts.Inconclusive} color={VERDICT_STYLE.Inconclusive.color} testId="stat-inconclusive" delay={120} />
        <Stat icon={Eye} label="Watched" value={s.watch_count} color="#38BDF8" testId="stat-watch-count" delay={160} />
        <Stat icon={BellRing} label="Unread alerts" value={s.unread_alerts} color="#F5EFE6" testId="stat-unread-alerts" delay={200} />
      </div>

      <div className="mt-6"><AnalyzeForm compact /></div>

      {s.total_analyses === 0 ? (
        <div className="mt-6"><Empty title="No analyses yet">Run one above or open the <Link to="/lab" className="text-sky-300">Demo Lab</Link>.</Empty></div>
      ) : (
        <>
          <div className="mt-6 grid gap-6 lg:grid-cols-12">
            <ChartCard title="Verdict distribution" className="lg:col-span-4">
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={verdictData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={92} paddingAngle={3} stroke="none">
                    {verdictData.map((d) => <Cell key={d.name} fill={VERDICT_STYLE[d.name].color} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
            </ChartCard>
            <ChartCard title="Risk score by analysis" className="lg:col-span-8">
              <ResponsiveContainer>
                <AreaChart data={s.risk_trend} margin={{ left: -20, right: 10 }}>
                  <defs>
                    <linearGradient id="risk" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#F97316" stopOpacity={0.45} />
                      <stop offset="100%" stopColor="#F97316" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#1E2C47" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" tick={{ fill: "#576B8E", fontSize: 10 }} interval={0} angle={-12} height={40} />
                  <YAxis domain={[0, 100]} tick={{ fill: "#576B8E", fontSize: 11 }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Area type="monotone" dataKey="risk" stroke="#F97316" strokeWidth={2} fill="url(#risk)" />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>
            <ChartCard title="Findings by severity" className="lg:col-span-5">
              <ResponsiveContainer>
                <BarChart data={sevData} margin={{ left: -20 }}>
                  <XAxis dataKey="name" tick={{ fill: "#8EA0C0", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#576B8E", fontSize: 11 }} allowDecimals={false} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(56,189,248,0.05)" }} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>{sevData.map((d) => <Cell key={d.name} fill={SEVERITY_STYLE[d.name].color} />)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
            <ChartCard title="Anomaly categories" className="lg:col-span-7">
              <ResponsiveContainer>
                <BarChart data={catData} layout="vertical" margin={{ left: 20 }}>
                  <XAxis type="number" tick={{ fill: "#576B8E", fontSize: 11 }} allowDecimals={false} />
                  <YAxis type="category" dataKey="name" tick={{ fill: "#8EA0C0", fontSize: 11 }} width={90} interval={0} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(56,189,248,0.05)" }} />
                  <Bar dataKey="value" fill="#F5EFE6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>
          <div className="mb-4 mt-10 flex items-center justify-between">
            <h2 className="font-display text-2xl font-bold text-white">Recent analyses</h2>
            <Link to="/history" data-testid="overview-view-all-link" className="text-sm text-sky-300 hover:text-sky-200">View all →</Link>
          </div>
          <AnalysesTable rows={s.recent} testId="recent-analyses-table" />
        </>
      )}
    </div>
  );
}
