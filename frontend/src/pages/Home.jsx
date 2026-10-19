import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Search, ArrowRight, CheckCircle2, MapPin } from "lucide-react";
import { api } from "@/lib/api";
import { CATEGORIES } from "@/lib/data";
import { Header, Footer } from "@/components/layout/Header";
import { PhotographerCard, ServiceCard } from "@/components/marketplace/Cards";

const STEPS = [["01", "Cari & bandingkan", "Filter berdasarkan kategori, tanggal, lokasi, dan anggaran."], ["02", "Chat fotografer", "Tanyakan detail paket dan kebutuhan khususmu."], ["03", "Pilih jadwal", "Kalender menunjukkan tanggal yang masih tersedia."], ["04", "Pesan dengan tenang", "Semua detail pesanan tercatat rapi di satu tempat."]];

function SearchPanel() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  return (
    <form className="search-panel" onSubmit={(e) => { e.preventDefault(); nav(`/fotografer?search=${encodeURIComponent(q)}`); }}>
      <label><span>Kebutuhan fotografi</span><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Contoh: wedding" data-testid="hero-search-input" /></label>
      <label><span>Tanggal</span><input type="date" data-testid="hero-date-input" /></label>
      <label><span>Lokasi</span><div className="select-like"><MapPin size={15} /> Makassar</div></label>
      <button className="olive-btn" data-testid="hero-search-button"><Search size={17} /> Cari Fotografer</button>
    </form>
  );
}

function CategoryStrip() {
  return (
    <section className="section" id="kategori">
      <div className="section-heading"><div><p className="eyebrow">PILIH SESUAI MOMENMU</p><h2>Empat cara untuk bercerita.</h2></div><Link to="/fotografer" className="text-link" data-testid="view-all-photographers">Lihat semua fotografer <ArrowRight size={16} /></Link></div>
      <div className="category-grid">
        {CATEGORIES.map((c) => (
          <Link to={`/fotografer?category=${c.name}`} className="category-card" key={c.name} data-testid={`category-${c.name.toLowerCase()}`}>
            <img src={c.image} alt={c.name} /><div><h3>{c.name}</h3><p>{c.desc}</p><span>Jelajahi <ArrowRight size={14} /></span></div>
          </Link>
        ))}
      </div>
    </section>
  );
}

export default function Home() {
  const [people, setPeople] = useState([]);
  const [services, setServices] = useState([]);
  useEffect(() => { Promise.all([api.get("/photographers"), api.get("/services")]).then(([p, s]) => { setPeople(p); setServices(s); }).catch(() => {}); }, []);
  return (
    <>
      <Header />
      <main>
        <section className="hero">
          <div className="hero-image" />
          <div className="hero-content">
            <p className="eyebrow light">MARKETPLACE FOTOGRAFI MAKASSAR</p>
            <h1>Temukan fotografer yang tepat untuk <em>setiap momen.</em></h1>
            <p className="hero-lead">Jelajahi portofolio, bandingkan paket layanan, periksa jadwal, dan pesan fotografer freelance sesuai kebutuhanmu.</p>
            <SearchPanel />
            <div className="hero-note"><span><CheckCircle2 size={15} /> Fotografer terverifikasi</span><span><CheckCircle2 size={15} /> Harga transparan</span><span><CheckCircle2 size={15} /> Jadwal terkoordinasi</span></div>
          </div>
        </section>
        <CategoryStrip />
        <section className="section cream-band">
          <div className="section-heading"><div><p className="eyebrow">PILIHAN EDITOR</p><h2>Fotografer pilihan di Makassar.</h2></div><Link to="/fotografer" className="text-link" data-testid="featured-see-more">Lihat semua <ArrowRight size={16} /></Link></div>
          <div className="photographer-grid">{people.slice(0, 4).map((p) => <PhotographerCard key={p.photographer_id} p={p} featured />)}</div>
        </section>
        <section className="section">
          <div className="section-heading"><div><p className="eyebrow">KATALOG PAKET</p><h2>Layanan untuk dibandingkan.</h2></div><Link to="/fotografer" className="text-link" data-testid="services-see-more">Jelajahi layanan <ArrowRight size={16} /></Link></div>
          <div className="services-row">{services.slice(0, 4).map((s) => <ServiceCard s={s} key={s.service_id} />)}</div>
        </section>
        <section className="steps section" id="cara-kerja">
          <div><p className="eyebrow">SESEDERHANA ITU</p><h2>Dari ide menjadi momen.</h2></div>
          <div className="step-grid">{STEPS.map((x) => <div className="step" key={x[0]}><b>{x[0]}</b><h3>{x[1]}</h3><p>{x[2]}</p></div>)}</div>
        </section>
        <section className="join-band">
          <div><p className="eyebrow light">UNTUK FOTOGRAFER MAKASSAR</p><h2>Karya baik pantas ditemukan.</h2><p>Tampilkan portofolio, kelola paket, jadwal, dan pesananmu dalam satu ruang.</p></div>
          <Link to="/untuk-fotografer" className="white-btn" data-testid="join-photographer-cta">Bergabung sebagai fotografer <ArrowRight size={16} /></Link>
        </section>
      </main>
      <Footer />
    </>
  );
}
