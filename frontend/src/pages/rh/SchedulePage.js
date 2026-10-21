import { useEffect, useMemo, useState } from "react";
import { currentMonth } from "@/lib/hrUtils";
import { api } from "@/lib/apiClient";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Wand2, AlertTriangle } from "lucide-react";

const WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

function monthMatrix(month) {
  const [y, m] = month.split("-").map(Number);
  const days = new Date(y, m, 0).getDate();
  return Array.from({ length: days }, (_, i) => {
    const d = new Date(y, m - 1, i + 1);
    return { date: `${month}-${String(i + 1).padStart(2, "0")}`, weekday: (d.getDay() + 6) % 7, dayNum: i + 1 };
  });
}

export default function SchedulePage() {
  const [employees, setEmployees] = useState([]);
  const [month, setMonth] = useState(currentMonth);
  const [empId, setEmpId] = useState("");
  const [shifts, setShifts] = useState([]);
  const [violations, setViolations] = useState([]);
  const [edit, setEdit] = useState(null);

  useEffect(() => {
    api.get("/hr/employees").then((r) => {
      setEmployees(r.data);
      if (r.data[0] && !empId) setEmpId(r.data[0].id);
    });
  }, []);  // eslint-disable-line

  const load = () => {
    if (!empId) { setShifts([]); return; }
    api.get(`/hr/schedule?month=${month}&employee_id=${empId}`).then((r) => setShifts(r.data));
    api.get(`/hr/schedule/violations?month=${month}&employee_id=${empId}`).then((r) => setViolations(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, [month, empId]);  // eslint-disable-line

  const generate = async () => {
    if (!empId) return toast.error("Selecione um colaborador");
    try {
      const r = await api.post(`/hr/employees/${empId}/schedule/generate?month=${month}`);
      toast.success(`Escala gerada: ${r.data.created} dias${r.data.kept_manual ? ` · ${r.data.kept_manual} edição(ões) manual(is) preservada(s)` : ""}`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Falha ao gerar"); }
  };

  const saveShift = async () => {
    try {
      const body = edit.is_rest ? { is_rest: true } : { is_rest: false, start_time: edit.start_time, end_time: edit.end_time };
      await api.put(`/hr/shifts/${edit.id}`, body);
      setEdit(null);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Falha"); }
  };

  const grid = useMemo(() => monthMatrix(month), [month]);
  const byDate = useMemo(() => Object.fromEntries(shifts.map((s) => [s.date, s])), [shifts]);
  const totals = useMemo(() => {
    const working = shifts.filter((s) => !s.is_rest).length;
    const resting = shifts.filter((s) => s.is_rest).length;
    const dsr = shifts.filter((s) => s.is_dsr).length;
    return { working, resting, dsr };
  }, [shifts]);

  return (
    <div className="space-y-5" data-testid="schedule-page">
      <div className="flex items-end flex-wrap gap-3">
        <div>
          <h1 className="font-serif text-2xl text-stone-900">Escala 5×2</h1>
          <p className="text-sm text-stone-500">Gerador automático com rodízio de domingos e validação CLT. Clique em um dia para editar.</p>
        </div>
        <div className="w-full sm:w-auto sm:ml-auto flex flex-wrap items-end gap-3">
          <div><Label className="text-xs">Mês</Label>
            <Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="w-40" data-testid="sched-month" /></div>
          <div className="w-full sm:w-auto sm:min-w-[220px]"><Label className="text-xs">Colaborador</Label>
            <Select value={empId} onValueChange={setEmpId}>
              <SelectTrigger data-testid="sched-emp"><SelectValue placeholder="Selecione" /></SelectTrigger>
              <SelectContent>{employees.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}</SelectContent>
            </Select></div>
          <Button className="btn-terra" onClick={generate} disabled={!empId} data-testid="btn-generate-schedule">
            <Wand2 className="w-4 h-4 mr-1" />Gerar escala
          </Button>
        </div>
      </div>

      {violations.length > 0 && (
        <div className="rounded-2xl bg-amber-50 border border-amber-200 p-4" data-testid="interjornada-warnings">
          <div className="flex items-center gap-2 text-amber-800 font-medium mb-2">
            <AlertTriangle className="w-4 h-4" /> Violações CLT na escala ({violations.length})
          </div>
          <ul className="text-sm text-amber-900">
            {violations.map((v, i) => <li key={i} data-testid={`violation-${v.rule}-${i}`}>• {v.message}</li>)}
          </ul>
        </div>
      )}

      <div className="rounded-2xl bg-white border border-stone-200 p-4">
        <div className="grid grid-cols-7 gap-1.5 text-[11px] uppercase tracking-widest text-stone-500 mb-2">
          {WEEKDAYS.map((d) => <div key={d} className="text-center">{d}</div>)}
        </div>
        <div className="grid grid-cols-7 gap-1.5" data-testid="sched-grid">
          {Array.from({ length: grid[0]?.weekday || 0 }).map((_, i) => <div key={`pad-${i}`} />)}
          {grid.map((cell) => {
            const s = byDate[cell.date];
            const isRest = s?.is_rest;
            const bg = !s ? "bg-stone-50 text-stone-400" :
              s.is_vacation ? "bg-sky-50 text-sky-800 border-sky-200" :
              isRest ? "bg-emerald-50 text-emerald-800 border-emerald-200" :
              "bg-[color:var(--pousada-terracotta)]/10 text-[color:var(--pousada-terracotta)] border-[color:var(--pousada-terracotta)]/30";
            return (
              <button key={cell.date} onClick={() => s && setEdit({ ...s, start_time: s.start_time || "08:00", end_time: s.end_time || "17:00" })} disabled={!s}
                className={`rounded-lg border p-2 text-left h-20 ${bg} ${!s ? "" : "hover:brightness-95 cursor-pointer"}`}
                title={s ? (isRest ? (s.is_dsr ? "DSR (domingo)" : "Folga rotativa") : `${s.start_time}–${s.end_time}`) : "Sem escala"}
                data-testid={`cell-${cell.date}`}>
                <div className="text-xs font-mono">{cell.dayNum}</div>
                {s ? (
                  isRest ? <div className="text-[10px] font-medium mt-1">{s.is_vacation ? "Férias" : s.is_dsr ? "DSR" : "Folga"}</div> : <div className="text-[10px] font-mono mt-1">{s.start_time}<br />–{s.end_time}</div>
                ) : <div className="text-[10px] mt-1">—</div>}
              </button>
            );
          })}
        </div>
        <div className="mt-4 flex gap-4 text-xs text-stone-500">
          <div><strong className="text-stone-900">{totals.working}</strong> dias trabalhados</div>
          <div><strong className="text-stone-900">{totals.resting}</strong> folgas</div>
          <div><strong className="text-stone-900">{totals.dsr}</strong> DSR em domingo</div>
          {totals.dsr === 0 && totals.working > 0 && <div className="text-amber-700">Sem DSR dominical</div>}
        </div>
      </div>

      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Turno de {edit?.date.split("-").reverse().join("/")}</DialogTitle>
            <DialogDescription>Após salvar, a escala é revalidada (11h, DSR, rodízio de domingos).</DialogDescription>
          </DialogHeader>
          {edit && (
            <div className="space-y-3">
              <label className="flex items-center justify-between text-sm">Folga neste dia
                <Switch checked={edit.is_rest} onCheckedChange={(v) => setEdit({ ...edit, is_rest: v })} data-testid="shift-rest-toggle" /></label>
              {!edit.is_rest && (
                <div className="grid grid-cols-2 gap-3">
                  <div><Label>Início</Label><Input type="time" value={edit.start_time} onChange={(e) => setEdit({ ...edit, start_time: e.target.value })} data-testid="shift-start" /></div>
                  <div><Label>Fim</Label><Input type="time" value={edit.end_time} onChange={(e) => setEdit({ ...edit, end_time: e.target.value })} data-testid="shift-end" /></div>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEdit(null)} data-testid="shift-cancel">Cancelar</Button>
            <Button className="btn-terra" onClick={saveShift} data-testid="shift-save">Salvar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
