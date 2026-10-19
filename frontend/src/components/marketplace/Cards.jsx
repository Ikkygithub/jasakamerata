import { Link } from "react-router-dom";
import { Heart, ArrowRight, ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { money } from "@/lib/api";
import { IMG } from "@/lib/data";

export function PhotographerCard({ p, featured = false }) {
  const { favIds, toggleFavorite } = useAuth();
  const fav = favIds.has(p.photographer_id);
  return (
    <article className={featured ? "photo-card featured" : "photo-card"} data-testid={`photographer-card-${p.photographer_id}`}>
      <div className="photo-cover">
        <img src={p.gallery?.[0] || IMG[0]} alt={p.name} />
        <button className={fav ? "save active" : "save"} onClick={() => toggleFavorite(p.photographer_id)} data-testid={`favorite-${p.photographer_id}`}>
          <Heart size={17} fill={fav ? "currentColor" : "none"} />
        </button>
        {p.verified && <span className="verified"><ShieldCheck size={13} /> Terverifikasi</span>}
        {p.demo && <span className="demo-tag">DEMO</span>}
      </div>
      <div className="photo-info">
        <div className="photo-name">
          <div><h3>{p.name}</h3><p>{p.category} · Makassar</p></div>
          {p.rating ? <span className="rating">★ {p.rating.toFixed(1)}</span> : <span className="rating muted">Baru</span>}
        </div>
        <p className="muted">{p.bio}</p>
        <div className="photo-bottom">
          <span>Mulai <b>{money(p.starting_price)}</b></span>
          <Link to={`/fotografer/${p.slug}`} className="outline-btn" data-testid={`view-profile-${p.photographer_id}`}>Lihat Profil <ArrowRight size={15} /></Link>
        </div>
      </div>
    </article>
  );
}

export function ServiceCard({ s, onClick }) {
  const body = (
    <>
      <img src={s.image || IMG[1]} alt={s.title} />
      <div className="service-copy">
        <p className="eyebrow">{s.category} · {s.pricing_type}</p>
        <h3>{s.title}</h3>
        <p className="muted">{s.duration} · {s.deliverables || "hasil edit berkualitas"}</p>
        <div><span>Mulai</span><b>{money(s.price)}</b></div>
      </div>
    </>
  );
  if (onClick) return <button type="button" className="service-card as-button" onClick={onClick} data-testid={`service-card-${s.service_id}`}>{body}</button>;
  return <Link to={`/fotografer/${s.photographer_slug}`} className="service-card" data-testid={`service-card-${s.service_id}`}>{body}</Link>;
}
