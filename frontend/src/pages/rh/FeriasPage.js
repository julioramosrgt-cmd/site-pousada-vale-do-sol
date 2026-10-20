import { useEffect, useState } from "react";
import { api } from "@/lib/apiClient";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { VacationPeriods } from "@/components/hr/VacationPeriods";
import { VacationForm } from "@/components/hr/VacationForm";
import { Badge, REQ_STATUS, fmtDate } from "@/lib/hrUtils";
import { Check, X, Plus } from "lucide-react";

const RequestRow = ({ v, onDecide }) => (
  <li className="py-2 flex flex-wrap items-center gap-3 text-sm" data-testid={`vac-req-${v.id}`}>
    <span className="font-mono text-xs">{fmtDate(v.start_date)} → {fmtDate(v.end_date)}</span>
    <span>{v.days}d{v.sell_days ? ` + ${v.sell_days}d abono` : ""}</span>
    {!v.notice_ok && v.status === "pending" && <span className="text-[11px] text-amber-700">aviso &lt; 30 dias (art. 135)</span>}
    <Badge map={REQ_STATUS} value={v.status} testid={`vac-status-${v.id}`} />
    {v.status === "pending" && onDecide && (
      <span className="ml-auto flex gap-1">
        <Button size="sm" variant="outline" onClick={() => onDecide(v, true)} data-testid={`vac-approve-${v.id}`}><Check className="w-4 h-4" /></Button>
        <Button size="sm" variant="outline" onClick={() => onDecide(v, false)} data-testid={`vac-reject-${v.id}`}><X className="w-4 h-4" /></Button>
      </span>
    )}
  </li>
);

export default function FeriasPage() {
  const [rows, setRows] = useState([]);
  const [formFor, setFormFor] = useState(null);
  const load = () => api.get("/hr/vacations").then((r) => setRows(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const decide = async (v, approve) => {
    try { await api.post(`/hr/vacations/${v.id}/decision`, { approve }); toast.success(approve ? "Férias aprovadas — escala atualizada" : "Pedido recusado"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Falha"); }
  };
  const create = async (payload) => {
    await api.post("/hr/vacations", { ...payload, employee_id: formFor.employee.id });
    toast.success("Férias lançadas e aprovadas");
    load();
  };
  const pending = rows.flatMap((r) => r.requests.filter((v) => v.status === "pending"));

  return (
    <div className="space-y-5" data-testid="ferias-page">
      <div>
        <h1 className="font-serif text-2xl text-stone-900">Férias</h1>
        <p className="text-sm text-stone-500">{pending.length} pedido(s) aguardando aprovação · períodos aquisitivos/concessivos (arts. 130–145).</p>
      </div>
      {rows.length === 0 && <p className="text-sm text-stone-500">Nenhum colaborador ativo.</p>}
      {rows.map((r) => (
        <section key={r.employee.id} className="rounded-2xl bg-white border border-stone-200 p-4 space-y-3" data-testid={`vac-emp-${r.employee.id}`}>
          <div className="flex items-center justify-between">
            <div><div className="font-medium text-stone-900">{r.employee.name}</div>
              <div className="text-xs text-stone-500">Admissão {fmtDate(r.employee.hire_date)}</div></div>
            <Button size="sm" variant="outline" onClick={() => setFormFor(r)} data-testid={`vac-new-${r.employee.id}`}><Plus className="w-4 h-4 mr-1" />Lançar férias</Button>
          </div>
          <VacationPeriods periods={r.periods} testid={`vac-periods-${r.employee.id}`} />
          {r.requests.length > 0 && <ul className="divide-y divide-stone-100 border-t border-stone-100">{r.requests.map((v) => <RequestRow key={v.id} v={v} onDecide={decide} />)}</ul>}
        </section>
      ))}
      {formFor && <VacationForm open={!!formFor} onOpenChange={(o) => !o && setFormFor(null)} periods={formFor.periods}
        onSubmit={create} title={`Lançar férias — ${formFor.employee.name}`} />}
    </div>
  );
}

export { RequestRow };
