import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ExternalLink } from "lucide-react";
import { api, money } from "@/lib/api";
import { DashShell, Stat } from "@/components/dashboard/DashShell";
import { BookingList, StatusFilter } from "@/components/dashboard/BookingRow";
import { Inbox } from "@/components/chat/Inbox";
import { CalendarTab, ServicesTab, PortfolioTab, ProfileTab, WalletTab } from "./StudioTabs";

function Orders({ onChange }) {
  const [status, setStatus] = useState("");
  const [items, setItems] = useState(null);
  const load = useCallback(() => api.get(`/bookings?status=${status}`).then(setItems).catch(() => setItems([])), [status]);
  useEffect(() => { load(); }, [load]);
  return <><StatusFilter value={status} onChange={setStatus} /><BookingList items={items} role="photographer" onChange={() => { load(); onChange(); }} /></>;
}

function Overview({ data }) {
  const c = data.counts;
  return (
    <>
      <div className="stats four">
        <Stat label="Permintaan baru" value={c.pending} testid="stat-pending" />
        <Stat label="Jadwal diterima" value={c.accepted} testid="stat-accepted" />
        <Stat label="Selesai" value={c.completed} testid="stat-completed" />
        <Stat label="Saldo DEMO" value={money(data.wallet.available)} testid="stat-wallet" />
      </div>
      <div className="dash-cards">
        <Link to="/studio/pesanan" className="dash-card" data-testid="overview-orders">Tinjau {c.pending} permintaan masuk →</Link>
        <Link to="/studio/kalender" className="dash-card" data-testid="overview-calendar">Atur kalender ketersediaan →</Link>
        <Link to="/studio/chat" className="dash-card" data-testid="overview-chat">{data.unread} pesan belum dibaca →</Link>
      </div>
    </>
  );
}

export default function PhotographerDashboard() {
  const { tab = "ringkasan" } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const reload = useCallback(() => api.get("/photographer/me").then(setData).catch((e) => setErr(e.message)), []);
  useEffect(() => { reload(); }, [reload, tab]);
  const tabs = [["ringkasan", "Ringkasan"], ["pesanan", "Pesanan", data?.counts.pending], ["kalender", "Kalender"], ["layanan", "Layanan"], ["portofolio", "Portofolio"], ["chat", "Chat", data?.unread], ["wallet", "Wallet"], ["profil", "Profil"]].map(([key, label, badge]) => ({ key, label, badge, to: key === "ringkasan" ? "/studio" : `/studio/${key}` }));
  if (err) return <DashShell eyebrow="STUDIO FOTOGRAFER" title="Studio belum siap." tabs={[]}><div className="empty"><p>{err}</p></div></DashShell>;
  if (!data) return <div className="loading">Memuat studio...</div>;
  const p = data.profile;
  const actions = p.listing_status === "approved" ? <Link to={`/fotografer/${p.slug}`} className="outline-btn" data-testid="studio-view-public"><ExternalLink size={15} /> Lihat profil publik</Link> : null;
  return (
    <DashShell eyebrow={`STUDIO FOTOGRAFER · ${p.category.toUpperCase()}`} title={p.name} subtitle="Kelola pesanan, jadwal, layanan, dan portofoliomu." tabs={tabs} active={tab} actions={actions}>
      {p.listing_status !== "approved" && <div className="notice" data-testid="studio-pending-notice"><AlertTriangle size={16} /> Profil {p.listing_status === "rejected" ? "ditolak" : "menunggu verifikasi"} admin — belum tampil di pencarian publik. Lengkapi layanan dan portofolio sambil menunggu.</div>}
      {tab === "ringkasan" && <Overview data={data} />}
      {tab === "pesanan" && <Orders onChange={reload} />}
      {tab === "kalender" && <CalendarTab profile={p} />}
      {tab === "layanan" && <ServicesTab profile={p} reload={reload} />}
      {tab === "portofolio" && <PortfolioTab profile={p} reload={reload} />}
      {tab === "chat" && <Inbox role="photographer" onRead={reload} />}
      {tab === "wallet" && <WalletTab wallet={data.wallet} reload={reload} />}
      {tab === "profil" && <ProfileTab profile={p} reload={reload} />}
    </DashShell>
  );
}
