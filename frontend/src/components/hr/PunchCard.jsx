import { useEffect, useState } from "react";
import { colabApi } from "@/lib/colabAuth";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { PUNCH_LABELS, fmtDate } from "@/lib/hrUtils";
import { Fingerprint, CheckCircle2 } from "lucide-react";

const Receipt = ({ r, onClose }) => (
  <Dialog open={!!r} onOpenChange={(o) => !o && onClose()}>
    <DialogContent className="max-w-sm">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2"><CheckCircle2 className="w-5 h-5 text-emerald-600" />Comprovante de registro de ponto</DialogTitle>
        <DialogDescription>Portaria MTP 671/2021 — guarde ou tire um print.</DialogDescription>
      </DialogHeader>
      {r && (
        <dl className="text-sm grid grid-cols-[110px_1fr] gap-y-1 font-mono" data-testid="punch-receipt">
          <dt className="text-stone-500 font-sans">Empregador</dt><dd>Pousada Vale do Sol</dd>
          <dt className="text-stone-500 font-sans">Colaborador</dt><dd>{r.employee_name}</dd>
          <dt className="text-stone-500 font-sans">CPF</dt><dd>{r.employee_cpf || "-"}</dd>
          <dt className="text-stone-500 font-sans">Tipo</dt><dd data-testid="receipt-type">{PUNCH_LABELS[r.type]}</dd>
          <dt className="text-stone-500 font-sans">Data/hora</dt><dd data-testid="receipt-time">{fmtDate(r.date)} {r.time}</dd>
          <dt className="text-stone-500 font-sans">NSR</dt><dd data-testid="receipt-nsr">{String(r.nsr).padStart(9, "0")}</dd>
          <dt className="text-stone-500 font-sans">IP</dt><dd>{r.ip || "-"}</dd>
          <dt className="text-stone-500 font-sans">Hash</dt><dd className="break-all text-[10px]">{r.hash}</dd>
        </dl>
      )}
      <DialogFooter><Button onClick={onClose} data-testid="receipt-close">Fechar</Button></DialogFooter>
    </DialogContent>
  </Dialog>
);

export const PunchCard = () => {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const [clock, setClock] = useState(new Date());

  const load = () => colabApi.get("/employee/punches/today").then((r) => setState(r.data)).catch(() => {});
  useEffect(() => { load(); const t = setInterval(() => setClock(new Date()), 1000); return () => clearInterval(t); }, []);

  const punch = async () => {
    setBusy(true);
    try { const r = await colabApi.post("/employee/punch"); setReceipt(r.data); toast.success(`${r.data.label} registrada às ${r.data.time.slice(0, 5)}`); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Falha ao registrar"); }
    setBusy(false);
  };

  return (
    <section className="rounded-2xl bg-white border border-stone-200 p-5" data-testid="punch-card">
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex-1">
          <div className="text-xs uppercase tracking-widest text-stone-500">Registro de ponto</div>
          <div className="font-mono text-4xl text-stone-900 tabular-nums" data-testid="punch-clock">{clock.toLocaleTimeString("pt-BR", { timeZone: "America/Sao_Paulo" })}</div>
          <div className="flex flex-wrap gap-1.5 mt-2" data-testid="punch-today-list">
            {state?.records.map((r) => (
              <button key={r.id} onClick={() => setReceipt(r)} className="text-[11px] px-2 py-0.5 rounded-full bg-stone-100 hover:bg-stone-200" data-testid={`punch-chip-${r.type}`}>
                {PUNCH_LABELS[r.type]} {r.time.slice(0, 5)}
              </button>
            ))}
            {state && state.records.length === 0 && <span className="text-xs text-stone-400">Nenhuma marcação hoje</span>}
          </div>
        </div>
        <Button onClick={punch} disabled={busy || !state?.next_type} className="btn-terra h-16 px-6 text-base rounded-2xl active:scale-95 transition-transform" data-testid="btn-punch">
          <Fingerprint className="w-6 h-6 mr-2" />{state?.next_type ? `Registrar ${state.next_label.toLowerCase()}` : "Jornada encerrada"}
        </Button>
      </div>
      <Receipt r={receipt} onClose={() => setReceipt(null)} />
    </section>
  );
};
