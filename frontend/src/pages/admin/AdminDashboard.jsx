import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { api, money, fmtTime, STATUS } from "@/lib/api";
import { DashShell, Stat } from "@/components/dashboard/DashShell";
import { BookingList, StatusFilter, StatusPill } from "@/components/dashboard/BookingRow";

export const act = async (fn, ok, after) => { try { await fn(); toast(ok); after?.(); return true; } catch (e) { toast(e.message); return false; } };

function Overview({ o }) {
  return (
    <>
      <div className="stats four">
        <Stat label="Total pengguna" value={o.users} testid="admin-stat-users" />
        <Stat label="Fotografer / terverifikasi" value={`${o.photographers} / ${o.verified}`} testid="admin-stat-photographers" />
        <Stat label="Verifikasi menunggu" value={o.pending_verification} testid="admin-stat-pending" />
        <Stat label="Komisi 5% tercatat (DEMO)" value={money(o.commission)} testid="admin-stat-commission" />
      </div>
      <h3 className="list-title">Pesanan per status · nilai pesanan selesai {money(o.completed_value)}</h3>
      <div className="stats four">{Object.entries(o.bookings).map(([s, n]) => <Stat key={s} label={STATUS[s]} value={n} testid={`admin-bookings-${s}`} />)}</div>
      <div className="dash-cards">
        <Link to="/admin/penarikan" className="dash-card" data-testid="admin-overview-payouts">{o.payouts_open} penarikan perlu tindakan →</Link>
        <Link to="/admin/verifikasi" className="dash-card" data-testid="admin-overview-verifications">{o.pending_verification} pengajuan verifikasi →</Link>
        <Link to="/admin/fotografer" className="dash-card" data-testid="admin-overview-listing">{o.pending_listing} profil menunggu publikasi →</Link>
      </div>
    </>
  );
}

function Photographers() {
  const [status, setStatus] = useState("pending");
  const [items, setItems] = useState(null);
  const load = useCallback(() => api.get(`/admin/photographers?status=${status}`).then(setItems).catch(() => setItems([])), [status]);
  useEffect(() => { load(); }, [load]);
  const decide = (pid, action) => act(() => api.post(`/admin/photographers/${pid}/listing`, { action }), "Status publikasi diperbarui", load);
  return (
    <>
      <div className="chip-row">{[["pending", "Menunggu publikasi"], ["approved", "Tampil publik"], ["rejected", "Disembunyikan"], ["", "Semua"]].map(([k, l]) => <button key={k || "all"} className={status === k ? "chip active" : "chip"} onClick={() => setStatus(k)} data-testid={`admin-ph-filter-${k || "all"}`}>{l}</button>)}</div>
      {items && !items.length && <div className="empty"><p>Tidak ada fotografer di status ini.</p></div>}
      {items?.map((p) => (
        <div className="mini-row tall" key={p.photographer_id} data-testid={`admin-ph-${p.photographer_id}`}>
          <span><b>{p.name} {p.demo && <em className="demo-inline">DEMO</em>}</b><small>{p.category} · {p.gallery?.length || 0} foto · verifikasi: {STATUS[p.verification?.status] || "-"}</small></span>
          <span className="row-actions">
            {p.listing_status === "approved" && <Link to={`/fotografer/${p.slug}`} className="outline-btn" data-testid={`admin-view-${p.photographer_id}`}>Lihat</Link>}
            {p.listing_status !== "approved" ? <button className="olive-btn" onClick={() => decide(p.photographer_id, "publish")} data-testid={`admin-approve-${p.photographer_id}`}>Tampilkan publik</button>
              : <button className="outline-btn" onClick={() => decide(p.photographer_id, "unpublish")} data-testid={`admin-reject-${p.photographer_id}`}>Sembunyikan</button>}
          </span>
        </div>
      ))}
    </>
  );
}

