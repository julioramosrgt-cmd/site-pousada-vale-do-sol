import { useEffect, useState } from "react";
import { colabApi } from "@/lib/colabAuth";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { VacationPeriods } from "@/components/hr/VacationPeriods";
import { VacationForm } from "@/components/hr/VacationForm";
import { RequestRow } from "@/pages/rh/FeriasPage";
import { Plus } from "lucide-react";

export default function ColabFerias() {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const load = () => colabApi.get("/employee/vacations").then((r) => setData(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const request = async (payload) => {
    await colabApi.post("/employee/vacations", payload);
    toast.success("Pedido enviado ao RH");
    load();
  };
  const cancel = async (v) => {
    try { await colabApi.post(`/employee/vacations/${v.id}/cancel`); toast.success("Pedido cancelado"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Falha"); }
  };

  if (!data) return <div className="text-stone-500">Carregando…</div>;
  return (
    <div className="space-y-4" data-testid="colab-ferias">
      <div className="flex items-center justify-between">
        <h1 className="font-serif text-xl text-stone-900">Minhas férias</h1>
        <Button className="btn-terra" onClick={() => setOpen(true)} data-testid="btn-request-vacation"><Plus className="w-4 h-4 mr-1" />Pedir férias</Button>
      </div>
      <section className="rounded-2xl bg-white border border-stone-200 p-4"><VacationPeriods periods={data.periods} /></section>
      <section className="rounded-2xl bg-white border border-stone-200 p-4">
        <h2 className="font-medium text-stone-900 mb-2">Meus pedidos</h2>
        {data.requests.length === 0 && <p className="text-sm text-stone-400">Nenhum pedido ainda.</p>}
        <div className="divide-y divide-stone-100">
          {data.requests.map((v) => (
            <div key={v.id} className="flex items-center gap-2">
              <ul className="flex-1"><RequestRow v={v} /></ul>
              {v.status === "pending" && <Button size="sm" variant="ghost" onClick={() => cancel(v)} data-testid={`vac-cancel-${v.id}`}>Cancelar</Button>}
            </div>
          ))}
        </div>
      </section>
      <VacationForm open={open} onOpenChange={setOpen} periods={data.periods} onSubmit={request} title="Pedir férias" />
    </div>
  );
}
