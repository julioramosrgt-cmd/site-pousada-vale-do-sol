import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL;
export const API = `${BASE}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("pousada_token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401 && window.location.pathname.startsWith("/admin") && window.location.pathname !== "/admin/login") {
      localStorage.removeItem("pousada_token");
      window.location.href = "/admin/login";
    }
    return Promise.reject(err);
  }
);

export default api;
