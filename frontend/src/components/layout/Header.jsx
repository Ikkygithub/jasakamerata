import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Search, Menu, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { dashboardPath } from "@/lib/api";

function UserActions() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  if (!user) {
    return (
      <>
        <Link to="/masuk" className="login-link" data-testid="header-login">Masuk</Link>
        <Link to="/daftar" className="dark-btn compact" data-testid="header-register">Daftar</Link>
      </>
    );
  }
  return (
    <>
      <Link to={dashboardPath(user.role)} className="dark-btn compact" data-testid="header-dashboard">
        {user.role === "admin" ? "Admin" : user.role === "photographer" ? "Studio" : "Ruang Saya"}
      </Link>
      <button className="icon-btn" title="Keluar" onClick={async () => { await logout(); nav("/"); }} data-testid="logout-button"><LogOut size={18} /></button>
    </>
  );
}

export function Header() {
  const [open, setOpen] = useState(false);
  return (
    <header className="site-header">
      <Link to="/" className="brand" data-testid="brand-home"><span className="brand-mark">JK</span><span>Jasa Kamera<small>MAKASSAR</small></span></Link>
      <nav className={open ? "open" : ""} data-testid="main-navigation">
        <Link to="/fotografer" data-testid="nav-photographers">Temukan Fotografer</Link>
        <a href="/#kategori" data-testid="nav-categories">Kategori</a>
        <a href="/#cara-kerja" data-testid="nav-how-it-works">Cara Kerja</a>
        <Link to="/untuk-fotografer" data-testid="nav-for-photographers">Untuk Fotografer</Link>
      </nav>
      <div className="header-actions">
        <Link to="/fotografer" className="icon-btn" title="Cari" data-testid="header-search"><Search size={18} /></Link>
        <UserActions />
        <button className="menu-btn" onClick={() => setOpen(!open)} data-testid="mobile-menu"><Menu size={19} /></button>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer>
      <div className="footer-main">
        <div>
          <Link to="/" className="brand footer-brand"><span className="brand-mark">JK</span><span>Jasa Kamera<small>MAKASSAR</small></span></Link>
          <p>Temukan fotografer yang tepat<br />untuk setiap momen.</p>
        </div>
        <div><b>Jelajahi</b><Link to="/fotografer">Cari fotografer</Link><a href="/#cara-kerja">Cara kerja</a><Link to="/untuk-fotografer">Untuk fotografer</Link></div>
        <div><b>Bantuan</b><Link to="/kebijakan-privasi">Kebijakan privasi</Link><Link to="/syarat-ketentuan">Syarat & ketentuan</Link><a href="mailto:halo@jasakamera.id">Hubungi kami</a></div>
      </div>
      <div className="footer-bottom">© 2026 Jasa Kamera · Dibuat untuk Makassar · Data fotografer bertanda DEMO adalah fiktif</div>
    </footer>
  );
}
