import { useEffect, useState } from "react";
import { Save, RotateCcw, Info } from "lucide-react";
import { api } from "../lib/api";

function Field({ label, hint, children }) {
  return (
    <div className="flex items-start justify-between py-4 border-b border-gray-50 last:border-0">
      <div className="mr-8">
        <p className="text-sm font-medium text-gray-800">{label}</p>
        {hint && <p className="text-xs text-gray-400 mt-0.5">{hint}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function NumInput({ value, onChange, min = 1, max = 9999 }) {
  return (
    <input
      type="number"
      min={min}
      max={max}
      value={value ?? ""}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-24 text-right px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
    />
  );
}

const DIAMOND_AMOUNTS = [1, 3, 5, 10, 20, 50];

export default function Settings() {
  const [form, setForm] = useState(null);
  const [original, setOriginal] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.settings().then((s) => {
      setForm(s);
      setOriginal(s);
    }).finally(() => setLoading(false));
  }, []);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));
  const setPrice = (diamonds, stars) =>
    setForm((f) => ({ ...f, diamond_prices: { ...f.diamond_prices, [String(diamonds)]: stars } }));

  const reset = () => { setForm(original); setSaved(false); };

  const save = async () => {
    setSaving(true);
    try {
      await api.saveSettings(form);
      setOriginal(form);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } finally {
      setSaving(false);
    }
  };

  const isDirty = JSON.stringify(form) !== JSON.stringify(original);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-7 h-7 border-2 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!form) return null;

  return (
    <div className="space-y-5 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-gray-900">Settings</h1>
          <p className="text-xs text-gray-400 mt-0.5">Bot configuration</p>
        </div>
        <div className="flex gap-2">
          {isDirty && (
            <button
              onClick={reset}
              className="flex items-center gap-1.5 text-xs text-gray-500 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <RotateCcw size={13} /> Reset
            </button>
          )}
          <button
            onClick={save}
            disabled={!isDirty || saving}
            className={`flex items-center gap-1.5 text-xs font-semibold px-4 py-1.5 rounded-lg transition-all ${
              saved
                ? "bg-emerald-500 text-white"
                : isDirty
                ? "bg-blue-600 text-white hover:bg-blue-700"
                : "bg-gray-100 text-gray-400 cursor-not-allowed"
            }`}
          >
            <Save size={13} />
            {saved ? "Saved!" : saving ? "Saving..." : "Save changes"}
          </button>
        </div>
      </div>

      {/* Restart notice */}
      <div className="flex items-start gap-2.5 bg-amber-50 border border-amber-100 rounded-xl px-4 py-3">
        <Info size={15} className="text-amber-500 mt-0.5 shrink-0" />
        <p className="text-xs text-amber-700">
          Changes are saved to <code className="font-mono bg-amber-100 px-1 rounded">bot_settings.json</code>.
          Restart the bot service for changes to take effect.
        </p>
      </div>

      {/* General settings */}
      <div className="bg-white rounded-2xl border border-gray-100 px-5">
        <h2 className="text-sm font-semibold text-gray-900 pt-4 pb-2">General</h2>
        <Field
          label="Daily Conversion Limit"
          hint="Free users' max conversions per day"
        >
          <NumInput value={form.daily_limit} onChange={(v) => set("daily_limit", v)} min={1} max={100} />
        </Field>
        <Field
          label="Max File Size (MB)"
          hint="Maximum video file size for free users"
        >
          <NumInput value={form.max_file_size_mb} onChange={(v) => set("max_file_size_mb", v)} min={1} max={500} />
        </Field>
        <Field
          label="Max Queue Size"
          hint="Max pending jobs before rejecting new ones"
        >
          <NumInput value={form.max_queue_size} onChange={(v) => set("max_queue_size", v)} min={1} max={200} />
        </Field>
        <Field
          label="Max Concurrent Jobs"
          hint="How many videos process in parallel"
        >
          <NumInput value={form.max_concurrent} onChange={(v) => set("max_concurrent", v)} min={1} max={20} />
        </Field>
        <Field
          label="Lifetime Stars Price"
          hint="Stars required for lifetime premium"
        >
          <NumInput value={form.lifetime_stars} onChange={(v) => set("lifetime_stars", v)} min={1} max={9999} />
        </Field>
      </div>

      {/* Diamond prices */}
      <div className="bg-white rounded-2xl border border-gray-100 px-5 pb-2">
        <div className="pt-4 pb-3 flex items-center justify-between border-b border-gray-50">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Diamond Prices</h2>
            <p className="text-xs text-gray-400 mt-0.5">Stars charged per diamond pack</p>
          </div>
        </div>
        <div className="py-2">
          {DIAMOND_AMOUNTS.map((amount) => (
            <div key={amount} className="flex items-center justify-between py-3 border-b border-gray-50 last:border-0">
              <div className="flex items-center gap-2">
                <span className="text-lg">💎</span>
                <span className="text-sm font-medium text-gray-700">{amount} diamond{amount > 1 ? "s" : ""}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-400">⭐</span>
                <NumInput
                  value={form.diamond_prices?.[String(amount)] ?? ""}
                  onChange={(v) => setPrice(amount, v)}
                  min={1}
                  max={9999}
                />
                <span className="text-xs text-gray-400 w-10">stars</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
