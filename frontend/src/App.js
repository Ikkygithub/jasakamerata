import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import "@/App.css";
import "@/dashboard.css";
import { AuthProvider } from "@/context/AuthContext";
import { RoleGuard } from "@/components/dashboard/DashShell";
import Home from "@/pages/Home";
import SearchPage from "@/pages/SearchPage";
import ProfilePage from "@/pages/ProfilePage";
import AuthPage, { AuthCallback } from "@/pages/AuthPage";
import CustomerDashboard from "@/pages/customer/CustomerDashboard";
import PhotographerDashboard from "@/pages/photographer/PhotographerDashboard";
import AdminDashboard from "@/pages/admin/AdminDashboard";

const guard = (role, el) => <RoleGuard role={role}>{el}</RoleGuard>;

function AppRouter() {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/fotografer" element={<SearchPage />} />
      <Route path="/fotografer/:slug" element={<ProfilePage />} />
      <Route path="/masuk" element={<AuthPage />} />
      <Route path="/daftar" element={<AuthPage register />} />
      <Route path="/untuk-fotografer" element={<AuthPage register />} />
      {["/customer/dashboard", "/customer/pesanan", "/customer/chat", "/customer/favorit"].map((p) => <Route key={p} path={p} element={guard("customer", <CustomerDashboard />)} />)}
      <Route path="/studio" element={guard("photographer", <PhotographerDashboard />)} />
      <Route path="/studio/:tab" element={guard("photographer", <PhotographerDashboard />)} />
      <Route path="/admin" element={guard("admin", <AdminDashboard />)} />
      <Route path="/admin/:tab" element={guard("admin", <AdminDashboard />)} />
      <Route path="*" element={<Home />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter><AppRouter /></BrowserRouter>
      <Toaster position="bottom-right" />
    </AuthProvider>
  );
}
