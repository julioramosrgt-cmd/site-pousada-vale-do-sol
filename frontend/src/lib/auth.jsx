import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/apiClient";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem("pousada_token");
    if (!t) { setLoading(false); return; }
    api.get("/auth/me").then((r) => setUser(r.data)).catch(() => localStorage.removeItem("pousada_token")).finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const r = await api.post("/auth/login", { email, password });
    localStorage.setItem("pousada_token", r.data.access_token);
    setUser(r.data.user);
    return r.data.user;
  };

  const logout = () => {
    localStorage.removeItem("pousada_token");
    setUser(null);
    window.location.href = "/admin/login";
  };

  return <AuthCtx.Provider value={{ user, loading, login, logout }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
