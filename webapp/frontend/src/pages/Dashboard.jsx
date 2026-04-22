import { useEffect, useState, useCallback } from "react";
import {
  Users, Zap, Star, Crown, TrendingUp, TrendingDown,
  Trophy, RefreshCw, Activity, Headphones,
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";
import { api } from "../lib/api";

const PERIODS = [
  { label: "7D", days: 7 },
  { label: "30D", days: 30 },
  { label: "1Y", days: 365 },
];
const PIE_COLORS = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444", "#6366f1", "#14b8a6"];
const MEDALS = ["🥇", "🥈", "🥉"];

function fmt(n) {
  if (n == null) return "0";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString();
}

function Trend({ value }) {
  if (value == null || value === 0) return null;
  const up = value > 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-semibold px-1.5 py-0.5 rounded-full ${up ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-500"
      }`}>
      {up ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
      {Math.abs(value).toFixed(1)}%
    </span>
  );
}

function KpiCard({ icon: Icon, label, value, sub, trend, accent = "blue" }) {
  const palette = {
    blue: "bg-blue-50 text-blue-600",
    purple: "bg-purple-50 text-purple-600",
    amber: "bg-amber-50 text-amber-600",
    emerald: "bg-emerald-50 text-emerald-600",
    rose: "bg-rose-50 text-rose-600",
    cyan: "bg-cyan-50 text-cyan-600",
  };
  return (
    <div className="bg-white rounded-2xl p-5 border border-gray-100 hover:shadow-md transition-shadow duration-200">
      <div className="flex items-start justify-between mb-3">
        <div className={`p-2.5 rounded-xl ${palette[accent]}`}>
          <Icon size={17} />
        </div>
        <Trend value={trend} />
      </div>
      <p className="text-2xl font-bold text-gray-900 tracking-tight leading-none">{value}</p>
      <p className="text-xs font-medium text-gray-500 mt-1.5">{label}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [chart, setChart] = useState([]);
  const [chartDays, setChartDays] = useState(7);
  const [topUsers, setTopUsers] = useState([]);
  const [revenue, setRevenue] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [updatedAt, setUpdatedAt] = useState(null);

  const loadAll = useCallback((days, isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    return Promise.all([
      api.dashboard(),
      api.chart(days),
      api.topUsers(10),
      api.revenue(),
    ]).then(([s, c, t, r]) => {
      setStats(s); setChart(c); setTopUsers(t); setRevenue(r);
      setUpdatedAt(new Date());
    }).finally(() => { setLoading(false); setRefreshing(false); });
  }, []);

  useEffect(() => { loadAll(7); }, []);

  const switchPeriod = (days) => {
    setChartDays(days);
    api.chart(days).then(setChart);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-7 h-7 border-2 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!stats) return null;

  const activeRatio = stats.total_users
    ? ((stats.active_users / stats.total_users) * 100).toFixed(1)
    : 0;
  const avgConv = stats.total_users
    ? (stats.total_conversions / stats.total_users).toFixed(1)
    : "0";

  return (
    <div className="space-y-5 max-w-screen-xl">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-gray-900">Dashboard</h1>
          {updatedAt && (
            <p className="text-xs text-gray-400 mt-0.5">
              Updated {updatedAt.toLocaleTimeString()}
            </p>
          )}
        </div>
        <button
          onClick={() => loadAll(chartDays, true)}
          disabled={refreshing}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-800 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-colors disabled:opacity-40"
        >
          <RefreshCw size={13} className={refreshing ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 xl:grid-cols-5 gap-3">
        <KpiCard
          icon={Users}
          label="Total Users"
          value={fmt(stats.total_users)}
          sub={`+${stats.new_today} today · +${stats.new_week} this week`}
          trend={stats.growth_rate}
          accent="blue"
        />
        <KpiCard
          icon={Headphones}
          label="Conversions"
          value={fmt(stats.total_conversions)}
          sub={`${avgConv} avg/user · ${activeRatio}% active`}
          accent="purple"
        />
        <KpiCard
          icon={Star}
          label="Stars Earned"
          value={fmt(stats.stars_earned)}
          sub={`≈ $${(stats.stars_earned * 0.013).toFixed(2)} · ${stats.lifetime_sold} lifetime · ${stats.diamonds_sold} 💎`}
          accent="amber"
        />
        <KpiCard
          icon={Crown}
          label="Premium"
          value={fmt(stats.premium_users)}
          sub={`${stats.total_users ? ((stats.premium_users / stats.total_users) * 100).toFixed(1) : 0}% of all users`}
          accent="emerald"
        />
        <KpiCard
          icon={Activity}
          label="Today"
          value={fmt(stats.today_conversions)}
          sub={`${fmt(stats.today_active_converters)} active converters · ${stats.new_today} new signups`}
          accent="rose"
        />
      </div>

      {/* Area Chart */}
      <div className="bg-white rounded-2xl p-5 border border-gray-100">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Growth Overview</h2>
            <p className="text-xs text-gray-400 mt-0.5">New users & conversions</p>
          </div>
          <div className="flex bg-gray-100 rounded-lg p-0.5 gap-px">
            {PERIODS.map((p) => (
              <button
                key={p.days}
                onClick={() => switchPeriod(p.days)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${chartDays === p.days
                    ? "bg-white text-gray-900 shadow-sm"
                    : "text-gray-500 hover:text-gray-700"
                  }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={chart} margin={{ top: 4, right: 0, left: -24, bottom: 0 }}>
            <defs>
              <linearGradient id="gU" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.12} />
                <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gC" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.12} />
                <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gA" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#10b981" stopOpacity={0.12} />
                <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "#9ca3af" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(d) => {
                const dt = new Date(d);
                return chartDays <= 30
                  ? `${dt.getDate()}/${dt.getMonth() + 1}`
                  : dt.toLocaleString("default", { month: "short" });
              }}
            />
            <YAxis tick={{ fontSize: 10, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ borderRadius: 10, border: "1px solid #e5e7eb", fontSize: 12, boxShadow: "0 4px 16px rgba(0,0,0,0.06)" }}
              labelFormatter={(d) => new Date(d).toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric" })}
            />
            <Area type="monotone" dataKey="users" stroke="#3b82f6" strokeWidth={2} fill="url(#gU)" name="New Users" dot={false} activeDot={{ r: 4, strokeWidth: 0 }} />
            <Area type="monotone" dataKey="conversions" stroke="#8b5cf6" strokeWidth={2} fill="url(#gC)" name="Conversions" dot={false} activeDot={{ r: 4, strokeWidth: 0 }} />
            <Area type="monotone" dataKey="active_converters" stroke="#10b981" strokeWidth={2} fill="url(#gA)" name="Active Converters" dot={false} activeDot={{ r: 4, strokeWidth: 0 }} />
          </AreaChart>
        </ResponsiveContainer>
        <div className="flex gap-4 mt-1 pl-1">
          {[{ color: "#3b82f6", label: "New Users" }, { color: "#8b5cf6", label: "Conversions" }, { color: "#10b981", label: "Active Converters" }].map(({ color, label }) => (
            <div key={label} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ background: color }} />
              <span className="text-xs text-gray-400">{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom 3-col */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Top Users */}
        <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-50 flex items-center gap-2">
            <Trophy size={14} className="text-amber-500" />
            <h2 className="text-sm font-semibold text-gray-900">Top Users</h2>
          </div>
          <div className="p-2">
            {topUsers.slice(0, 10).map((u, i) => (
              <div
                key={u.user_id}
                className="flex items-center justify-between px-3 py-2 rounded-xl hover:bg-gray-50 group transition-colors"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="w-5 text-center text-sm shrink-0">
                    {i < 3 ? MEDALS[i] : <span className="text-gray-300 text-xs font-medium">{i + 1}</span>}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm text-gray-700 truncate font-medium">
                      {u.name || u.username || `#${u.user_id}`}
                    </p>
                    {u.username && u.name && (
                      <p className="text-xs text-gray-400 truncate">@{u.username}</p>
                    )}
                  </div>
                </div>
                <span className="text-xs font-semibold text-gray-400 group-hover:text-gray-700 shrink-0 ml-2 tabular-nums">
                  {fmt(u.conversation_count)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Languages */}
        <div className="bg-white rounded-2xl border border-gray-100">
          <div className="px-5 py-4 border-b border-gray-50">
            <h2 className="text-sm font-semibold text-gray-900">Languages</h2>
            <p className="text-xs text-gray-400 mt-0.5">{stats.languages?.length ?? 0} languages detected</p>
          </div>
          <div className="p-5">
            {stats.languages?.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={130}>
                  <PieChart>
                    <Pie
                      data={stats.languages}
                      dataKey="count"
                      nameKey="lang"
                      cx="50%"
                      cy="50%"
                      innerRadius={36}
                      outerRadius={58}
                      paddingAngle={2}
                    >
                      {stats.languages.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} stroke="none" />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(v, n) => [fmt(v), (n || "??").toUpperCase()]}
                      contentStyle={{ borderRadius: 8, fontSize: 12, border: "1px solid #e5e7eb" }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-2 mt-3">
                  {stats.languages.slice(0, 6).map(({ lang, count }, i) => {
                    const pct = stats.total_users ? ((count / stats.total_users) * 100).toFixed(0) : 0;
                    return (
                      <div key={lang} className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                        <span className="text-xs font-semibold text-gray-600 uppercase w-7 shrink-0">{lang || "??"}</span>
                        <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                          <div className="h-1.5 rounded-full" style={{ width: `${pct}%`, background: PIE_COLORS[i % PIE_COLORS.length] }} />
                        </div>
                        <span className="text-xs text-gray-400 w-12 text-right tabular-nums">{pct}% · {fmt(count)}</span>
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <p className="text-sm text-gray-400 py-8 text-center">No data</p>
            )}
          </div>
        </div>

        {/* Revenue */}
        <div className="bg-white rounded-2xl border border-gray-100">
          <div className="px-5 py-4 border-b border-gray-50 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-gray-900">Revenue</h2>
              <p className="text-xs text-gray-400 mt-0.5">Telegram Stars payments</p>
            </div>
            {revenue && (
              <div className="text-right">
                <p className="text-lg font-bold text-yellow-500 leading-none">{fmt(revenue.stars_earned)}</p>
                <p className="text-xs text-gray-400 mt-0.5">⭐ · ≈ ${(revenue.stars_earned * 0.013).toFixed(2)}</p>
              </div>
            )}
          </div>
          <div className="p-5">
            {revenue ? (
              <div className="space-y-1">
                {[
                  { emoji: "💎", label: "Diamonds Sold", value: fmt(revenue.diamonds_sold), sub: "total diamonds", color: "text-cyan-600" },
                  { emoji: "👑", label: "Lifetime Members", value: fmt(revenue.lifetime_sold), sub: "×200 stars each", color: "text-amber-600" },
                  { emoji: "🧾", label: "Total Payments", value: fmt(revenue.total_payments), sub: null, color: "text-gray-800" },
                  { emoji: "👤", label: "Unique Buyers", value: fmt(revenue.unique_buyers), sub: null, color: "text-gray-800" },
                ].map(({ emoji, label, value, sub, color }) => (
                  <div key={label} className="flex items-center justify-between py-2.5 border-b border-gray-50 last:border-0">
                    <div>
                      <p className="text-sm text-gray-600">{emoji} {label}</p>
                      {sub && <p className="text-xs text-gray-400">{sub}</p>}
                    </div>
                    <span className={`text-sm font-bold ${color}`}>{value}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400 py-8 text-center">No payments yet</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
