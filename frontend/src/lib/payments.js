import { api } from "@/lib/api";

let configPromise;
const getConfig = () => (configPromise ||= api.get("/payments/config"));

function loadSnap(cfg) {
  if (window.snap) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = cfg.snap_url;
    s.setAttribute("data-client-key", cfg.client_key);
    s.onload = resolve;
    s.onerror = () => reject(new Error("Gagal memuat halaman pembayaran Midtrans"));
    document.body.appendChild(s);
  });
}

export const paymentsEnabled = async () => (await getConfig()).enabled;

export async function payBooking(bookingId, onDone) {
  const cfg = await getConfig();
  if (!cfg.enabled) throw new Error("Pembayaran online belum diaktifkan");
  await loadSnap(cfg);
  const { token } = await api.post(`/payments/bookings/${bookingId}/snap`);
  const check = () => api.post(`/payments/bookings/${bookingId}/check`).catch(() => null).finally(onDone);
  window.snap.pay(token, { onSuccess: check, onPending: check, onError: check, onClose: onDone });
}
