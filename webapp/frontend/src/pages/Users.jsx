import { useEffect, useState, useCallback } from "react";
import {
  Search,
  ChevronLeft,
  ChevronRight,
  Gem,
  Crown,
  ShieldOff,
  Download,
} from "lucide-react";
import { api } from "../lib/api";

export default function UsersPage() {
  const [data, setData] = useState({ users: [], total: 0, page: 1, pages: 1 });
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("conversions");
  const [loading, setLoading] = useState(true);

  // Modal
  const [modal, setModal] = useState(null);
  const [diamondCount, setDiamondCount] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api
      .users(page, search, sort)
      .then(setData)
      .finally(() => setLoading(false));
  }, [page, search, sort]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setPage(1);
  }, [search]);

  const handleGiveDiamonds = async () => {
    if (!modal || !diamondCount) return;
    setActionLoading(true);
    try {
      await api.giveDiamonds(modal.user_id, parseInt(diamondCount));
      setModal(null);
      setDiamondCount("");
      load();
    } catch (e) {
      alert(e.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleTogglePremium = async (user) => {
    setActionLoading(true);
    try {
      await api.togglePremium(user.user_id, !user.is_premium);
      load();
    } catch (e) {
      alert(e.message);
    } finally {
      setActionLoading(false);
    }
  };

  const fmt = (n) => (n ?? 0).toLocaleString();

  const sorts = [
    { value: "conversions", label: "Conversions" },
    { value: "diamonds", label: "Diamonds" },
    { value: "joined", label: "Newest" },
    { value: "name", label: "Name" },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Users</h1>

      {/* Search + Sort */}
      <div className="flex gap-3">
        <div className="relative flex-1 max-w-md">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name, username or user ID..."
            className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {sorts.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        <button
          onClick={() => api.exportUsers()}
          className="flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition-colors"
        >
          <Download size={15} />
          CSV
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="text-left px-4 py-3 font-medium text-gray-500">
                  User
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">
                  User ID
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-500">
                  Conv.
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-500">
                  Diamonds
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-500">
                  Status
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-500">
                  Lang
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">
                  Joined
                </th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-gray-400">
                    Loading...
                  </td>
                </tr>
              ) : data.users.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-gray-400">
                    No users found
                  </td>
                </tr>
              ) : (
                data.users.map((u) => (
                  <tr
                    key={u.user_id}
                    className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium text-gray-900">
                          {u.name || "—"}
                        </p>
                        {u.username && (
                          <p className="text-xs text-gray-400">
                            @{u.username}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">
                      {u.user_id}
                    </td>
                    <td className="px-4 py-3 text-center font-medium">
                      {fmt(u.conversation_count)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="text-cyan-600 font-medium">
                        {fmt(u.diamonds)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {u.is_premium ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-50 text-amber-600 rounded-full text-xs font-medium">
                          <Crown size={12} /> Premium
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">Free</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center text-xs text-gray-500 uppercase">
                      {u.lang || "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {u.joined_at}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => setModal(u)}
                          title="Give diamonds"
                          className="p-1.5 rounded-lg text-cyan-600 hover:bg-cyan-50 transition-colors"
                        >
                          <Gem size={15} />
                        </button>
                        <button
                          onClick={() => handleTogglePremium(u)}
                          title={
                            u.is_premium
                              ? "Remove premium"
                              : "Give premium"
                          }
                          disabled={actionLoading}
                          className={`p-1.5 rounded-lg transition-colors ${
                            u.is_premium
                              ? "text-gray-400 hover:bg-gray-100"
                              : "text-amber-500 hover:bg-amber-50"
                          }`}
                        >
                          {u.is_premium ? (
                            <ShieldOff size={15} />
                          ) : (
                            <Crown size={15} />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
          <span className="text-xs text-gray-400">
            {fmt(data.total)} users total
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-30"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="text-sm text-gray-600">
              {page} / {data.pages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
              disabled={page >= data.pages}
              className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-30"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Give Diamonds Modal */}
      {modal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm shadow-2xl">
            <h3 className="text-lg font-bold text-gray-900 mb-1">
              Give Diamonds
            </h3>
            <p className="text-sm text-gray-500 mb-4">
              {modal.name || modal.username || modal.user_id}
              <span className="text-gray-400">
                {" "}
                — current: {fmt(modal.diamonds)}
              </span>
            </p>
            <input
              type="number"
              min="1"
              value={diamondCount}
              onChange={(e) => setDiamondCount(e.target.value)}
              placeholder="Enter count"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setModal(null);
                  setDiamondCount("");
                }}
                className="flex-1 px-4 py-2.5 border border-gray-200 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleGiveDiamonds}
                disabled={
                  actionLoading || !diamondCount || parseInt(diamondCount) <= 0
                }
                className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {actionLoading ? "..." : "Give"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
