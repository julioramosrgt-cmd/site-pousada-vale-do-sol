import { NavLink, Navigate, Outlet, useLocation } from "react-router-dom";
import { useColabAuth } from "@/lib/colabAuth";
import { LogOut, Home, Fingerprint, Palmtree } from "lucide-react";

const TABS = [
  { to: "/colaborador", label: "Início", id: "inicio", icon: Home, end: true },
  { to: "/colaborador/ponto", label: "Meu ponto", id: "ponto", icon: Fingerprint },
  { to: "/colaborador/ferias", label: "Férias", id: "ferias", icon: Palmtree },
];

export default function ColabLayout() {
  const { employee, loading, logout } = useColabAuth();
  const loc = useLocation();
  if (loading) return <div className="p-10 text-stone-500">Carregando…</div>;
  if (!employee) return <Navigate to="/colaborador/login" replace state={{ from: loc }} />;

  return (
    <div className="min-h-screen bg-stone-50" data-testid="colab-layout">
      <header className="bg-white border-b border-stone-200 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
          <div>
            <div className="font-serif text-lg text-stone-900">Olá, {employee.name.split(" ")[0]}</div>
            <div className="text-xs text-stone-500">{employee.role_title}</div>
          </div>
          <button onClick={logout} className="inline-flex items-center gap-1 text-sm text-stone-600 hover:text-stone-900" data-testid="colab-logout">
            <LogOut className="w-4 h-4" /> Sair
          </button>
        </div>
        <nav className="max-w-4xl mx-auto px-2 flex gap-1 overflow-x-auto">
          {TABS.map((t) => (
            <NavLink key={t.to} to={t.to} end={t.end} data-testid={`colab-nav-${t.id}`}
              className={({ isActive }) => `inline-flex items-center gap-1.5 px-3 py-2 text-sm border-b-2 whitespace-nowrap transition-colors ${isActive ? "border-[color:var(--pousada-terracotta)] text-stone-900 font-medium" : "border-transparent text-stone-500 hover:text-stone-800"}`}>
              <t.icon className="w-4 h-4" />{t.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="max-w-4xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
