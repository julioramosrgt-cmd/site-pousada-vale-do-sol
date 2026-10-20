import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { fmtDate } from "@/lib/hrUtils";

export const VacationForm = ({ open, onOpenChange, periods, onSubmit, title }) => {
  const eligible = periods.filter((p) => p.status !== "em_aquisicao" && p.balance - p.pending_days > 0);
  const [f, setF] = useState({ period_start: "", start_date: "", days: 30, sell_days: 0, notes: "" });
  const [busy, setBusy] = useState(false);
  const period = f.period_start || eligible[0]?.period_start || "";

  const submit = async () => {
    setBusy(true);
    try {
      await onSubmit({ ...f, period_start: period, days: Number(f.days), sell_days: Number(f.sell_days) });
      onOpenChange(false);
    } catch (e) { toast.error(e?.response?.data?.detail || "Falha ao enviar"); }
    setBusy(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>Mín. 5 dias por período, até 3 frações (uma com 14+ dias) e abono de até 10 dias.</DialogDescription>
        </DialogHeader>
        {eligible.length === 0 ? <p className="text-sm text-stone-500" data-testid="vac-no-balance">Nenhum período com saldo disponível.</p> : (
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2"><Label>Período aquisitivo</Label>
              <Select value={period} onValueChange={(v) => setF({ ...f, period_start: v })}>
                <SelectTrigger data-testid="vac-period"><SelectValue /></SelectTrigger>
                <SelectContent>{eligible.map((p) => <SelectItem key={p.period_start} value={p.period_start}>{fmtDate(p.period_start)} – saldo {p.balance - p.pending_days}d</SelectItem>)}</SelectContent>
              </Select></div>
            <div className="col-span-2"><Label>Início</Label>
              <Input type="date" value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} data-testid="vac-start" /></div>
            <div><Label>Dias de descanso</Label>
              <Input type="number" min={5} max={30} value={f.days} onChange={(e) => setF({ ...f, days: e.target.value })} data-testid="vac-days" /></div>
            <div><Label>Abono (vender)</Label>
              <Input type="number" min={0} max={10} value={f.sell_days} onChange={(e) => setF({ ...f, sell_days: e.target.value })} data-testid="vac-sell" /></div>
            <div className="col-span-2"><Label>Observações</Label>
              <Input value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} data-testid="vac-notes" /></div>
          </div>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} data-testid="vac-cancel">Cancelar</Button>
          <Button className="btn-terra" onClick={submit} disabled={busy || !eligible.length || !f.start_date} data-testid="vac-submit">Enviar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
