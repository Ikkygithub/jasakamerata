export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(method, path, body) {
  const res = await fetch(`${API}${path}`, {
    method,
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new ApiError(typeof d === "string" ? d : "Data yang dikirim belum valid", res.status);
  }
  return data;
}

export const api = {
  get: (p) => request("GET", p),
  post: (p, b) => request("POST", p, b || {}),
  put: (p, b) => request("PUT", p, b),
  del: (p) => request("DELETE", p),
};

export const money = (n) => new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(n || 0);

export const fmtDate = (d) => new Date(`${d}T00:00:00`).toLocaleDateString("id-ID", { weekday: "short", day: "numeric", month: "short", year: "numeric" });

export const fmtTime = (iso) => new Date(iso).toLocaleString("id-ID", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export const STATUS = { pending: "Menunggu", accepted: "Diterima", declined: "Ditolak", completed: "Selesai", cancelled: "Dibatalkan", requested: "Diajukan", approved: "Disetujui", rejected: "Ditolak" };

export const dashboardPath = (role) => (role === "admin" ? "/admin" : role === "photographer" ? "/studio" : "/customer/dashboard");
