import { NavLink, Outlet, Link } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { LayoutDashboard, CalendarDays, ClipboardList, BedDouble, Image, Cable, MessageSquare, Wallet, KeyRound, LogOut, ExternalLink, Grid3x3, Users } from "lucide-react";

const NAV = [
  { to: "/admin", icon: LayoutDashboard, label: "Visão Geral", end: true, testid: "nav-dashboard" },
  { to: "/admin/calendar", icon: CalendarDays, label: "Calendário", testid: "nav-calendar" },
  { to: "/admin/heatmap", icon: Grid3x3, label: "Ocupação", testid: "nav-heatmap", adminOnly: true },
  { to: "/admin/reservations", icon: ClipboardList, label: "Reservas", testid: "nav-reservations" },
  { to: "/admin/rooms", icon: BedDouble, label: "Quartos", testid: "nav-rooms", adminOnly: true },
  { to: "/admin/settings", icon: Image, label: "Site & Galeria", testid: "nav-settings", adminOnly: true },
  { to: "/admin/ical", icon: Cable, label: "iCal / OTAs", testid: "nav-ical", adminOnly: true },
  { to: "/admin/whatsapp", icon: MessageSquare, label: "WhatsApp", testid: "nav-whatsapp" },
  { to: "/admin/finance", icon: Wallet, label: "Financeiro", testid: "nav-finance", adminOnly: true },
  { to: "/admin/users", icon: Users, label: "Usuários", testid: "nav-users", adminOnly: true },
  { to: "/admin/account", icon: KeyRound, label: "Conta", testid: "nav-account" },
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const items = NAV.filter((it) => !it.adminOnly || user?.role === "admin");
  return (
    <div className="min-h-screen bg-[color:var(--pousada-bg)] flex">
      <aside className="hidden md:flex md:w-64 flex-col border-r border-stone-200 bg-white">
        <div className="p-5 border-b border-stone-100">
          <div className="font-serif text-xl">Painel Pousada</div>
          <div className="text-xs text-stone-500 mt-1 truncate">{user?.email}</div>
          <div className="text-[10px] uppercase tracking-widest mt-1 text-[color:var(--pousada-terracotta)]">{user?.role === "admin" ? "Administrador" : "Recepção"}</div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {items.map((it) => (
            <NavLink key={it.to} to={it.to} end={it.end} data-testid={it.testid}
              className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-xl text-sm ${isActive ? "bg-[color:var(--pousada-terracotta)] text-white" : "text-stone-700 hover:bg-stone-100"}`}>
              <it.icon className="w-4 h-4" /> {it.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-stone-100 space-y-1">
          <Link to="/" target="_blank" className="flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-stone-600 hover:bg-stone-100"><ExternalLink className="w-4 h-4" /> Ver site público</Link>
          <button data-testid="btn-logout" onClick={logout} className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-stone-600 hover:bg-stone-100"><LogOut className="w-4 h-4" /> Sair</button>
        </div>
      </aside>
      <main className="flex-1 min-w-0 p-4 sm:p-8">
        {/* Mobile top nav */}
        <div className="md:hidden mb-4 overflow-x-auto flex gap-2">
          {items.map((it) => (
            <NavLink key={it.to} to={it.to} end={it.end} className={({ isActive }) => `whitespace-nowrap px-3 py-1.5 rounded-full text-xs ${isActive ? "bg-[color:var(--pousada-terracotta)] text-white" : "bg-white border border-stone-200"}`}>
              {it.label}
            </NavLink>
          ))}
        </div>
        <Outlet />
      </main>
    </div>
  );
}
