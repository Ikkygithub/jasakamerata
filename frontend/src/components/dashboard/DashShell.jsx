import { Link, Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { dashboardPath } from "@/lib/api";
import { Header, Footer } from "@/components/layout/Header";

export function RoleGuard({ role, children }) {
  const { user } = useAuth();
  if (user === undefined) return <div className="loading">Memeriksa akses...</div>;
  if (!user) return <Navigate to="/masuk" replace />;
  if ((user.role || "customer") !== role) return <Navigate to={dashboardPath(user.role)} replace />;
  return children;
}

export function DashShell({ eyebrow, title, subtitle, tabs, active, actions, children }) {
  return (
    <>
      <Header />
      <main className="dashboard">
        <div className="dash-head">
          <div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>
          {actions}
        </div>
        <nav className="dash-tabs" data-testid="dashboard-tabs">
          {tabs.map((t) => <Link key={t.to} to={t.to} className={t.key === active ? "active" : ""} data-testid={`dash-tab-${t.key}`}>{t.label}{t.badge ? <i>{t.badge}</i> : null}</Link>)}
        </nav>
        <section className="dash-body">{children}</section>
      </main>
      <Footer />
    </>
  );
}

export function Stat({ label, value, testid }) {
  return <div><span>{label}</span><b data-testid={testid}>{value}</b></div>;
}
