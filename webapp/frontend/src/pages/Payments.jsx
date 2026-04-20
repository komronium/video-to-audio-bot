import { useEffect, useState } from "react";
import { CreditCard, Star, Gem, Crown, ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "../lib/api";

const TABS = [
  { key: "all", label: "All" },
  { key: "diamond", label: "💎 Diamond" },
  { key: "lifetime", label: "👑 Lifetime" },
];

function fmt(n) {
  return (n ?? 0).toLocaleString();
}

export default function Payments() {
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("all");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = (t, p) => {
    setLoading(true);
    api.payments(p, t)
      .then(setData)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(tab, page); }, [tab, page]);

  const switchTab = (t) => { setTab(t); setPage(1); };

  return (
    <div className="space-y-5 max-w-screen-xl">
      <div>
        <h1 className="text-lg font-bold text-gray-900">Payments</h1>
        <p className="text-xs text-gray-400 mt-0.5">Telegram Stars payment history</p>
      </div>

      {/* Summary cards */}
      {data && (
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-white rounded-2xl p-4 border border-gray-100 flex items-center gap-3">
            <div className="p-2.5 bg-blue-50 rounded-xl text-blue-600"><CreditCard size={17} /></div>
            <div>
              <p className="text-xl font-bold text-gray-900">{fmt(data.total)}</p>
              <p className="text-xs text-gray-400">Total payments</p>
            </div>
          </div>
          <div className="bg-white rounded-2xl p-4 border border-gray-100 flex items-center gap-3">
            <div className="p-2.5 bg-cyan-50 rounded-xl text-cyan-600"><Gem size={17} /></div>
            <div>
              <p className="text-xl font-bold text-gray-900">
                {fmt(data.payments.filter(p => !p.is_lifetime).length)} / pg
              </p>
              <p className="text-xs text-gray-400">Diamond purchases</p>
            </div>
          </div>
          <div className="bg-white rounded-2xl p-4 border border-gray-100 flex items-center gap-3">
            <div className="p-2.5 bg-amber-50 rounded-xl text-amber-600"><Crown size={17} /></div>
            <div>
              <p className="text-xl font-bold text-gray-900">
                {fmt(data.payments.filter(p => p.is_lifetime).length)} / pg
              </p>
              <p className="text-xs text-gray-400">Lifetime purchases</p>
            </div>
          </div>
        </div>
      )}

      {/* Table card */}
      <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
        {/* Tabs */}
        <div className="flex items-center gap-px px-4 pt-4 border-b border-gray-100">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => switchTab(t.key)}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors border-b-2 -mb-px ${
                tab === t.key
                  ? "border-blue-600 text-blue-700"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {t.label}
            </button>
          ))}
          {data && (
            <span className="ml-auto text-xs text-gray-400 pb-2">
              {fmt(data.total)} total
            </span>
          )}
        </div>

        {/* Table */}
        {loading ? (
          <div className="flex justify-center py-16">
            <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" />
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-50 text-left">
                <th className="px-5 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">#</th>
                <th className="px-5 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">User</th>
                <th className="px-5 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Type</th>
                <th className="px-5 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Amount</th>
                <th className="px-5 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {data?.payments.length === 0 ? (
                <tr><td colSpan={5} className="text-center text-gray-400 py-12">No payments found</td></tr>
              ) : data?.payments.map((p) => (
                <tr key={p.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-5 py-3 text-gray-400 tabular-nums">{p.id}</td>
                  <td className="px-5 py-3">
                    <div>
                      <p className="font-medium text-gray-800">{p.user_name || `#${p.user_id}`}</p>
                      {p.username && <p className="text-xs text-gray-400">@{p.username}</p>}
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    {p.is_lifetime ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 bg-amber-50 px-2 py-1 rounded-full">
                        <Crown size={11} /> Lifetime
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-cyan-700 bg-cyan-50 px-2 py-1 rounded-full">
                        <Gem size={11} /> {p.diamonds} 💎
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-1 text-yellow-600 font-semibold">
                      <Star size={13} />
                      {fmt(p.stars)}
                    </div>
                  </td>
                  <td className="px-5 py-3 text-gray-400 text-xs tabular-nums">
                    {p.created_at ? new Date(p.created_at).toLocaleDateString("en", { month: "short", day: "numeric", year: "numeric" }) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Pagination */}
        {data && data.pages > 1 && (
          <div className="px-5 py-3 border-t border-gray-50 flex items-center justify-between">
            <p className="text-xs text-gray-400">Page {page} of {data.pages}</p>
            <div className="flex gap-1">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                onClick={() => setPage(p => Math.min(data.pages, p + 1))}
                disabled={page === data.pages}
                className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
