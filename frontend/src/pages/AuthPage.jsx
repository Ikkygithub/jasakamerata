import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { api, dashboardPath } from "@/lib/api";
import { CATEGORIES } from "@/lib/data";
import { useAuth } from "@/context/AuthContext";
import { Header, Footer } from "@/components/layout/Header";

const googleLogin = (path) => {
  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(window.location.origin + path)}`;
};

function GoogleButton({ path = "/customer/dashboard", label = "Lanjutkan dengan Google" }) {
  return <button type="button" className="google-btn" onClick={() => googleLogin(path)} data-testid="google-login-button"><span>G</span> {label}</button>;
}

function OnboardForm() {
  const { user, refresh } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ name: user.name || "", category: "Wedding", agree_policy: false });
  const [sending, setSending] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setSending(true);
    try {
      await api.post("/photographer/onboard", form);
      await refresh();
      toast("Akun fotografer dibuat. Lengkapi profilmu di Studio.");
      nav("/studio");
    } catch (err) { toast(err.message); } finally { setSending(false); }
  };
  return (
    <form onSubmit={submit} data-testid="onboard-form">
      <p className="muted">Masuk sebagai <b>{user.email}</b>. Rekening bank, portofolio, dan verifikasi profesional dilengkapi nanti di Studio.</p>
      <label>Nama profesional<input required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="photographer-name-input" /></label>
      <label>Kategori utama<select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} data-testid="photographer-category-select">{CATEGORIES.map((c) => <option key={c.name}>{c.name}</option>)}</select></label>
      <label className="check"><input type="checkbox" checked={form.agree_policy} onChange={(e) => setForm({ ...form, agree_policy: e.target.checked })} data-testid="photographer-agree-checkbox" /> Saya menyetujui <Link to="/kebijakan/syarat-ketentuan" target="_blank">syarat</Link>, <Link to="/kebijakan/pembayaran-komisi" target="_blank">komisi 5%</Link>, dan <Link to="/kebijakan/penarikan-saldo" target="_blank">kebijakan penarikan</Link>.</label>
      <button className="olive-btn full" disabled={sending} data-testid="photographer-register-submit">{sending ? "Membuat akun..." : "Buat akun fotografer"} <ArrowRight size={16} /></button>
    </form>
  );
}

function RegisterBody() {
  const { user } = useAuth();
  if (user === undefined) return <p className="muted">Memeriksa sesi...</p>;
  if (!user) return <><p className="muted">Langkah 1: masuk dengan akun Google yang akan dipakai sebagai akun fotografer.</p><GoogleButton path="/daftar" label="Daftar dengan Google" /></>;
  if ((user.role || "customer") !== "customer") return <Navigate to={dashboardPath(user.role)} replace />;
  return <OnboardForm />;
}

export default function AuthPage({ register = false }) {
  const { user } = useAuth();
  const cancelled = new URLSearchParams(useLocation().search).get("batal");
  if (user && !register) return <Navigate to={dashboardPath(user.role)} replace />;
  return (
    <>
      <Header />
      <main className="auth-page">
        <div className="auth-art"><p className="eyebrow light">JASAKAMERATA · MAKASSAR</p><h1>Karya baik<br /><em>bertemu momen.</em></h1></div>
        <div className="auth-form">
          <p className="eyebrow">{register ? "DAFTAR SEBAGAI FOTOGRAFER" : "SELAMAT DATANG KEMBALI"}</p>
          <h2>{register ? "Mulai tampilkan karyamu." : "Masuk ke Jasakamerata."}</h2>
          {cancelled && <p className="notice" data-testid="login-cancelled">Login dibatalkan. Silakan coba lagi.</p>}
          {register ? <RegisterBody /> : <><p className="muted">Customer, fotografer, dan admin masuk dengan akun Google.</p><GoogleButton /><div className="divider"><span>atau</span></div><Link to="/daftar" className="outline-btn full" data-testid="register-link">Daftar sebagai fotografer</Link></>}
          <p className="form-foot">Dengan melanjutkan, kamu menyetujui <Link to="/kebijakan/syarat-ketentuan">syarat</Link> dan <Link to="/kebijakan/privasi">kebijakan privasi</Link> Jasakamerata.</p>
        </div>
      </main>
      <Footer />
    </>
  );
}

export function AuthCallback() {
  const once = useRef(false);
  const nav = useNavigate();
  const location = useLocation();
  const { refresh } = useAuth();
  const [error, setError] = useState("");
  useEffect(() => {
    if (once.current) return;
    once.current = true;
    const id = new URLSearchParams(location.hash.slice(1)).get("session_id");
    api.post("/auth/session", { session_id: id })
      .then(async () => {
        const u = await refresh();
        const toRegister = location.pathname === "/daftar" && (u?.role || "customer") === "customer";
        nav(toRegister ? "/daftar" : dashboardPath(u?.role), { replace: true });
      })
      .catch((e) => setError(e.message));
  }, [nav, location.hash, location.pathname, refresh]);
  if (error) return <div className="loading"><div className="empty"><p data-testid="oauth-error">{error}</p><Link className="olive-btn" to="/masuk" data-testid="oauth-retry">Kembali ke masuk</Link></div></div>;
  return <div className="loading">Menyiapkan ruangmu...</div>;
}
