import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/apiClient";
import { Users2, Clock, Coffee, AlertTriangle, CalendarCheck, Timer, Palmtree } from "lucide-react";

const Card = ({ icon: Icon, label, value, tone = "palm", testid }) => (
  <div className="rounded-2xl bg-white border border-stone-200 p-4 shadow-sm" data-testid={testid}>
    <div className="flex items-center gap-3">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center bg-[color:var(--pousada-${tone})]/10`}>
        <Icon className={`w-5 h-5 text-[color:var(--pousada-${tone})]`} />
      </div>
      <div>
        <div className="text-2xl font-semibold text-stone-900 leading-none">{value}</div>
        <div className="text-xs text-stone-500 mt-1">{label}</div>
      </div>
    </div>
  </div>
);

const List = ({ title, items, empty, right, testid }) => (
  <div className="rounded-2xl bg-white border border-stone-200 p-4" data-testid={testid}>
    <h2 className="font-medium text-stone-900 mb-3">{title} ({items.length})</h2>
    <ul className="divide-y divide-stone-100">
      {items.length === 0 && <li className="text-sm text-stone-400 py-2">{empty}</li>}
      {items.map((x) => (
        <li key={x.employee.id} className="py-2 flex justify-between text-sm">
          <span className="font-medium">{x.employee.name}</span>
          <span className="font-mono text-xs text-stone-500">{right(x)}</span>
        </li>
      ))}
    </ul>
  </div>
);

const ALERT_CLS = { danger: "text-red-700", warning: "text-amber-900", info: "text-stone-600" };

export default function RhDashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = () => api.get("/hr/dashboard").then((r) => setData(r.data)).catch((e) => setError(e?.response?.data?.detail || "Falha ao carregar"));
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, []);

  if (error) return <div className="text-sm text-red-600" data-testid="rh-dashboard-error">{error}</div>;
  if (!data) return <div className="text-stone-500">Carregando…</div>;

  const t = data.totals;
  const shiftTxt = (x) => (x.shift?.start_time ? `${x.shift.start_time}–${x.shift.end_time}` : "");
  const punchTxt = (x) => (x.last_punch ? `desde ${x.last_punch.time.slice(0, 5)}` : "");
  return (
    <div className="space-y-6" data-testid="rh-dashboard">
      <div>
        <h1 className="font-serif text-2xl text-stone-900">{(() => { const s = new Date(data.today + "T12:00").toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" }); return s.charAt(0).toUpperCase() + s.slice(1); })()}</h1>
        <p className="text-sm text-stone-500">Agora: {data.now} · atualiza a cada minuto pelo ponto eletrônico</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        <Card icon={Users2} label="Ativos" value={t.employees} testid="card-total" />
        <Card icon={Clock} label="Trabalhando agora" value={t.working_now} tone="terracotta" testid="card-working" />
        <Card icon={Timer} label="Em intervalo" value={t.on_break} testid="card-break" />
        <Card icon={AlertTriangle} label="Atrasados" value={t.late} tone="terracotta" testid="card-late" />
        <Card icon={Coffee} label="Folga hoje" value={t.resting_today} testid="card-resting" />
        <Link to="/rh/ferias" data-testid="card-pending-vac-link"><Card icon={Palmtree} label="Férias a aprovar" value={t.pending_vacations} testid="card-pending-vac" /></Link>
      </div>

      {data.alerts?.length > 0 && (
        <section className="rounded-2xl bg-amber-50 border border-amber-200 p-4" data-testid="alerts-panel">
          <div className="flex items-center gap-2 text-amber-800 font-medium mb-2">
            <AlertTriangle className="w-4 h-4" /> Alertas trabalhistas ({data.alerts.length})
          </div>
          <ul className="space-y-1 text-sm max-h-64 overflow-y-auto">
            {data.alerts.map((a, i) => (
              <li key={i} className={ALERT_CLS[a.level]} data-testid={`alert-${a.type}-${i}`}><strong>{a.employee_name}</strong> — {a.message}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="grid lg:grid-cols-2 gap-4">
        <List title="Trabalhando agora" items={data.working_now} empty="Ninguém com entrada registrada" right={punchTxt} testid="working-list" />
        <List title="Em intervalo" items={data.on_break} empty="Ninguém em intervalo" right={punchTxt} testid="break-list" />
        <List title="Atrasados (sem entrada)" items={data.late} empty="Nenhum atraso" right={shiftTxt} testid="late-list" />
        <List title="Escalados hoje" items={data.scheduled_today} empty="—" right={shiftTxt} testid="scheduled-list" />
        <List title="Folga hoje" items={data.resting_today} empty="Ninguém de folga" right={(x) => (x.shift?.is_vacation ? "Férias" : x.shift?.is_dsr ? "DSR (domingo)" : "Folga")} testid="resting-list" />
        {data.off_today.length > 0 && (
          <div className="rounded-2xl bg-white border border-stone-200 p-4" data-testid="off-list">
            <h2 className="font-medium text-stone-900 mb-2 flex items-center gap-2"><CalendarCheck className="w-4 h-4" />Sem escala hoje ({data.off_today.length})</h2>
            <p className="text-sm text-stone-600">{data.off_today.map((e) => e.name).join(", ")}</p>
          </div>
        )}
      </section>
    </div>
  );
}
