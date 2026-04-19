import { useEffect, useState } from "react";
import {
  Users,
  Zap,
  Headphones,
  Crown,
  Gem,
  UserPlus,
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

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [chart, setChart] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.dashboard(), api.chart(30)])
      .then(([s, c]) => {
        setStats(s);
        setChart(c);
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

      {/* Languages */}
      {stats.languages?.length > 0 && (
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">
            Languages
          </h2>
          <div className="flex flex-wrap gap-2">
            {stats.languages.map(({ lang, count }) => (
              <span
                key={lang}
                className="px-3 py-1.5 bg-gray-100 rounded-full text-xs font-medium text-gray-600"
              >
                {lang.toUpperCase()}{" "}
                <span className="text-gray-400">{fmt(count)}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
