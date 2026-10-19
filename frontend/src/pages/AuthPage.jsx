import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { api, dashboardPath } from "@/lib/api";
import { CATEGORIES } from "@/lib/data";
import { useAuth } from "@/context/AuthContext";
import { Header, Footer } from "@/components/layout/Header";

const googleLogin = () => {
  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(window.location.origin + "/customer/dashboard")}`;
};

function GoogleButton() {
  return <button type="button" className="google-btn" onClick={googleLogin} data-testid="google-login-button"><span>G</span> Lanjutkan dengan Google</button>;
}

function RegisterForm() {
  const [form, setForm] = useState({ name: "", email: "", category: "Wedding", bank_account: "" });
  const [done, setDone] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    try { setDone(await api.post("/photographers/register", form)); } catch (err) { toast(err.message); }
  };
  if (done) return (
    <div data-testid="register-success">
      <CheckCircle2 size={30} className="ok-icon" />
      <h2>Pendaftaran diterima.</h2>
      <p className="muted">Rekening tersimpan terenkripsi ({done.bank_account_masked}). Profilmu menunggu verifikasi admin. Masuk dengan Google memakai email <b>{form.email}</b> untuk membuka Studio.</p>
      <GoogleButton />
    </div>
  );
  return (
    <form onSubmit={submit}>
      <label>Nama profesional<input required value={form.name} onChange={set("name")} data-testid="photographer-name-input" /></label>
      <label>Email Google<input required type="email" value={form.email} onChange={set("email")} data-testid="photographer-email-input" /></label>
      <label>Kategori utama<select value={form.category} onChange={set("category")} data-testid="photographer-category-select">{CATEGORIES.map((c) => <option key={c.name}>{c.name}</option>)}</select></label>
      <label>Nomor rekening <span className="label-note">terenkripsi & aman</span><input required inputMode="numeric" value={form.bank_account} onChange={set("bank_account")} placeholder="Contoh: 1234567890" data-testid="photographer-bank-input" /></label>
      <button className="olive-btn full" data-testid="photographer-register-submit">Kirim pendaftaran <ArrowRight size={16} /></button>
    </form>
  );
}

export default function AuthPage({ register = false }) {
  const { user } = useAuth();
  if (user && !register) return <Navigate to={dashboardPath(user.role)} replace />;
  return (
    <>
      <Header />
      <main className="auth-page">
        <div className="auth-art"><p className="eyebrow light">JASA KAMERA · MAKASSAR</p><h1>Karya baik<br /><em>bertemu momen.</em></h1></div>
        <div className="auth-form">
          <p className="eyebrow">{register ? "DAFTAR SEBAGAI FOTOGRAFER" : "SELAMAT DATANG KEMBALI"}</p>
          <h2>{register ? "Mulai tampilkan karyamu." : "Masuk ke Jasa Kamera."}</h2>
          <p className="muted">{register ? "Buat profil profesional dan terima pesanan dari Makassar." : "Customer, fotografer, dan admin masuk dengan akun Google."}</p>
          {register ? <RegisterForm /> : <><GoogleButton /><div className="divider"><span>atau</span></div><Link to="/daftar" className="outline-btn full" data-testid="register-link">Daftar sebagai fotografer</Link></>}
          <p className="form-foot">Dengan melanjutkan, kamu menyetujui syarat dan kebijakan Jasa Kamera.</p>
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
      .then(async () => { const u = await refresh(); nav(dashboardPath(u?.role), { replace: true }); })
      .catch((e) => setError(e.message));
  }, [nav, location.hash, refresh]);
  if (error) return <div className="loading"><div className="empty"><p data-testid="oauth-error">{error}</p><Link className="olive-btn" to="/masuk" data-testid="oauth-retry">Kembali ke masuk</Link></div></div>;
  return <div className="loading">Menyiapkan ruangmu...</div>;
}
