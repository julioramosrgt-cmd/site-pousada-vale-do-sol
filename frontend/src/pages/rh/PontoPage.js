import { useEffect, useState } from "react";
import { api } from "@/lib/apiClient";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { TimesheetTable } from "@/components/hr/TimesheetTable";
import { currentMonth, downloadPdf, PUNCH_LABELS } from "@/lib/hrUtils";
import { FileDown, Plus } from "lucide-react";

export default function PontoPage() {
  const [employees, setEmployees] = useState([]);
  const [empId, setEmpId] = useState("");
  const [month, setMonth] = useState(currentMonth());
  const [data, setData] = useState(null);
  const [adj, setAdj] = useState(null);

  useEffect(() => {
    api.get("/hr/employees").then((r) => { setEmployees(r.data); if (r.data[0]) setEmpId(r.data[0].id); });
  }, []);

  const load = () => { if (empId) api.get(`/hr/timesheet?employee_id=${empId}&month=${month}`).then((r) => setData(r.data)); };
  useEffect(() => { load(); }, [empId, month]); // eslint-disable-line

  const onVoid = async (r) => {
    const reason = window.prompt(`Justificativa para desconsiderar a marcação ${r.time.slice(0, 5)} (mín. 5 caracteres):`);
    if (!reason) return;
    if (reason.trim().length < 5) return toast.error("Justificativa precisa de no mínimo 5 caracteres");
    try { await api.post(`/hr/time-records/${r.id}/void`, { reason }); toast.success("Marcação desconsiderada"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Falha"); }
  };

  const saveAdj = async () => {
    if (!adj.date || !adj.time) return toast.error("Informe data e hora");
    if (adj.reason.trim().length < 5) return toast.error("Justificativa precisa de no mínimo 5 caracteres");
    try { await api.post("/hr/time-records", { ...adj, employee_id: empId }); toast.success("Marcação incluída"); setAdj(null); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Falha"); }
  };

  const pdf = () => downloadPdf(api, `/hr/timesheet/pdf?employee_id=${empId}&month=${month}`, `espelho-ponto-${month}.pdf`)
    .catch(() => toast.error("Falha ao gerar PDF"));

  return (
    <div className="space-y-5" data-testid="ponto-page">
      <div className="flex flex-wrap items-end gap-3">
        <div className="mr-auto">
          <h1 className="font-serif text-2xl text-stone-900">Ponto eletrônico</h1>
          <p className="text-sm text-stone-500">Espelho de ponto, ajustes com justificativa e exportação (Portaria 671).</p>
        </div>
        <div><Label className="text-xs">Mês</Label><Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="w-40" data-testid="ponto-month" /></div>
        <div className="min-w-[200px]"><Label className="text-xs">Colaborador</Label>
          <Select value={empId} onValueChange={setEmpId}>
            <SelectTrigger data-testid="ponto-emp"><SelectValue placeholder="Selecione" /></SelectTrigger>
            <SelectContent>{employees.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}</SelectContent>
          </Select></div>
        <Button variant="outline" onClick={() => setAdj({ date: "", time: "", type: "entrada", reason: "" })} disabled={!empId} data-testid="btn-add-punch"><Plus className="w-4 h-4 mr-1" />Incluir marcação</Button>
        <Button className="btn-terra" onClick={pdf} disabled={!empId} data-testid="btn-ponto-pdf"><FileDown className="w-4 h-4 mr-1" />Espelho PDF</Button>
      </div>

      {!empId && <p className="text-sm text-stone-500">Cadastre um colaborador primeiro.</p>}
      {data && <TimesheetTable data={data} onVoid={onVoid} />}

      <Dialog open={!!adj} onOpenChange={(o) => !o && setAdj(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Incluir marcação</DialogTitle>
            <DialogDescription>A marcação original nunca é apagada; o ajuste fica registrado com sua justificativa.</DialogDescription>
          </DialogHeader>
          {adj && (
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Data</Label><Input type="date" value={adj.date} onChange={(e) => setAdj({ ...adj, date: e.target.value })} data-testid="adj-date" /></div>
              <div><Label>Hora</Label><Input type="time" value={adj.time} onChange={(e) => setAdj({ ...adj, time: e.target.value })} data-testid="adj-time" /></div>
              <div className="col-span-2"><Label>Tipo</Label>
                <Select value={adj.type} onValueChange={(v) => setAdj({ ...adj, type: v })}>
                  <SelectTrigger data-testid="adj-type"><SelectValue /></SelectTrigger>
                  <SelectContent>{Object.entries(PUNCH_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
                </Select></div>
              <div className="col-span-2"><Label>Justificativa *</Label><Input value={adj.reason} onChange={(e) => setAdj({ ...adj, reason: e.target.value })} placeholder="Ex.: esqueceu de marcar a saída" data-testid="adj-reason" /></div>
            </div>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setAdj(null)} data-testid="adj-cancel">Cancelar</Button>
            <Button className="btn-terra" onClick={saveAdj} data-testid="adj-save">Salvar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
