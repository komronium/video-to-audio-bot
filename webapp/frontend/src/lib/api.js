const API = "/api";

function headers() {
  const h = { "Content-Type": "application/json" };
  const token = localStorage.getItem("token");
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

async function request(url, options = {}) {
  const res = await fetch(`${API}${url}`, {
    headers: headers(),
    ...options,
  });
  if (res.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export const api = {
  login: (password) =>
    request("/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),

  dashboard: () => request("/dashboard"),
  chart: (days = 30) => request(`/dashboard/chart?days=${days}`),
  topUsers: (limit = 10) => request(`/top-users?limit=${limit}`),
  revenue: () => request("/revenue"),

  users: (page = 1, search = "", sort = "conversions", perPage = 20) =>
    request(
      `/users?page=${page}&search=${encodeURIComponent(search)}&sort=${sort}&per_page=${perPage}`
    ),
  user: (userId) => request(`/users/${userId}`),
  giveDiamonds: (userId, count) =>
    request(`/users/${userId}/diamonds`, {
      method: "POST",
      body: JSON.stringify({ count }),
    }),
  togglePremium: (userId, isPremium) =>
    request(`/users/${userId}/premium`, {
      method: "POST",
      body: JSON.stringify({ is_premium: isPremium }),
    }),
  exportUsers: () => {
    const token = localStorage.getItem("token");
    window.open(`${API}/users/export?token=${token}`, "_blank");
  },

  broadcast: (text, parseMode = "HTML") =>
    request("/broadcast", {
      method: "POST",
      body: JSON.stringify({ text, parse_mode: parseMode }),
    }),
  broadcastStatus: (bid) => request(`/broadcast/${bid}`),
  broadcasts: () => request("/broadcasts"),

  payments: (page = 1, type = "all") =>
    request(`/payments?page=${page}&type=${type}`),

  conversions: (page = 1, filter = "all") =>
    request(`/conversions?page=${page}&filter=${filter}`),

  analytics: () => request("/analytics"),

  settings: () => request("/settings"),
  saveSettings: (data) =>
    request("/settings", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
