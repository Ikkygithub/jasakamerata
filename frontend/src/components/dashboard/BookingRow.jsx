import { useState } from "react";
import { Link } from "react-router-dom";
import { Download, X } from "lucide-react";
import { toast } from "sonner";
import { api, money, fmtDate, fmtTime, STATUS, downloadFile } from "@/lib/api";

const ACTIONS = {
  photographer: { pending: [["accepted", "Terima"], ["declined", "Tolak"]], accepted: [["deliver", "Serahkan hasil"], ["cancelled", "Batalkan"]], revision_requested: [["deliver", "Kirim revisi"]] },
  customer: { pending: [["cancelled", "Batalkan"]], accepted: [["cancelled", "Batalkan"]], delivered: [["completed", "Setujui hasil"], ["revision_requested", "Minta revisi"], ["disputed", "Ajukan keberatan"]] },
  admin: { pending: [["cancelled", "Batalkan"]], accepted: [["cancelled", "Batalkan"]], delivered: [["completed", "Selesaikan"]], disputed: [["completed", "Selesaikan (fotografer)"], ["cancelled", "Batalkan pesanan"]] },
};
const NEEDS_NOTE = ["revision_requested", "disputed", "declined", "cancelled"];
const PRIMARY = ["accepted", "completed", "deliver"];

export function StatusPill({ status }) {
  return <span className={`status-pill st-${status}`} data-testid="status-pill">{STATUS[status] || status}</span>;
}

function DeliverForm({ b, close, onDone }) {
  const [files, setFiles] = useState([]);
  const [link, setLink] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("link", link);
    fd.append("note", note);
    setBusy(true);
    try { await api.upload(`/bookings/${b.booking_id}/deliver`, fd); toast("Hasil diserahkan ke customer"); onDone(); close(); } catch (err) { toast(err.message); } finally { setBusy(false); }
  };
  return (
    <div className="modal-backdrop">
      <form className="chat-modal auth-form booking-modal" onSubmit={submit} data-testid="deliver-form">
        <button type="button" className="modal-close" onClick={close} data-testid="deliver-close"><X size={18} /></button>
        <p className="eyebrow">SERAHKAN HASIL · {b.booking_id}</p><h2>{b.service}</h2>
        <label>File hasil (JPG/PNG/WEBP/PDF/ZIP, maks 25 MB per file, 10 file)<input type="file" multiple accept=".jpg,.jpeg,.png,.webp,.pdf,.zip" onChange={(e) => setFiles([...e.target.files])} data-testid="deliver-files-input" /></label>
        <label>Atau tautan galeri (https://)<input value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://drive.google.com/..." data-testid="deliver-link-input" /></label>
        <label>Catatan untuk customer<textarea value={note} onChange={(e) => setNote(e.target.value)} data-testid="deliver-note-input" /></label>
        <button className="olive-btn full" disabled={busy} data-testid="deliver-submit">{busy ? "Mengunggah..." : "Serahkan hasil"}</button>
      </form>
    </div>
  );
}

function ReviewForm({ b, onDone }) {
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    try { await api.post(`/bookings/${b.booking_id}/review`, { rating, comment }); toast("Terima kasih atas ulasanmu"); onDone(); } catch (err) { toast(err.message); }
  };
  return (
    <form className="review-form" onSubmit={submit} data-testid={`review-form-${b.booking_id}`}>
      <span className="stars">{[1, 2, 3, 4, 5].map((n) => <button type="button" key={n} className={n <= rating ? "on" : ""} onClick={() => setRating(n)} data-testid={`review-star-${n}`}>★</button>)}</span>
      <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Ceritakan pengalamanmu" data-testid="review-comment-input" />
      <button className="olive-btn" data-testid="review-submit">Kirim ulasan</button>
    </form>
  );
}

