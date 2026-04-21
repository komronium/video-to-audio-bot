import { useEffect, useState } from "react";
import { Headphones, ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "../lib/api";

const TABS = [
  { key: "all", label: "All" },
  { key: "video", label: "🎬 Video" },
  { key: "youtube", label: "▶️ YouTube" },
  { key: "instagram", label: "📸 Instagram" },
  { key: "tiktok", label: "🎵 TikTok" },
  { key: "premium", label: "👑 Premium" },
  { key: "free", label: "🆓 Free" },
];

function fmt(n) {
  return (n ?? 0).toLocaleString();
}

export default function Conversions() {
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("all");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = (f, p) => {
    setLoading(true);
    api.conversions(p, f)
      .then(setData)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(tab, page); }, [tab, page]);

  const switchTab = (t) => { setTab(t); setPage(1); };

  return (
    <div className="space-y-5 max-w-screen-xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-gray-900">Conversions</h1>
          <p className="text-xs text-gray-400 mt-0.5">All video-to-audio conversion history</p>
        </div>
        {data && (
          <div className="flex items-center gap-2 bg-white border border-gray-100 rounded-xl px-4 py-2">
            <Headphones size={16} className="text-purple-500" />
            <span className="text-sm font-bold text-gray-800">{fmt(data.total)}</span>
            <span className="text-xs text-gray-400">total</span>
          </div>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
        {/* Tabs */}
        <div className="flex items-center px-4 pt-4 border-b border-gray-100 gap-px">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => switchTab(t.key)}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors border-b-2 -mb-px ${tab === t.key
                ? "border-purple-600 text-purple-700"
                : "border-transparent text-gray-500 hover:text-gray-700"
                }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex justify-center py-16">
            <div className="animate-spin w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full" />
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-50 text-left">
                <th className="px-5 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">#</th>
                <th className="px-5 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">User</th>
                <th className="px-5 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Source</th>
                <th className="px-5 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Plan</th>
                <th className="px-5 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Status</th>
                <th className="px-5 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wider">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {data?.conversions.length === 0 ? (
                <tr><td colSpan={5} className="text-center text-gray-400 py-12">No conversions found</td></tr>
              ) : data?.conversions.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-5 py-3 text-gray-400 tabular-nums text-xs">{c.id}</td>
                  <td className="px-5 py-3">
                    <div>
                      <p className="font-medium text-gray-800">{c.user_name || `#${c.user_id}`}</p>
                      {c.username && <p className="text-xs text-gray-400">@{c.username}</p>}
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    {c.type === "youtube" ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-600 bg-red-50 px-2 py-1 rounded-full">▶️ YouTube</span>
                    ) : c.type === "instagram" ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-pink-600 bg-pink-50 px-2 py-1 rounded-full">📸 Instagram</span>
                    ) : c.type === "tiktok" ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-gray-800 bg-gray-100 px-2 py-1 rounded-full">🎵 TikTok</span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 bg-blue-50 px-2 py-1 rounded-full">🎬 Video</span>
                    )}
                  </td>
                  <td className="px-5 py-3">
                    {c.is_premium ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 bg-amber-50 px-2 py-1 rounded-full">
                        👑 Premium
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                        Free
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3">
                    {c.success !== false ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-1 rounded-full">
                        ✓ Success
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-600 bg-red-50 px-2 py-1 rounded-full">
                        ✗ Failed
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-gray-400 text-xs tabular-nums">
                    {c.created_at ? new Date(c.created_at).toLocaleDateString("en", { month: "short", day: "numeric", year: "numeric" }) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

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
