import { useCallback, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Search, MessageCircle, Heart, ChevronRight, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { DashShell, Stat } from "@/components/dashboard/DashShell";
import { BookingList, StatusFilter } from "@/components/dashboard/BookingRow";
import { Inbox } from "@/components/chat/Inbox";
import { PhotographerCard } from "@/components/marketplace/Cards";

const KEYS = { "/customer/pesanan": "orders", "/customer/chat": "chat", "/customer/favorit": "favorites" };

function Overview({ data, reload }) {
  return (
    <>
      <div className="stats">
        <Stat label="Pesanan aktif" value={data.active_bookings} testid="stat-active-bookings" />
        <Stat label="Favorit tersimpan" value={data.favorites} testid="stat-favorites" />
        <Stat label="Pesan belum dibaca" value={data.unread} testid="stat-unread" />
      </div>
      <div className="dashboard-content">
        <div>
          <div className="section-heading"><h2>Pesanan terbaru</h2><Link to="/customer/pesanan" className="text-link" data-testid="dashboard-orders-link">Lihat semua <ArrowRight size={16} /></Link></div>
          <BookingList items={data.bookings} role="customer" onChange={reload} empty="Belum ada pesanan. Temukan fotografer untuk momen berikutnya." />
        </div>
        <aside className="dash-side">
          <p className="eyebrow">TAUTAN CEPAT</p>
          <Link to="/fotografer" data-testid="quick-search"><Search size={17} /> Cari fotografer <ChevronRight size={15} /></Link>
          <Link to="/customer/chat" data-testid="quick-chat"><MessageCircle size={17} /> Buka chat <ChevronRight size={15} /></Link>
          <Link to="/customer/favorit" data-testid="quick-favorites"><Heart size={17} /> Fotografer favorit <ChevronRight size={15} /></Link>
        </aside>
      </div>
    </>
  );
}

function Orders() {
  const [status, setStatus] = useState("");
  const [items, setItems] = useState(null);
  const load = useCallback(() => api.get(`/bookings?status=${status}`).then(setItems).catch(() => setItems([])), [status]);
  useEffect(() => { load(); }, [load]);
  return <><StatusFilter value={status} onChange={setStatus} /><BookingList items={items} role="customer" onChange={load} /></>;
}

function Favorites() {
  const { favIds } = useAuth();
  const [items, setItems] = useState(null);
  useEffect(() => { api.get("/favorites").then(setItems).catch(() => setItems([])); }, [favIds]);
  if (!items) return <p className="muted">Memuat favorit...</p>;
  if (!items.length) return <div className="empty" data-testid="favorites-empty"><p>Belum ada fotografer favorit.</p><Link to="/fotografer" className="olive-btn" data-testid="favorites-find">Cari fotografer</Link></div>;
  return <div className="results grid-results" data-testid="favorites-list">{items.map((p) => <PhotographerCard key={p.photographer_id} p={p} />)}</div>;
}

export default function CustomerDashboard() {
  const { user } = useAuth();
  const key = KEYS[useLocation().pathname] || "overview";
  const [data, setData] = useState(null);
  const reload = useCallback(() => api.get("/dashboard/summary").then(setData).catch(() => {}), []);
  useEffect(() => { reload(); }, [reload, key]);
  const tabs = [
    { key: "overview", to: "/customer/dashboard", label: "Ringkasan" },
    { key: "orders", to: "/customer/pesanan", label: "Pesanan", badge: data?.active_bookings },
    { key: "chat", to: "/customer/chat", label: "Chat", badge: data?.unread },
    { key: "favorites", to: "/customer/favorit", label: "Favorit" },
  ];
  return (
    <DashShell eyebrow="RUANG KAMU" title={`Halo, ${user.name?.split(" ")[0] || "kamu"}.`} subtitle="Kelola pesanan, percakapan, dan fotografer favoritmu." tabs={tabs} active={key}>
      {key === "overview" && (data ? <Overview data={data} reload={reload} /> : <p className="muted">Memuat...</p>)}
      {key === "orders" && <Orders />}
      {key === "chat" && <Inbox role="customer" onRead={reload} />}
      {key === "favorites" && <Favorites />}
    </DashShell>
  );
}
