import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";
import { TrendingUp, TrendingDown, Users, Headphones } from "lucide-react";
import { api } from "../lib/api";

function fmt(n) {
  if (n == null) return "0";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString();
}

function pctChange(current, prev) {
  if (!prev) return null;
  return ((current - prev) / prev * 100).toFixed(1);
}

function MonthCard({ icon: Icon, label, current, last, color }) {
  const change = pctChange(current, last);
  const up = change >= 0;
  return (
    <div className="bg-white rounded-2xl p-5 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <div className={`p-2.5 rounded-xl ${color}`}>
          <Icon size={16} />
        </div>
        {change !== null && (
          <span className={`inline-flex items-center gap-0.5 text-xs font-semibold px-1.5 py-0.5 rounded-full ${
            up ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-500"
          }`}>
            {up ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
            {Math.abs(change)}%
          </span>
        )}
      </div>
      <p className="text-2xl font-bold text-gray-900 tracking-tight">{fmt(current)}</p>
      <p className="text-xs font-medium text-gray-500 mt-1.5">{label} this month</p>
      <p className="text-xs text-gray-400 mt-0.5">{fmt(last)} last month</p>
    </div>
  );
}

export default function Analytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.analytics().then(setData).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-7 h-7 border-2 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!data) return null;

  const maxFunnel = data.funnel[0]?.value || 1;

  return (
    <div className="space-y-5 max-w-screen-xl">
      <div>
        <h1 className="text-lg font-bold text-gray-900">Analytics</h1>
        <p className="text-xs text-gray-400 mt-0.5">Detailed insights and metrics</p>
      </div>

      {/* Month comparison */}
      <div className="grid grid-cols-2 gap-3">
        <MonthCard
          icon={Users}
          label="New users"
          current={data.month.this.users}
          last={data.month.last.users}
          color="bg-blue-50 text-blue-600"
        />
        <MonthCard
          icon={Headphones}
          label="Conversions"
          current={data.month.this.conversions}
          last={data.month.last.conversions}
          color="bg-purple-50 text-purple-600"
        />
      </div>

      {/* Funnel */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5">
        <h2 className="text-sm font-semibold text-gray-900 mb-1">User Funnel</h2>
        <p className="text-xs text-gray-400 mb-5">From registered to paying customers</p>
        <div className="space-y-3">
          {data.funnel.map((item, i) => (
            <div key={item.label}>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-medium text-gray-700">{item.label}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400">{item.pct}%</span>
                  <span className="text-sm font-bold text-gray-900 tabular-nums w-16 text-right">{fmt(item.value)}</span>
                </div>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2.5">
                <div
                  className="h-2.5 rounded-full transition-all duration-500"
                  style={{
                    width: `${(item.value / maxFunnel) * 100}%`,
                    background: item.color,
                  }}
                />
              </div>
              {i < data.funnel.length - 1 && (
                <p className="text-xs text-gray-300 mt-1 pl-1">
                  ↓ {data.funnel[i + 1] ? `${data.funnel[i + 1].pct}% conversion` : ""}
                </p>
              )}
            </div>
          ))}
        </div>

        {/* Premium ratio badge */}
        <div className="mt-5 pt-4 border-t border-gray-50 flex items-center gap-2">
          <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
            <div className="h-2 bg-amber-400 rounded-full" style={{ width: `${data.premium_ratio}%` }} />
          </div>
          <span className="text-xs font-semibold text-amber-600 shrink-0">
            {data.premium_ratio}% premium conversions
          </span>
        </div>
      </div>

      {/* 30-day dual bar chart */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5">
        <h2 className="text-sm font-semibold text-gray-900 mb-1">Last 30 Days</h2>
        <p className="text-xs text-gray-400 mb-5">Daily new users and conversions</p>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data.daily} margin={{ top: 0, right: 0, left: -24, bottom: 0 }} barGap={2}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "#9ca3af" }}
              axisLine={false}
              tickLine={false}
              interval={4}
              tickFormatter={(d) => {
                const dt = new Date(d);
                return `${dt.getDate()}/${dt.getMonth() + 1}`;
              }}
            />
            <YAxis tick={{ fontSize: 10, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ borderRadius: 10, border: "1px solid #e5e7eb", fontSize: 12, boxShadow: "0 4px 16px rgba(0,0,0,0.06)" }}
              labelFormatter={(d) => new Date(d).toLocaleDateString("en", { month: "short", day: "numeric" })}
            />
            <Bar dataKey="users" fill="#3b82f6" name="New Users" radius={[3, 3, 0, 0]} maxBarSize={14} />
            <Bar dataKey="conversions" fill="#8b5cf6" name="Conversions" radius={[3, 3, 0, 0]} maxBarSize={14} />
          </BarChart>
        </ResponsiveContainer>
        <div className="flex gap-4 mt-2 pl-1">
          {[{ color: "#3b82f6", label: "New Users" }, { color: "#8b5cf6", label: "Conversions" }].map(({ color, label }) => (
            <div key={label} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ background: color }} />
              <span className="text-xs text-gray-400">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
