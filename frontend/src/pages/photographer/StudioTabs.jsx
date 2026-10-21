import { useCallback, useEffect, useState } from "react";
import { Trash2, Plus } from "lucide-react";
import { toast } from "sonner";
import { api, money, fmtDate } from "@/lib/api";
import { AvailabilityCalendar } from "@/components/booking/AvailabilityCalendar";

export const run = async (fn, ok) => { try { await fn(); if (ok) toast(ok); return true; } catch (e) { toast(e.message); return false; } };

export function CalendarTab({ profile }) {
  const [blocks, setBlocks] = useState([]);
  const [form, setForm] = useState({ date: "", start: "08:00", end: "17:00", reason: "" });
  const [key, setKey] = useState(0);
  const load = useCallback(() => api.get("/photographer/availability").then(setBlocks).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);
  const refresh = () => { load(); setKey((k) => k + 1); };
  const add = async (e) => {
    e.preventDefault();
    if (!form.date) return toast("Pilih tanggal di kalender");
    if (await run(() => api.post("/photographer/availability", form), "Jadwal diblokir")) refresh();
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  return (
    <div className="studio-split">
      <AvailabilityCalendar slug={profile.slug} value={form.date} onChange={(d) => setForm({ ...form, date: d })} refreshKey={key} />
      <div>
        <form className="panel-form" onSubmit={add} data-testid="block-form">
          <h3>Blokir jadwal {form.date && `· ${fmtDate(form.date)}`}</h3>
          <div className="two-col"><label>Mulai<input type="time" value={form.start} onChange={set("start")} data-testid="block-start-input" /></label><label>Selesai<input type="time" value={form.end} onChange={set("end")} data-testid="block-end-input" /></label></div>
          <label>Alasan (opsional)<input value={form.reason} onChange={set("reason")} placeholder="Contoh: libur, acara pribadi" data-testid="block-reason-input" /></label>
          <div className="row-actions"><button className="olive-btn" data-testid="block-submit">Blokir jam ini</button><button type="button" className="outline-btn" onClick={() => setForm({ ...form, start: "00:00", end: "23:59" })} data-testid="block-full-day">Satu hari penuh</button></div>
        </form>
        <h3 className="list-title">Jadwal diblokir</h3>
        {!blocks.length && <p className="muted">Belum ada blokir jadwal.</p>}
        {blocks.map((b) => (
          <div className="mini-row" key={b.block_id} data-testid={`block-${b.block_id}`}>
            <span><b>{fmtDate(b.date)}</b> {b.start}–{b.end} {b.reason && `· ${b.reason}`}</span>
            <button className="icon-btn" onClick={async () => { if (await run(() => api.del(`/photographer/availability/${b.block_id}`), "Blokir dihapus")) refresh(); }} data-testid={`block-delete-${b.block_id}`}><Trash2 size={15} /></button>
          </div>
        ))}
      </div>
    </div>
  );
}

const EMPTY = { title: "", price: 500000, duration: "2 jam", deliverables: "", turnaround: "7 hari kerja" };

export function ServicesTab({ profile, reload }) {
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: k === "price" ? Number(e.target.value) : e.target.value });
  const save = async (e) => {
    e.preventDefault();
    const ok = await run(() => (editing ? api.put(`/photographer/services/${editing}`, form) : api.post("/photographer/services", form)), editing ? "Layanan diperbarui" : "Layanan ditambahkan");
    if (ok) { setForm(EMPTY); setEditing(null); reload(); }
  };
  return (
    <div className="studio-split">
      <div>
        {!profile.services.length && <p className="muted">Belum ada layanan. Tambahkan paket pertamamu.</p>}
        {profile.services.map((s) => (
          <div className="mini-row tall" key={s.service_id} data-testid={`studio-service-${s.service_id}`}>
            <span><b>{s.title}</b><small>{s.duration} · {s.deliverables} · {s.turnaround}</small></span>
            <span className="row-actions"><b>{money(s.price)}</b>
              <button className="outline-btn" onClick={() => { setEditing(s.service_id); setForm({ title: s.title, price: s.price, duration: s.duration, deliverables: s.deliverables, turnaround: s.turnaround }); }} data-testid={`service-edit-${s.service_id}`}>Ubah</button>
              <button className="icon-btn" onClick={async () => { if (await run(() => api.del(`/photographer/services/${s.service_id}`), "Layanan dihapus")) reload(); }} data-testid={`service-delete-${s.service_id}`}><Trash2 size={15} /></button>
            </span>
          </div>
        ))}
      </div>
      <form className="panel-form" onSubmit={save} data-testid="service-form">
        <h3>{editing ? "Ubah layanan" : "Tambah layanan"}</h3>
        <label>Nama paket<input required minLength={3} value={form.title} onChange={set("title")} data-testid="service-title-input" /></label>
        <div className="two-col"><label>Harga (Rp)<input required type="number" min="50000" step="10000" value={form.price} onChange={set("price")} data-testid="service-price-input" /></label><label>Durasi<input required value={form.duration} onChange={set("duration")} data-testid="service-duration-input" /></label></div>
        <label>Hasil yang diterima<input required value={form.deliverables} onChange={set("deliverables")} placeholder="Contoh: 100 foto edit" data-testid="service-deliverables-input" /></label>
        <label>Waktu pengerjaan<input value={form.turnaround} onChange={set("turnaround")} data-testid="service-turnaround-input" /></label>
        <div className="row-actions"><button className="olive-btn" data-testid="service-submit"><Plus size={15} /> {editing ? "Simpan" : "Tambah"}</button>{editing && <button type="button" className="outline-btn" onClick={() => { setEditing(null); setForm(EMPTY); }} data-testid="service-cancel-edit">Batal</button>}</div>
      </form>
    </div>
  );
}

export function ProfileTab({ profile, reload }) {
  const [form, setForm] = useState({ bio: profile.bio, service_area: profile.service_area, profile_image: profile.profile_image, min_duration: profile.min_duration });
  const set = (k) => (e) => setForm({ ...form, [k]: k === "min_duration" ? Number(e.target.value) : e.target.value });
  const save = async (e) => { e.preventDefault(); if (await run(() => api.put("/photographer/profile", form), "Profil disimpan")) reload(); };
  return (
    <form className="panel-form wide" onSubmit={save} data-testid="profile-form">
      <label>Bio<textarea rows={4} value={form.bio} onChange={set("bio")} data-testid="profile-bio-input" /></label>
      <div className="two-col"><label>Area layanan<input value={form.service_area} onChange={set("service_area")} data-testid="profile-area-input" /></label><label>Durasi minimum (jam)<input type="number" min="1" max="12" value={form.min_duration} onChange={set("min_duration")} data-testid="profile-min-duration-input" /></label></div>
      <label>URL foto profil<input value={form.profile_image} onChange={set("profile_image")} data-testid="profile-image-input" /></label>
      <p className="muted small">Kategori: <b>{profile.category}</b> (ditetapkan saat pendaftaran).</p>
      <button className="olive-btn" data-testid="profile-save-button">Simpan profil</button>
    </form>
  );
}

