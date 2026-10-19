import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, money, fmtDate, fmtTime, STATUS } from "@/lib/api";

const ACTIONS = {
  photographer: { pending: [["accepted", "Terima"], ["declined", "Tolak"]], accepted: [["completed", "Tandai selesai"], ["cancelled", "Batalkan"]] },
  customer: { pending: [["cancelled", "Batalkan"]], accepted: [["cancelled", "Batalkan"]] },
  admin: { pending: [["cancelled", "Batalkan"]], accepted: [["completed", "Tandai selesai"], ["cancelled", "Batalkan"]] },
};

export function StatusPill({ status }) {
  return <span className={`status-pill st-${status}`} data-testid="status-pill">{STATUS[status] || status}</span>;
}

export function BookingRow({ b, role, onChange }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const act = async (status) => {
    setBusy(true);
    try {
      await api.post(`/bookings/${b.booking_id}/status`, { status });
      toast(`Pesanan ${STATUS[status].toLowerCase()}`);
      onChange?.();
    } catch (e) { toast(e.message); } finally { setBusy(false); }
  };
  const actions = ACTIONS[role]?.[b.status] || [];
  return (
    <div className="order" data-testid={`booking-row-${b.booking_id}`}>
      <div className="order-main">
        <div className="order-top"><StatusPill status={b.status} /><small>{b.booking_id}</small><small className="demo-pay">Pembayaran: DEMO</small></div>
        <h3>{b.service}</h3>
        <p>{role === "customer" ? <Link to={`/fotografer/${b.photographer_slug}`}>{b.photographer_name}</Link> : `Customer: ${b.customer_name || "-"}`}{role === "admin" && ` · ${b.photographer_name}`}</p>
        <p>{fmtDate(b.date)} · {b.time} · {b.duration} jam · {b.location}</p>
        {b.notes && <p className="note">“{b.notes}”</p>}
        <button className="link-btn" onClick={() => setOpen(!open)} data-testid={`booking-history-toggle-${b.booking_id}`}>{open ? "Sembunyikan riwayat" : "Lihat riwayat status"}</button>
        {open && <ul className="history">{b.history?.map((h, i) => <li key={i}><StatusPill status={h.status} /> oleh {h.by} · {fmtTime(h.at)}{h.note && ` — ${h.note}`}</li>)}</ul>}
      </div>
      <div className="order-side">
        <b>{money(b.total)}</b>
        {role !== "customer" && <small>Komisi 10%: {money(b.commission)}</small>}
        <div className="order-actions">{actions.map(([s, label]) => <button key={s} disabled={busy} className={s === "accepted" || s === "completed" ? "olive-btn" : "outline-btn"} onClick={() => act(s)} data-testid={`booking-action-${s}-${b.booking_id}`}>{label}</button>)}</div>
      </div>
    </div>
  );
}

export function BookingList({ items, role, onChange, empty = "Belum ada pesanan." }) {
  if (!items) return <p className="muted">Memuat pesanan...</p>;
  if (!items.length) return <div className="empty" data-testid="bookings-empty"><p>{empty}</p></div>;
  return <div className="order-list" data-testid="bookings-list">{items.map((b) => <BookingRow key={b.booking_id} b={b} role={role} onChange={onChange} />)}</div>;
}

export function StatusFilter({ value, onChange }) {
  return (
    <div className="chip-row" data-testid="booking-status-filter">
      {["", "pending", "accepted", "completed", "declined", "cancelled"].map((s) => <button key={s || "all"} className={value === s ? "chip active" : "chip"} onClick={() => onChange(s)} data-testid={`filter-status-${s || "all"}`}>{s ? STATUS[s] : "Semua"}</button>)}
    </div>
  );
}
