import { useEffect, useState } from "react";
import { api } from "@/lib/apiClient";
import { Link } from "react-router-dom";
import { BedDouble, ClipboardList, Wallet, TrendingUp } from "lucide-react";

const StatCard = ({ icon: Icon, label, value, color }) => (
  <div className="rounded-2xl bg-white border border-stone-200/70 p-5 shadow-warm">
    <div className="flex items-center justify-between">
      <span className="text-xs uppercase tracking-widest text-stone-500">{label}</span>
      <Icon className="w-5 h-5" style={{ color }} />
    </div>
    <div className="mt-3 font-serif text-3xl">{value}</div>
  </div>
);

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [pending, setPending] = useState([]);
  const [rooms, setRooms] = useState([]);

  useEffect(() => {
    const today = new Date();
    const from = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10);
    const to = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().slice(0, 10);
    api.get(`/finance/summary?from_date=${from}&to_date=${to}`).then((r) => setSummary(r.data));
    api.get(`/reservations?status=pending`).then((r) => setPending(r.data));
    api.get(`/rooms`).then((r) => setRooms(r.data));
  }, []);

  return (
    <div>
      <div className="flex items-end justify-between mb-6">
        <div>
          <span className="text-xs uppercase tracking-widest text-amber-800/70">Bem-vindo</span>
          <h1 className="font-serif text-3xl sm:text-4xl">Visão geral</h1>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={BedDouble} label="Quartos" value={rooms.length} color="#C85A32" />
        <StatCard icon={ClipboardList} label="Pré-reservas" value={pending.length} color="#ED6C02" />
        <StatCard icon={Wallet} label="Receita mês" value={`R$ ${summary?.income?.toFixed(0) ?? "0"}`} color="#2D5A43" />
        <StatCard icon={TrendingUp} label="Ocupação" value={`${summary?.occupancy ?? 0}%`} color="#D99B26" />
      </div>

      <div className="grid lg:grid-cols-2 gap-6 mt-8">
        <div className="rounded-2xl bg-white border border-stone-200/70 p-6 shadow-warm">
          <div className="flex items-center justify-between">
            <h3 className="font-serif text-xl">Pré-reservas pendentes</h3>
            <Link to="/admin/reservations" className="text-sm text-[color:var(--pousada-terracotta)]">Ver todas</Link>
          </div>
          {pending.length === 0 ? <p className="text-stone-500 mt-4">Nenhuma pré-reserva pendente.</p> : (
            <ul className="mt-4 divide-y divide-stone-100">
              {pending.slice(0, 6).map((r) => (
                <li key={r.id} className="py-3 flex items-center gap-3" data-testid={`dashboard-pending-${r.id}`}>
                  <span className="status-dot status-pending" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{r.guest_name}</div>
                    <div className="text-xs text-stone-500">{r.checkin_date} → {r.checkout_date}</div>
                  </div>
                  <span className="text-xs text-stone-500">{r.source}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-2xl bg-white border border-stone-200/70 p-6 shadow-warm">
          <h3 className="font-serif text-xl">Resumo financeiro do mês</h3>
          <div className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between"><span className="text-stone-500">Receitas</span><span className="font-mono text-emerald-700">R$ {summary?.income?.toFixed(2) ?? "0.00"}</span></div>
            <div className="flex justify-between"><span className="text-stone-500">Despesas</span><span className="font-mono text-red-700">R$ {summary?.expense?.toFixed(2) ?? "0.00"}</span></div>
            <div className="flex justify-between border-t border-stone-100 pt-3"><span className="font-medium">Lucro líquido</span><span className="font-mono font-semibold">R$ {summary?.profit?.toFixed(2) ?? "0.00"}</span></div>
            <div className="flex justify-between"><span className="text-stone-500">Noites reservadas</span><span className="font-mono">{summary?.booked_nights ?? 0} / {summary?.capacity ?? 0}</span></div>
          </div>
          <Link to="/admin/finance" className="btn-terra inline-flex mt-5 rounded-xl px-4 py-2 text-sm">Ver financeiro</Link>
        </div>
      </div>
    </div>
  );
}
