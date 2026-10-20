import { Link, NavLink, Outlet, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { LayoutDashboard, Users2, CalendarRange, LogOut, Fingerprint, Palmtree, Wallet } from "lucide-react";

const TABS = [
  { to: "/rh", label: "Dashboard", id: "dashboard", icon: LayoutDashboard, end: true },
  { to: "/rh/colaboradores", label: "Colaboradores", id: "colaboradores", icon: Users2 },
  { to: "/rh/escala", label: "Escala 5×2", id: "escala", icon: CalendarRange },
  { to: "/rh/ponto", label: "Ponto", id: "ponto", icon: Fingerprint },
  { to: "/rh/ferias", label: "Férias", id: "ferias", icon: Palmtree },
  { to: "/rh/folha", label: "Folha", id: "folha", icon: Wallet },
];

export default function RhLayout() {
  const { user, loading, logout } = useAuth();
  const loc = useLocation();
  if (loading) return <div className="p-10 text-stone-500">Carregando…</div>;
  if (!user) return <Navigate to="/rh/login" replace state={{ from: loc }} />;

  return (
    <div className="min-h-screen bg-stone-50 md:flex" data-testid="rh-layout">
      <aside className="md:w-60 shrink-0 bg-white border-b md:border-b-0 md:border-r border-stone-200 flex md:flex-col">
        <div className="px-5 py-4 md:py-5 md:border-b border-stone-200 hidden md:block">
          <Link to="/rh" className="font-serif text-lg text-stone-900">Gestão RH</Link>
          <div className="text-xs text-stone-500 mt-0.5">Pousada Vale do Sol</div>
        </div>
        <nav className="flex-1 p-2 md:p-3 flex md:flex-col gap-1 overflow-x-auto">
          {TABS.map((t) => (
            <NavLink key={t.to} to={t.to} end={t.end} className={({ isActive }) =>
              `flex items-center gap-2 px-3 py-2 rounded-lg text-sm whitespace-nowrap transition-colors ${isActive ? "bg-[color:var(--pousada-palm)]/10 text-[color:var(--pousada-palm)] font-medium" : "text-stone-700 hover:bg-stone-100"}`}
              data-testid={`rh-nav-${t.id}`}>
              <t.icon className="w-4 h-4" />{t.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-2 md:p-3 md:border-t border-stone-200 flex md:block items-center">
          <div className="text-xs text-stone-500 mb-2 truncate hidden md:block">{user.email}</div>
          <button onClick={logout} className="md:w-full inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-stone-600 hover:bg-stone-100" data-testid="rh-logout">
            <LogOut className="w-4 h-4" /><span className="hidden md:inline">Sair</span>
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0 p-4 md:p-6 overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  );
}
