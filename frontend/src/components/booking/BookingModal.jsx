import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, X, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { api, money, mediaUrl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { AvailabilityCalendar } from "./AvailabilityCalendar";

const TIMES = Array.from({ length: 33 }, (_, i) => `${String(6 + Math.floor(i / 2)).padStart(2, "0")}:${i % 2 ? "30" : "00"}`);

function Alternatives({ list, close }) {
  return (
    <div className="alt-box" data-testid="booking-alternatives">
      <p className="eyebrow">JADWAL BENTROK · ALTERNATIF TERSEDIA</p>
      {list.length ? list.map((a) => (
        <Link key={a.photographer_id} to={`/fotografer/${a.slug}`} onClick={close} className="alt-item" data-testid={`alternative-${a.photographer_id}`}>
          <img src={mediaUrl(a.profile_image || a.gallery?.[0])} alt={a.name} /><span><b>{a.name}</b><small>{a.category} · mulai {money(a.starting_price)}</small></span><ArrowRight size={15} />
        </Link>
      )) : <p className="muted">Belum ada fotografer lain yang kosong di waktu tersebut. Coba tanggal lain.</p>}
    </div>
  );
}

export function BookingModal({ p, close }) {
  const { user } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ service_id: p.services[0]?.service_id || "", date: "", time: "09:00", duration: p.min_duration || 2, location: "", notes: "", agree_policy: false });
  const [alts, setAlts] = useState(null);
  const [done, setDone] = useState(null);
  const [sending, setSending] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const service = p.services.find((s) => s.service_id === form.service_id);

  const submit = async (e) => {
    e.preventDefault();
    if (!user) { toast("Masuk terlebih dahulu untuk mengajukan booking"); nav("/masuk"); return; }
    if (!form.date) { toast("Pilih tanggal di kalender"); return; }
    if (!form.agree_policy) { toast("Setujui kebijakan pemesanan terlebih dahulu"); return; }
    setSending(true); setAlts(null);
    try {
      setDone(await api.post("/bookings", { ...form, photographer_id: p.photographer_id, duration: Number(form.duration) }));
    } catch (err) {
      toast(err.message);
      if (err.status === 409) setAlts(await api.get(`/photographers/available?date=${form.date}&time=${form.time}&duration=${form.duration}&category=${p.category}&exclude=${p.photographer_id}`).catch(() => []));
    } finally { setSending(false); }
  };

  if (done) return (
    <div className="modal-backdrop"><div className="chat-modal auth-form booking-done" data-testid="booking-success">
      <CheckCircle2 size={34} className="ok-icon" /><p className="eyebrow">PERMINTAAN TERKIRIM</p><h2>{done.booking_id}</h2>
      <p className="muted">{p.name} akan meninjau permintaanmu. Pembayaran masih tahap DEMO — belum ada tagihan.</p>
      <Link to="/customer/pesanan" className="olive-btn full" data-testid="booking-go-orders">Lihat pesanan saya</Link>
      <button type="button" className="outline-btn full" onClick={close} data-testid="close-booking">Tutup</button>
    </div></div>
  );

  return (
    <div className="modal-backdrop">
      <form className="chat-modal auth-form booking-modal" onSubmit={submit} data-testid="booking-modal">
        <button type="button" className="modal-close" onClick={close} data-testid="close-booking"><X size={18} /></button>
        <p className="eyebrow">AJUKAN PERMINTAAN</p><h2>{p.name}</h2>
        <label>Paket layanan<select value={form.service_id} onChange={set("service_id")} data-testid="booking-service-select">{p.services.map((s) => <option key={s.service_id} value={s.service_id}>{s.title} — {money(s.price)}</option>)}</select></label>
        <AvailabilityCalendar slug={p.slug} value={form.date} onChange={(d) => setForm({ ...form, date: d })} />
        <div className="two-col">
          <label>Jam mulai<select value={form.time} onChange={set("time")} data-testid="booking-time-input">{TIMES.map((t) => <option key={t}>{t}</option>)}</select></label>
          <label>Durasi (jam)<input required type="number" min="1" max="12" value={form.duration} onChange={set("duration")} data-testid="booking-duration-input" /></label>
        </div>
        <label>Lokasi sesi<input required value={form.location} onChange={set("location")} placeholder="Contoh: Pantai Losari" data-testid="booking-location-input" /></label>
        <label>Catatan<textarea value={form.notes} onChange={set("notes")} data-testid="booking-notes-input" /></label>
        {service && <p className="booking-total" data-testid="booking-total">Total harga paket <b>{money(service.price)}</b></p>}
        <p className="muted small">Pembayaran dilakukan setelah fotografer menerima pesanan, maksimal 24 jam. Jika belum aktif, pesanan berjalan dalam mode DEMO tanpa tagihan.</p>
        <label className="check"><input type="checkbox" checked={form.agree_policy} onChange={(e) => setForm({ ...form, agree_policy: e.target.checked })} data-testid="booking-agree-checkbox" /><span>Saya memahami ruang lingkup paket dan menyetujui <Link to="/kebijakan/pembatalan-refund" target="_blank">kebijakan pembatalan, revisi & sengketa</Link>.</span></label>
        {alts && <Alternatives list={alts} close={close} />}
        <button className="olive-btn full" disabled={sending} data-testid="booking-submit">{sending ? "Mengirim..." : "Kirim permintaan"} <ArrowRight size={16} /></button>
      </form>
    </div>
  );
}
