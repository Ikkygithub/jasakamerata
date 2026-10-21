import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Search, Menu, LogOut, ChevronDown, User, ClipboardList, MessageCircle, Heart } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useAuth } from "@/context/AuthContext";
import { dashboardPath } from "@/lib/api";

function CustomerMenu({ user, onLogout }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="user-trigger" data-testid="customer-menu-trigger">
        {user.picture ? <img src={user.picture} alt="" /> : <span className="avatar">{user.name?.[0]}</span>}
        <span className="user-name">{user.name?.split(" ")[0]}</span><ChevronDown size={14} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="user-menu">
        {[["/customer/dashboard", "Profil Saya", User, "profile"], ["/customer/pesanan", "Pesanan Saya", ClipboardList, "orders"], ["/customer/chat", "Chat", MessageCircle, "chat"], ["/customer/favorit", "Favorit", Heart, "favorites"]].map(([to, label, Icon, k]) => (
          <DropdownMenuItem key={to} asChild><Link to={to} data-testid={`customer-menu-${k}`}><Icon size={15} /> {label}</Link></DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onLogout} data-testid="customer-menu-logout"><LogOut size={15} /> Keluar</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function UserActions() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const out = async () => { await logout(); nav("/"); };
  if (!user) {
    return (
      <>
        <Link to="/masuk" className="login-link" data-testid="header-login">Masuk</Link>
        <Link to="/daftar" className="dark-btn compact" data-testid="header-register">Daftar</Link>
      </>
    );
  }
  if ((user.role || "customer") === "customer") return <CustomerMenu user={user} onLogout={out} />;
  return (
    <>
      <Link to={dashboardPath(user.role)} className="dark-btn compact" data-testid="header-dashboard">{user.role === "admin" ? "Admin" : "Studio"}</Link>
      <button className="icon-btn" title="Keluar" onClick={out} data-testid="logout-button"><LogOut size={18} /></button>
    </>
  );
}

export function Header() {
  const [open, setOpen] = useState(false);
  return (
    <header className="site-header">
      <Link to="/" className="brand" data-testid="brand-home"><span className="brand-mark">J</span><span>Jasakamerata<small>MAKASSAR</small></span></Link>
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
          <Link to="/" className="brand footer-brand"><span className="brand-mark">J</span><span>Jasakamerata<small>MAKASSAR</small></span></Link>
          <p>Temukan fotografer yang tepat<br />untuk setiap momen.</p>
        </div>
        <div><b>Jelajahi</b><Link to="/fotografer">Cari fotografer</Link><a href="/#cara-kerja">Cara kerja</a><Link to="/untuk-fotografer">Untuk fotografer</Link></div>
        <div><b>Bantuan</b><Link to="/kebijakan/syarat-ketentuan">Syarat & ketentuan</Link><Link to="/kebijakan/privasi">Kebijakan privasi</Link><Link to="/kebijakan/pembayaran-komisi">Pembayaran & komisi</Link><Link to="/kebijakan/pembatalan-refund">Pembatalan & refund</Link><Link to="/kebijakan/penarikan-saldo">Penarikan saldo</Link><a href="mailto:halo@jasakamerata.com">Hubungi kami</a></div>
      </div>
      <div className="footer-bottom">© 2026 Jasakamerata · Dibuat untuk Makassar · Komisi platform 5% · Data bertanda DEMO adalah fiktif</div>
    </footer>
  );
}
