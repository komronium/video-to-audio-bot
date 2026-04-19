import { useState, useEffect, useRef } from "react";
import { Send, Radio, CheckCircle, XCircle, Clock } from "lucide-react";
import { api } from "../lib/api";

export default function Broadcast() {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [activeBid, setActiveBid] = useState(null);
  const [progress, setProgress] = useState(null);
  const [history, setHistory] = useState([]);
  const pollRef = useRef(null);

  useEffect(() => {
    api.broadcasts().then(setHistory).catch(() => {});
  }, []);

  useEffect(() => {
    if (!activeBid) return;
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.broadcastStatus(activeBid);
        setProgress(s);
        if (s.status === "done") {
          clearInterval(pollRef.current);
          setSending(false);
          api.broadcasts().then(setHistory).catch(() => {});
        }
      } catch {
        clearInterval(pollRef.current);
      }
    }, 1000);
    return () => clearInterval(pollRef.current);
  }, [activeBid]);

  const handleSend = async () => {
    if (!text.trim()) return;
    setSending(true);
    try {
      const { broadcast_id } = await api.broadcast(text.trim());
      setActiveBid(broadcast_id);
    } catch (e) {
      alert(e.message);
      setSending(false);
    }
  };

  const pct = progress
    ? Math.round(((progress.sent + progress.failed) / Math.max(progress.total, 1)) * 100)
    : 0;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Broadcast</h1>

      {/* Compose */}
      <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">
          Send message to all users
        </h2>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type your message... (HTML supported)"
          rows={6}
          className="w-full px-4 py-3 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none font-mono"
          disabled={sending}
        />
        <div className="flex items-center justify-between mt-3">
          <span className="text-xs text-gray-400">
            {text.length} characters
          </span>
          <button
            onClick={handleSend}
            disabled={sending || !text.trim()}
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <Send size={15} />
            {sending ? "Sending..." : "Send to All"}
          </button>
        </div>
      </div>

      {/* Progress */}
      {progress && (
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-center gap-2 mb-3">
            {progress.status === "running" ? (
              <Radio size={16} className="text-blue-500 animate-pulse" />
            ) : (
              <CheckCircle size={16} className="text-green-500" />
            )}
            <h2 className="text-sm font-semibold text-gray-700">
              {progress.status === "running" ? "Broadcasting..." : "Broadcast Complete"}
            </h2>
          </div>

          <div className="w-full bg-gray-100 rounded-full h-3 mb-3">
            <div
              className="bg-blue-600 h-3 rounded-full transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>

          <div className="grid grid-cols-4 gap-4 text-center">
            <div>
              <p className="text-lg font-bold text-gray-900">{progress.total}</p>
              <p className="text-xs text-gray-400">Total</p>
            </div>
            <div>
              <p className="text-lg font-bold text-green-600">{progress.sent}</p>
              <p className="text-xs text-gray-400">Sent</p>
            </div>
            <div>
              <p className="text-lg font-bold text-red-500">{progress.failed}</p>
              <p className="text-xs text-gray-400">Failed</p>
            </div>
            <div>
              <p className="text-lg font-bold text-blue-600">{pct}%</p>
              <p className="text-xs text-gray-400">Progress</p>
            </div>
          </div>
        </div>
      )}

      {/* History */}
      {history.length > 0 && (
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">
            Recent Broadcasts
          </h2>
          <div className="space-y-2">
            {history.map((b) => (
              <div
                key={b.id}
                className="flex items-center justify-between py-2.5 px-3 bg-gray-50 rounded-lg"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700 truncate">{b.text}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    <Clock size={10} className="inline mr-1" />
                    {b.started_at ? new Date(b.started_at).toLocaleString() : "—"}
                  </p>
                </div>
                <div className="flex items-center gap-3 ml-4 shrink-0">
                  <span className="flex items-center gap-1 text-xs text-green-600">
                    <CheckCircle size={12} /> {b.sent}
                  </span>
                  {b.failed > 0 && (
                    <span className="flex items-center gap-1 text-xs text-red-500">
                      <XCircle size={12} /> {b.failed}
                    </span>
                  )}
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      b.status === "done"
                        ? "bg-green-50 text-green-600"
                        : "bg-blue-50 text-blue-600"
                    }`}
                  >
                    {b.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
