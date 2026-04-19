import { useEffect, useState } from "react";
import {
  Users,
  Zap,
  Headphones,
  Crown,
  Gem,
  UserPlus,
  Trophy,
  DollarSign,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import StatCard from "../components/StatCard";
import { api } from "../lib/api";

const medals = ["🥇", "🥈", "🥉"];

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [chart, setChart] = useState([]);
  const [topUsers, setTopUsers] = useState([]);
  const [revenue, setRevenue] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.dashboard(), api.chart(30), api.topUsers(10), api.revenue()])
      .then(([s, c, t, r]) => {
        setStats(s);
        setChart(c);
        setTopUsers(t);
        setRevenue(r);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!stats) return null;

  const fmt = (n) => (n ?? 0).toLocaleString();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard
          icon={Users}
          label="Total Users"
          value={fmt(stats.total_users)}
          sub={`+${stats.new_today} today`}
          color="blue"
        />
        <StatCard
          icon={Zap}
          label="Active Users"
          value={fmt(stats.active_users)}
          sub={`${stats.total_users ? Math.round((stats.active_users / stats.total_users) * 100) : 0}% of total`}
          color="green"
        />
        <StatCard
          icon={Headphones}
          label="Conversions"
          value={fmt(stats.total_conversions)}
          color="purple"
        />
        <StatCard
          icon={Crown}
          label="Premium"
          value={fmt(stats.premium_users)}
          color="amber"
        />
        <StatCard
          icon={Gem}
          label="Diamonds Sold"
          value={fmt(stats.diamonds_sold)}
          color="cyan"
        />
        <StatCard
          icon={UserPlus}
          label="This Week"
          value={`+${fmt(stats.new_week)}`}
          sub="new users"
          color="rose"
        />
      </div>

      {/* Chart */}
      <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">
          Last 30 Days
        </h2>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chart}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickFormatter={(d) => {
                const dt = new Date(d);
                return `${dt.getDate()}/${dt.getMonth() + 1}`;
              }}
            />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip
              labelFormatter={(d) => new Date(d).toLocaleDateString()}
              contentStyle={{
                borderRadius: 8,
                border: "1px solid #e5e7eb",
                fontSize: 13,
              }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="users"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              name="New Users"
            />
            <Line
              type="monotone"
              dataKey="conversions"
              stroke="#8b5cf6"
              strokeWidth={2}
              dot={false}
              name="Conversions"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Bottom row: Top Users + Languages + Revenue */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Top Users */}
        {topUsers.length > 0 && (
          <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
            <div className="flex items-center gap-2 mb-3">
              <Trophy size={16} className="text-amber-500" />
              <h2 className="text-sm font-semibold text-gray-700">Top Users</h2>
            </div>
            <div className="space-y-1.5">
              {topUsers.map((u, i) => (
                <div
                  key={u.user_id}
                  className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-gray-50"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="w-6 text-center text-sm">
                      {i < 3 ? medals[i] : <span className="text-gray-400 text-xs">{i + 1}</span>}
                    </span>
                    <span className="text-sm text-gray-800 truncate">
                      {u.name || u.username || u.user_id}
                    </span>
                  </div>
                  <span className="text-xs font-medium text-gray-500 shrink-0">
                    {fmt(u.conversation_count)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Languages */}
        {stats.languages?.length > 0 && (
          <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">
              Languages
            </h2>
            <div className="space-y-2">
              {stats.languages.map(({ lang, count }) => {
                const pct = stats.total_users
                  ? Math.round((count / stats.total_users) * 100)
                  : 0;
                return (
                  <div key={lang} className="flex items-center gap-3">
                    <span className="text-xs font-bold text-gray-600 w-6 uppercase">
                      {lang}
                    </span>
                    <div className="flex-1 bg-gray-100 rounded-full h-2">
                      <div
                        className="bg-blue-500 h-2 rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-400 w-16 text-right">
                      {fmt(count)} ({pct}%)
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Revenue */}
        {revenue && (
          <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
            <div className="flex items-center gap-2 mb-3">
              <DollarSign size={16} className="text-green-500" />
              <h2 className="text-sm font-semibold text-gray-700">Revenue</h2>
            </div>
            <div className="space-y-3">
              <div className="flex justify-between items-center py-2 border-b border-gray-50">
                <span className="text-sm text-gray-500">Total Payments</span>
                <span className="font-semibold text-gray-900">{fmt(revenue.total_payments)}</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-gray-50">
                <span className="text-sm text-gray-500">Diamonds Sold</span>
                <span className="font-semibold text-cyan-600">{fmt(revenue.diamonds_sold)}</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-gray-50">
                <span className="text-sm text-gray-500">Lifetime Premium</span>
                <span className="font-semibold text-amber-600">{fmt(revenue.lifetime_sold)}</span>
              </div>
              <div className="flex justify-between items-center py-2">
                <span className="text-sm text-gray-500">Unique Buyers</span>
                <span className="font-semibold text-gray-900">{fmt(revenue.unique_buyers)}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
