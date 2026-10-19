import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { api, money, fmtTime, STATUS } from "@/lib/api";
import { DashShell, Stat } from "@/components/dashboard/DashShell";
import { BookingList, StatusFilter, StatusPill } from "@/components/dashboard/BookingRow";

const act = async (fn, ok, after) => { try { await fn(); toast(ok); after(); } catch (e) { toast(e.message); } };

function Overview({ o }) {
  return (
    <>
      <div className="stats four">
        <Stat label="Total pengguna" value={o.users} testid="admin-stat-users" />
        <Stat label="Fotografer" value={o.photographers} testid="admin-stat-photographers" />
        <Stat label="Menunggu verifikasi" value={o.pending_verification} testid="admin-stat-pending" />
        <Stat label="Komisi tercatat (DEMO)" value={money(o.commission_demo)} testid="admin-stat-commission" />
      </div>
      <h3 className="list-title">Pesanan per status</h3>
      <div className="stats five">{Object.entries(o.bookings).map(([s, n]) => <Stat key={s} label={STATUS[s]} value={n} testid={`admin-bookings-${s}`} />)}</div>
      <Link to="/admin/payout" className="dash-card" data-testid="admin-overview-payouts">{o.payouts_requested} permintaan pencairan menunggu →</Link>
    </>
  );
}

function Photographers() {
  const [status, setStatus] = useState("pending");
  const [items, setItems] = useState(null);
  const load = useCallback(() => api.get(`/admin/photographers?status=${status}`).then(setItems).catch(() => setItems([])), [status]);
  useEffect(() => { load(); }, [load]);
  const decide = (pid, action) => act(() => api.post(`/admin/photographers/${pid}/verify`, { action }), "Status fotografer diperbarui", load);
  return (
    <>
      <div className="chip-row">{[["pending", "Menunggu"], ["approved", "Disetujui"], ["rejected", "Ditolak"], ["", "Semua"]].map(([k, l]) => <button key={k || "all"} className={status === k ? "chip active" : "chip"} onClick={() => setStatus(k)} data-testid={`admin-ph-filter-${k || "all"}`}>{l}</button>)}</div>
      {items && !items.length && <div className="empty"><p>Tidak ada fotografer di status ini.</p></div>}
      {items?.map((p) => (
        <div className="mini-row tall" key={p.photographer_id} data-testid={`admin-ph-${p.photographer_id}`}>
          <span><b>{p.name} {p.demo && <em className="demo-inline">DEMO</em>}</b><small>{p.category} · {p.listing_status} · {p.verified ? "terverifikasi" : "belum terverifikasi"} · {p.gallery?.length || 0} foto</small></span>
          <span className="row-actions">
            {p.listing_status !== "approved" && <button className="olive-btn" onClick={() => decide(p.photographer_id, "approve")} data-testid={`admin-approve-${p.photographer_id}`}>Setujui</button>}
            {p.listing_status === "approved" && p.verified && <button className="outline-btn" onClick={() => decide(p.photographer_id, "unverify")} data-testid={`admin-unverify-${p.photographer_id}`}>Cabut verifikasi</button>}
            {p.listing_status === "approved" && !p.verified && <button className="olive-btn" onClick={() => decide(p.photographer_id, "approve")} data-testid={`admin-verify-${p.photographer_id}`}>Verifikasi</button>}
            {p.listing_status !== "rejected" && <button className="outline-btn" onClick={() => decide(p.photographer_id, "reject")} data-testid={`admin-reject-${p.photographer_id}`}>Tolak</button>}
          </span>
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

function Payouts() {
  const [items, setItems] = useState([]);
  const load = useCallback(() => api.get("/admin/payouts").then(setItems).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);
  if (!items.length) return <div className="empty"><p>Belum ada permintaan pencairan.</p></div>;
  return items.map((p) => (
    <div className="mini-row tall" key={p.payout_id} data-testid={`admin-payout-${p.payout_id}`}>
      <span><b>{money(p.amount)} · {p.photographer_name}</b><small>Rekening {p.bank_account_masked} · {fmtTime(p.created_at)} · DEMO, tanpa transfer nyata</small></span>
      <span className="row-actions"><StatusPill status={p.status} />{p.status === "requested" && <>
        <button className="olive-btn" onClick={() => act(() => api.post(`/admin/payouts/${p.payout_id}`, { action: "approve" }), "Pencairan disetujui", load)} data-testid={`admin-payout-approve-${p.payout_id}`}>Setujui</button>
        <button className="outline-btn" onClick={() => act(() => api.post(`/admin/payouts/${p.payout_id}`, { action: "reject" }), "Pencairan ditolak", load)} data-testid={`admin-payout-reject-${p.payout_id}`}>Tolak</button></>}
      </span>
    </div>
  ));
}

function Users() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/admin/users").then(setItems).catch(() => {}); }, []);
  return <table className="data-table" data-testid="admin-users-table"><thead><tr><th>Nama</th><th>Email</th><th>Peran</th><th>Rekening</th></tr></thead><tbody>{items.map((u) => <tr key={u.user_id}><td>{u.name}</td><td>{u.email}</td><td>{u.role || "customer"}</td><td>{u.bank_account_masked || "-"}</td></tr>)}</tbody></table>;
}

function Audit() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/admin/audit").then(setItems).catch(() => {}); }, []);
  if (!items.length) return <div className="empty"><p>Belum ada aktivitas tercatat.</p></div>;
  return <table className="data-table" data-testid="admin-audit-table"><thead><tr><th>Waktu</th><th>Aktor</th><th>Aksi</th><th>Target</th></tr></thead><tbody>{items.map((l) => <tr key={l.log_id}><td>{fmtTime(l.created_at)}</td><td>{l.actor_name} ({l.actor_role})</td><td>{l.action}</td><td>{l.target}</td></tr>)}</tbody></table>;
}

export default function AdminDashboard() {
  const { tab = "ringkasan" } = useParams();
  const [o, setO] = useState(null);
  useEffect(() => { api.get("/admin/overview").then(setO).catch(() => {}); }, [tab]);
  const tabs = [["ringkasan", "Ringkasan"], ["fotografer", "Fotografer", o?.pending_verification], ["pesanan", "Pesanan"], ["payout", "Pencairan", o?.payouts_requested], ["pengguna", "Pengguna"], ["audit", "Audit log"]].map(([key, label, badge]) => ({ key, label, badge, to: key === "ringkasan" ? "/admin" : `/admin/${key}` }));
  return (
    <DashShell eyebrow="PANEL ADMIN" title="Operasional Jasa Kamera." subtitle="Verifikasi fotografer, pantau pesanan, dan tinjau pencairan DEMO." tabs={tabs} active={tab}>
      {tab === "ringkasan" && (o ? <Overview o={o} /> : <p className="muted">Memuat...</p>)}
      {tab === "fotografer" && <Photographers />}
      {tab === "pesanan" && <Bookings />}
      {tab === "payout" && <Payouts />}
      {tab === "pengguna" && <Users />}
      {tab === "audit" && <Audit />}
    </DashShell>
  );
}
