import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Heart, MessageCircle, ArrowRight, MapPin, Clock3, ShieldCheck } from "lucide-react";
import { api, money, mediaUrl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Header, Footer } from "@/components/layout/Header";
import { ServiceCard } from "@/components/marketplace/Cards";
import { ChatModal } from "@/components/chat/ChatModal";
import { BookingModal } from "@/components/booking/BookingModal";
import { AvailabilityCalendar } from "@/components/booking/AvailabilityCalendar";

const TABS = [["portfolio", "Portofolio"], ["services", "Layanan & Paket"], ["about", "Tentang"], ["schedule", "Jadwal"], ["reviews", "Ulasan"]];

function Reviews({ slug }) {
  const [items, setItems] = useState(null);
  useEffect(() => { api.get(`/photographers/${slug}/reviews`).then(setItems).catch(() => setItems([])); }, [slug]);
  if (!items) return <p className="muted">Memuat ulasan...</p>;
  if (!items.length) return <div className="empty" data-testid="reviews-empty"><p>Belum ada ulasan dari pesanan yang selesai.</p></div>;
  return <div className="review-list" data-testid="reviews-list">{items.map((r) => <div className="mini-row tall" key={r.review_id}><span><b>{"★".repeat(r.rating)} · {r.customer_name}</b><small>{r.service}</small>{r.comment && <small>“{r.comment}”</small>}</span></div>)}</div>;
}

function TabContent({ tab, p, onBook }) {
  const [day, setDay] = useState("");
  if (tab === "portfolio") {
    const items = p.portfolio?.length ? p.portfolio : p.gallery.map((url, i) => ({ item_id: String(i), url }));
    if (!items.length) return <div className="empty"><p>Fotografer belum mengunggah portofolio.</p></div>;
    return <div className="portfolio-grid" data-testid="portfolio-grid">{items.map((it) => <figure key={it.item_id}><img src={mediaUrl(it.url)} alt={it.title || "Portofolio"} loading="lazy" />{it.title && <figcaption><b>{it.title}</b>{it.description && <span>{it.description}</span>}</figcaption>}</figure>)}</div>;
  }
  if (tab === "reviews") return <Reviews slug={p.slug} />;
  if (tab === "services") return <div className="services-row two">{p.services.map((s) => <ServiceCard key={s.service_id} s={{ ...s, image: p.gallery[0] }} onClick={onBook} />)}</div>;
  if (tab === "schedule") return <div className="schedule-tab"><p className="muted">Tanggal bertanda menunjukkan jadwal yang sudah terisi. Pilih tanggal untuk melihat jam yang terpakai.</p><AvailabilityCalendar slug={p.slug} value={day} onChange={setDay} /></div>;
  return <div className="about-block"><p className="eyebrow">TENTANG FOTOGRAFER</p><h2>Visual yang terasa personal.</h2><p>{p.bio} Melayani {p.service_area}. Durasi minimum {p.min_duration} jam.</p></div>;
}

export default function ProfilePage() {
  const { slug } = useParams();
  const { favIds, toggleFavorite } = useAuth();
  const [p, setP] = useState(null);
  const [error, setError] = useState(false);
  const [slide, setSlide] = useState(0);
  const [tab, setTab] = useState("portfolio");
  const [modal, setModal] = useState("");
  useEffect(() => { setP(null); api.get(`/photographers/${slug}`).then(setP).catch(() => setError(true)); }, [slug]);

  if (error) return <><Header /><div className="loading"><div className="empty"><p>Fotografer tidak ditemukan.</p><Link to="/fotografer" className="olive-btn" data-testid="profile-back-search">Kembali mencari</Link></div></div></>;
  if (!p) return <div className="loading">Memuat profil...</div>;
  const fav = favIds.has(p.photographer_id);
  const gallery = p.gallery.length ? p.gallery : [p.profile_image].filter(Boolean);

  return (
    <>
      <Header />
      <main className="profile-page">
        <div className="profile-top">
          <div className="profile-identity">
            <img src={mediaUrl(p.profile_image || gallery[0])} alt={p.name} />
            <div>
              <span className="eyebrow">{p.category} · MAKASSAR {p.demo && "· DEMO"}</span>
              <h1 data-testid="profile-name">{p.name}</h1>
              <p className="handle">{p.username} · {p.rating ? <span className="rating">★ {p.rating.toFixed(1)} ({p.reviews} ulasan{p.rating_source === "verified" ? "" : " demo"})</span> : <span>Belum ada ulasan</span>}</p>
              <p>{p.bio}</p>
              <div className="profile-badges">{p.verified && <span><ShieldCheck size={15} /> Terverifikasi admin</span>}<span><MapPin size={15} /> Melayani {p.service_area}</span></div>
            </div>
          </div>
          <div className="profile-actions">
            <button className="save-profile" onClick={() => toggleFavorite(p.photographer_id)} data-testid="profile-save"><Heart size={17} fill={fav ? "currentColor" : "none"} /> {fav ? "Tersimpan" : "Simpan"}</button>
            <button className="olive-btn" onClick={() => setModal("chat")} data-testid="profile-chat"><MessageCircle size={17} /> Chat fotografer</button>
          </div>
        </div>
        {gallery.length > 0 && (
          <div className="gallery-wrap">
            <div className="gallery-main">
              <img src={mediaUrl(gallery[slide % gallery.length])} alt={`Portofolio ${p.name}`} data-testid="profile-gallery-image" />
              <button className="gallery-prev" onClick={() => setSlide((slide + gallery.length - 1) % gallery.length)} data-testid="gallery-previous">‹</button>
              <button className="gallery-next" onClick={() => setSlide((slide + 1) % gallery.length)} data-testid="gallery-next">›</button>
            </div>
            <div className="gallery-side">{gallery.slice(1, 3).map((x, i) => <img src={mediaUrl(x)} key={x + i} alt="Portofolio" onClick={() => setSlide(i + 1)} data-testid={`gallery-thumb-${i}`} />)}</div>
          </div>
        )}
        <div className="profile-lower">
          <div>
            <div className="tab-row">{TABS.map(([k, l]) => <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)} data-testid={`${k}-tab`}>{l}</button>)}</div>
            <TabContent tab={tab} p={{ ...p, gallery }} onBook={() => setModal("book")} />
          </div>
          <aside className="booking-box">
            <p className="eyebrow">MULAI DARI</p><h2>{money(p.starting_price)}</h2>
            <p><Clock3 size={15} /> Minimum {p.min_duration} jam · {p.category}</p>
            <button className="olive-btn full" disabled={!p.services.length} onClick={() => setModal("book")} data-testid="book-now-button">Ajukan permintaan <ArrowRight size={16} /></button>
            <button className="outline-btn full" onClick={() => setModal("chat")} data-testid="profile-secondary-chat">Tanya dulu</button>
            <small>Jadwal dicek otomatis oleh sistem. Pembayaran online belum aktif (DEMO) — belum ada tagihan. <Link to="/kebijakan/pembatalan-refund">Kebijakan pesanan</Link></small>
          </aside>
        </div>
      </main>
      {modal === "chat" && <ChatModal p={p} close={() => setModal("")} />}
      {modal === "book" && <BookingModal p={p} close={() => setModal("")} />}
      <Footer />
    </>
  );
}