function Verifications() {
  const [status, setStatus] = useState("pending");
  const [items, setItems] = useState(null);
  const load = useCallback(() => api.get(`/admin/verifications?status=${status}`).then(setItems).catch(() => setItems([])), [status]);
  useEffect(() => { load(); }, [load]);
  const view = async (sid, doc) => {
    const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/admin/verifications/${sid}/documents/${doc}`, { credentials: "include" });
    if (!res.ok) return toast("Dokumen tidak dapat dibuka");
    window.open(URL.createObjectURL(await res.blob()), "_blank");
  };
  const decide = (sid, action) => {
    const note = action === "approve" ? "" : window.prompt("Alasan keputusan:");
    if (note === null) return;
    act(() => api.post(`/admin/verifications/${sid}`, { action, note }), "Keputusan verifikasi disimpan", load);
  };
  return (
    <>
      <div className="chip-row">{["pending", "needs_fix", "approved", "rejected"].map((k) => <button key={k} className={status === k ? "chip active" : "chip"} onClick={() => setStatus(k)} data-testid={`admin-ver-filter-${k}`}>{STATUS[k] || k}</button>)}</div>
      {items && !items.length && <div className="empty"><p>Tidak ada pengajuan.</p></div>}
      {items?.map((v) => (
        <div className="order" key={v.submission_id} data-testid={`admin-ver-${v.submission_id}`}>
          <div className="order-main">
            <div className="order-top"><StatusPill status={v.status} /><small>{fmtTime(v.created_at)}</small></div>
            <h3>{v.photographer_name}</h3>
            <p>{v.experience}</p>{v.links && <p>Tautan: {v.links}</p>}
            <p className="muted small">Cek otomatis: formulir lengkap ✓ · KTP terunggah ✓ · minimal 3 portofolio ✓ (keaslian dokumen harus diperiksa manual)</p>
            <div className="row-actions">{v.documents.map((d) => <button key={d.doc_id} className="link-btn" onClick={() => view(v.submission_id, d.doc_id)} data-testid={`admin-ver-doc-${d.doc_id}`}>Buka {d.kind === "id_document" ? "KTP" : "dokumen pendukung"}</button>)}</div>
            {v.note && <p className="note">Catatan: {v.note}</p>}
          </div>
          {v.status === "pending" && <div className="order-actions">
            <button className="olive-btn" onClick={() => decide(v.submission_id, "approve")} data-testid={`admin-ver-approve-${v.submission_id}`}>Setujui</button>
            <button className="outline-btn" onClick={() => decide(v.submission_id, "needs_fix")} data-testid={`admin-ver-fix-${v.submission_id}`}>Minta perbaikan</button>
            <button className="outline-btn" onClick={() => decide(v.submission_id, "reject")} data-testid={`admin-ver-reject-${v.submission_id}`}>Tolak</button>
          </div>}
        </div>
      ))}
    </>
  );
}

function Bookings() {
  const [status, setStatus] = useState("");
  const [items, setItems] = useState(null);
  const load = useCallback(() => api.get(`/bookings?status=${status}`).then(setItems).catch(() => setItems([])), [status]);
  useEffect(() => { load(); }, [load]);
  return <><StatusFilter value={status} onChange={setStatus} /><BookingList items={items} role="admin" onChange={load} /></>;
}

const PAYOUT_ACTIONS = { requested: [["approve", "Setujui"], ["reject", "Tolak"]], approved: [["process", "Mulai transfer"], ["reject", "Tolak"]], processing: [["success", "Transfer berhasil"], ["fail", "Transfer gagal"]] };

function Payouts() {
  const [items, setItems] = useState([]);
  const [account, setAccount] = useState({});
  const load = useCallback(() => { setAccount({}); api.get("/admin/payouts").then(setItems).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);
  const decide = (po, action) => {
    let note = "";
    let reference = "";
    if (action === "success") { reference = window.prompt("Nomor referensi transfer bank (wajib):"); if (reference === null) return; }
    if (action === "reject" || action === "fail") { note = window.prompt("Alasan:"); if (note === null) return; }
    act(() => api.post(`/admin/payouts/${po.payout_id}`, { action, note, reference }), "Status penarikan diperbarui", load);
  };
  const reveal = (id) => api.get(`/admin/payouts/${id}/account`).then((a) => setAccount({ ...account, [id]: a })).catch((e) => toast(e.message));
  if (!items.length) return <div className="empty"><p>Belum ada permintaan penarikan.</p></div>;
  return items.map((p) => (
    <div className="order" key={p.payout_id} data-testid={`admin-payout-${p.payout_id}`}>
      <div className="order-main">
        <div className="order-top"><StatusPill status={p.status} /><small>{p.payout_id} · {fmtTime(p.created_at)}</small></div>
        <h3>{money(p.amount)} · {p.photographer_name}</h3>
        <p>{p.bank_name || "Bank lama"} · {p.holder_name || "-"} · {account[p.payout_id]?.account_number || p.bank_account_masked}
          {["approved", "processing"].includes(p.status) && !account[p.payout_id] && <button className="link-btn" onClick={() => reveal(p.payout_id)} data-testid={`admin-payout-reveal-${p.payout_id}`}> · Tampilkan nomor lengkap</button>}</p>
        {p.transfer_reference && <p>Referensi transfer: <b>{p.transfer_reference}</b></p>}
        <ul className="history">{p.history?.map((h, i) => <li key={i}><StatusPill status={h.status} /> {h.by} · {fmtTime(h.at)}{h.note && ` — ${h.note}`}</li>)}</ul>
      </div>
      <div className="order-actions">{(PAYOUT_ACTIONS[p.status] || []).map(([a, l]) => <button key={a} className={["approve", "process", "success"].includes(a) ? "olive-btn" : "outline-btn"} onClick={() => decide(p, a)} data-testid={`admin-payout-${a}-${p.payout_id}`}>{l}</button>)}</div>
    </div>
  ));
}

const LEDGER_TYPES = { platform_commission: "Komisi platform 5%", earning: "Pendapatan fotografer 95%", payout_reserve: "Cadangan penarikan", payout_release: "Pengembalian dana penarikan" };

function Ledger() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/admin/ledger").then(setItems).catch(() => {}); }, []);
  if (!items.length) return <div className="empty"><p>Belum ada transaksi tercatat.</p></div>;
  return <table className="data-table" data-testid="admin-ledger-table"><thead><tr><th>Waktu</th><th>Jenis</th><th>Fotografer</th><th>Referensi</th><th>Nominal</th></tr></thead><tbody>{items.map((e) => <tr key={e.entry_id}><td>{fmtTime(e.created_at)}</td><td>{LEDGER_TYPES[e.type] || e.type}</td><td>{e.photographer_name}</td><td>{e.ref}</td><td>{money(e.amount)}</td></tr>)}</tbody></table>;
}

function Users() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/admin/users").then(setItems).catch(() => {}); }, []);
  return <table className="data-table" data-testid="admin-users-table"><thead><tr><th>Nama</th><th>Email</th><th>Peran</th><th>Rekening</th></tr></thead><tbody>{items.map((u) => <tr key={u.user_id}><td>{u.name}</td><td>{u.email}</td><td>{u.role || "customer"}</td><td>{u.bank ? `${u.bank.bank_name} ${u.bank.masked}` : u.bank_account_masked || "-"}</td></tr>)}</tbody></table>;
}

function Audit() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/admin/audit").then(setItems).catch(() => {}); }, []);
  if (!items.length) return <div className="empty"><p>Belum ada aktivitas tercatat.</p></div>;
  return <table className="data-table" data-testid="admin-audit-table"><thead><tr><th>Waktu</th><th>Aktor</th><th>Aksi</th><th>Target</th><th>Detail</th></tr></thead><tbody>{items.map((l) => <tr key={l.log_id}><td>{fmtTime(l.created_at)}</td><td>{l.actor_name} ({l.actor_role})</td><td>{l.action}</td><td>{l.target}</td><td>{l.detail}</td></tr>)}</tbody></table>;
}

export default function AdminDashboard() {
  const params = useParams();
  const tab = params.tab && params.tab !== "dashboard" ? params.tab : "ringkasan";
  const [o, setO] = useState(null);
  useEffect(() => { api.get("/admin/overview").then(setO).catch(() => {}); }, [tab]);
  const tabs = [["ringkasan", "Ringkasan"], ["fotografer", "Fotografer", o?.pending_listing], ["verifikasi", "Verifikasi", o?.pending_verification], ["pesanan", "Pesanan", o?.bookings?.disputed], ["penarikan", "Penarikan", o?.payouts_open], ["ledger", "Komisi & Ledger"], ["pengguna", "Pengguna"], ["audit", "Audit log"]].map(([key, label, badge]) => ({ key, label, badge, to: key === "ringkasan" ? "/admin" : `/admin/${key}` }));
  return (
    <DashShell eyebrow="PANEL ADMIN" title="Operasional Jasakamerata." subtitle="Verifikasi fotografer, pantau pesanan & sengketa, dan proses penarikan saldo." tabs={tabs} active={tab}>
      {tab === "ringkasan" && (o ? <Overview o={o} /> : <p className="muted">Memuat...</p>)}
      {tab === "fotografer" && <Photographers />}
      {tab === "verifikasi" && <Verifications />}
      {tab === "pesanan" && <Bookings />}
      {tab === "penarikan" && <Payouts />}
      {tab === "ledger" && <Ledger />}
      {tab === "pengguna" && <Users />}
      {tab === "audit" && <Audit />}
    </DashShell>
  );
}