function Deliveries({ b }) {
  if (!b.deliveries?.length) return null;
  return (
    <div className="deliveries" data-testid={`deliveries-${b.booking_id}`}>
      {b.deliveries.map((d) => (
        <div key={d.delivery_id}>
          <small>Hasil diserahkan {fmtTime(d.created_at)}{d.note && ` — ${d.note}`}</small>
          {d.link && <a href={d.link} target="_blank" rel="noreferrer" data-testid={`delivery-link-${d.delivery_id}`}>Buka galeri hasil</a>}
          {d.files.map((f) => <button key={f.file_id} className="link-btn" onClick={() => downloadFile(`/bookings/${b.booking_id}/files/${f.file_id}`, f.original_filename).catch((e) => toast(e.message))} data-testid={`delivery-file-${f.file_id}`}><Download size={12} /> {f.original_filename}</button>)}
        </div>
      ))}
    </div>
  );
}

export function BookingRow({ b, role, onChange }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [deliver, setDeliver] = useState(false);
  const act = async (status) => {
    if (status === "deliver") return setDeliver(true);
    let note = "";
    if (NEEDS_NOTE.includes(status)) {
      note = window.prompt(status === "revision_requested" ? "Jelaskan revisi yang diminta:" : status === "disputed" ? "Jelaskan keberatanmu:" : "Alasan (opsional):") ?? null;
      if (note === null) return;
    }
    setBusy(true);
    try { await api.post(`/bookings/${b.booking_id}/status`, { status, note }); toast(`Pesanan: ${STATUS[status]}`); onChange?.(); } catch (e) { toast(e.message); } finally { setBusy(false); }
  };
  const actions = ACTIONS[role]?.[b.status] || [];
  return (
    <div className="order" data-testid={`booking-row-${b.booking_id}`}>
      <div className="order-main">
        <div className="order-top"><StatusPill status={b.status} /><small>{b.booking_id}</small><small className="demo-pay">Pembayaran: DEMO (belum aktif)</small></div>
        <h3>{b.service}</h3>
        <p>{role === "customer" ? <Link to={`/fotografer/${b.photographer_slug}`}>{b.photographer_name}</Link> : `Customer: ${b.customer_name || "-"}`}{role === "admin" && ` · ${b.photographer_name}`}</p>
        <p>{fmtDate(b.date)} · {b.time} · {b.duration} jam · {b.location}</p>
        {b.notes && <p className="note">“{b.notes}”</p>}
        <Deliveries b={b} />
        {role === "customer" && b.status === "completed" && !b.reviewed && <ReviewForm b={b} onDone={onChange} />}
        {b.reviewed && <small className="muted block">Ulasan sudah dikirim.</small>}
        <button className="link-btn" onClick={() => setOpen(!open)} data-testid={`booking-history-toggle-${b.booking_id}`}>{open ? "Sembunyikan riwayat" : "Lihat riwayat status"}</button>
        {open && <ul className="history">{b.history?.map((h, i) => <li key={i}><StatusPill status={h.status} /> oleh {h.by} · {fmtTime(h.at)}{h.note && ` — ${h.note}`}</li>)}</ul>}
      </div>
      <div className="order-side">
        <b>{money(b.total)}</b>
        {role !== "customer" && <small>Komisi 5%: {money(b.commission)} · Fotografer 95%: {money(b.photographer_earning)}</small>}
        <div className="order-actions">{actions.map(([s, label]) => <button key={s} disabled={busy} className={PRIMARY.includes(s) ? "olive-btn" : "outline-btn"} onClick={() => act(s)} data-testid={`booking-action-${s}-${b.booking_id}`}>{label}</button>)}</div>
      </div>
      {deliver && <DeliverForm b={b} close={() => setDeliver(false)} onDone={onChange} />}
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
      {["", "pending", "accepted", "delivered", "revision_requested", "disputed", "completed", "cancelled"].map((s) => <button key={s || "all"} className={value === s ? "chip active" : "chip"} onClick={() => onChange(s)} data-testid={`filter-status-${s || "all"}`}>{s ? STATUS[s] : "Semua"}</button>)}
    </div>
  );
}
