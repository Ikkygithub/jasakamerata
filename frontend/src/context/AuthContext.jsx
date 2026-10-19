import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined);
  const [favIds, setFavIds] = useState(new Set());

  const refresh = useCallback(async () => {
    try {
      const u = await api.get("/auth/me");
      setUser(u);
      const favs = await api.get("/favorites");
      setFavIds(new Set(favs.map((p) => p.photographer_id)));
      return u;
    } catch {
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    if (window.location.hash?.includes("session_id=")) return;
    refresh();
  }, [refresh]);

  const logout = async () => {
    await api.post("/auth/logout").catch(() => {});
    setUser(null);
    setFavIds(new Set());
  };

  const toggleFavorite = async (pid) => {
    if (!user) {
      toast("Masuk terlebih dahulu untuk menyimpan favorit");
      return;
    }
    const next = new Set(favIds);
    try {
      if (favIds.has(pid)) {
        await api.del(`/favorites/${pid}`);
        next.delete(pid);
        toast("Dihapus dari favorit");
      } else {
        await api.post("/favorites", { photographer_id: pid });
        next.add(pid);
        toast("Fotografer disimpan ke favorit");
      }
      setFavIds(next);
    } catch (e) {
      toast(e.message);
    }
  };

  return <AuthCtx.Provider value={{ user, setUser, refresh, logout, favIds, toggleFavorite }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
