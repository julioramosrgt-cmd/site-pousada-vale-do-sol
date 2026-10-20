import { createContext, useContext, useEffect, useState } from "react";
import axios from "axios";
import { normalizeDetail } from "@/lib/apiClient";

const COLAB_TOKEN_KEY = "pousada_colab_token";
const BASE = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const colabApi = axios.create({ baseURL: BASE });
colabApi.interceptors.request.use((cfg) => {
  const t = localStorage.getItem(COLAB_TOKEN_KEY);
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});
colabApi.interceptors.response.use((r) => r, (err) => Promise.reject(normalizeDetail(err)));

const Ctx = createContext(null);

export function ColabAuthProvider({ children }) {
  const [employee, setEmployee] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem(COLAB_TOKEN_KEY);
    if (!t) { setLoading(false); return; }
    colabApi.get("/employee/me")
      .then((r) => setEmployee(r.data))
      .catch(() => localStorage.removeItem(COLAB_TOKEN_KEY))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const r = await colabApi.post("/employee/auth/login", { email, password });
    localStorage.setItem(COLAB_TOKEN_KEY, r.data.access_token);
    setEmployee(r.data.employee);
    return r.data.employee;
  };

  const logout = () => {
    localStorage.removeItem(COLAB_TOKEN_KEY);
    setEmployee(null);
    window.location.href = "/colaborador/login";
  };

  return <Ctx.Provider value={{ employee, loading, login, logout }}>{children}</Ctx.Provider>;
}

export const useColabAuth = () => useContext(Ctx);
