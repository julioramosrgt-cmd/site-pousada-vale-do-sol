import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/apiClient";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Trash2, TrendingUp, TrendingDown } from "lucide-react";

const CATEGORIES = ["Diárias", "Consumo Bar/Restaurante", "Manutenção", "Limpeza", "Comissões OTA", "Salários", "Utilidades", "Outros"];

export default function FinancePage() {
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [range, setRange] = useState(() => {
    const t = new Date();
    return {
      from: new Date(t.getFullYear(), t.getMonth(), 1).toISOString().slice(0, 10),
      to: new Date(t.getFullYear(), t.getMonth() + 1, 0).toISOString().slice(0, 10),
    };
  });
  const [form, setForm] = useState({ kind: "income", category: "Diárias", amount: 0, entry_date: new Date().toISOString().slice(0, 10), description: "" });

  const load = () => {
    const q = `?from_date=${range.from}&to_date=${range.to}`;
    api.get(`/finance${q}`).then((r) => setRows(r.data));
    api.get(`/finance/summary${q}`).then((r) => setSummary(r.data));
  };
  useEffect(load, [range]);

  const save = async (e) => {
    e.preventDefault();
    await api.post("/finance", { ...form, amount: parseFloat(form.amount || 0) });
    toast.success("Lançamento salvo");
    setForm({ ...form, amount: 0, description: "" });
    load();
  };

  const remove = async (id) => {
    if (!window.confirm("Excluir lançamento?")) return;
    await api.delete(`/finance/${id}`); load();
  };

  return (
    <div>
      <div className="mb-6">
        <span className="text-xs uppercase tracking-widest text-amber-800/70">Financeiro</span>
        <h1 className="font-serif text-3xl sm:text-4xl">Receitas & Despesas</h1>
      </div>

      <div className="grid sm:grid-cols-3 gap-4 mb-6">
        <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm p-5">
          <div className="flex justify-between text-xs uppercase tracking-widest text-stone-500"><span>Receitas</span><TrendingUp className="w-4 h-4 text-emerald-700" /></div>
          <div className="mt-2 font-serif text-3xl text-emerald-700">R$ {summary?.income?.toFixed(2) ?? "0.00"}</div>
        </div>
        <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm p-5">
          <div className="flex justify-between text-xs uppercase tracking-widest text-stone-500"><span>Despesas</span><TrendingDown className="w-4 h-4 text-red-700" /></div>
          <div className="mt-2 font-serif text-3xl text-red-700">R$ {summary?.expense?.toFixed(2) ?? "0.00"}</div>
        </div>
        <div className="rounded-2xl bg-[color:var(--pousada-terracotta)] text-white p-5">
          <div className="flex justify-between text-xs uppercase tracking-widest text-white/80"><span>Lucro</span><span>{summary?.occupancy ?? 0}% ocup.</span></div>
          <div className="mt-2 font-serif text-3xl">R$ {summary?.profit?.toFixed(2) ?? "0.00"}</div>
        </div>
      </div>

      <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm p-6 mb-6">
        <div className="grid sm:grid-cols-2 gap-3 mb-3">
          <div><Label>De</Label><Input type="date" value={range.from} onChange={(e) => setRange({ ...range, from: e.target.value })} data-testid="fin-from" /></div>
          <div><Label>Até</Label><Input type="date" value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })} data-testid="fin-to" /></div>
        </div>
        <form onSubmit={save} className="grid sm:grid-cols-6 gap-2 items-end">
          <div>
            <Label>Tipo</Label>
            <Select value={form.kind} onValueChange={(v) => setForm({ ...form, kind: v })}>
              <SelectTrigger data-testid="fin-kind"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="income">Receita</SelectItem><SelectItem value="expense">Despesa</SelectItem></SelectContent>
            </Select>
          </div>
          <div>
            <Label>Categoria</Label>
            <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div><Label>Data</Label><Input type="date" value={form.entry_date} onChange={(e) => setForm({ ...form, entry_date: e.target.value })} /></div>
          <div><Label>Valor R$</Label><Input type="number" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} data-testid="fin-amount" /></div>
          <div className="sm:col-span-2 flex gap-2">
            <div className="flex-1"><Label>Descrição</Label><Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
            <Button type="submit" className="btn-terra rounded-xl mb-0.5" data-testid="fin-submit"><Plus className="w-4 h-4" /></Button>
          </div>
        </form>
      </div>

      <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-xs uppercase tracking-widest text-stone-500">
              <tr><th className="p-3 text-left">Data</th><th className="p-3 text-left">Tipo</th><th className="p-3 text-left">Categoria</th><th className="p-3 text-left">Descrição</th><th className="p-3 text-right">Valor</th><th className="p-3"></th></tr>
            </thead>
            <tbody>
              {rows.length === 0 && <tr><td colSpan={6} className="p-6 text-center text-stone-500">Sem lançamentos no período.</td></tr>}
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-stone-100">
                  <td className="p-3 font-mono text-xs">{r.entry_date}</td>
                  <td className="p-3">{r.kind === "income" ? <span className="text-emerald-700">Receita</span> : <span className="text-red-700">Despesa</span>}</td>
                  <td className="p-3">{r.category}</td>
                  <td className="p-3">{r.description}</td>
                  <td className={`p-3 text-right font-mono ${r.kind === "income" ? "text-emerald-700" : "text-red-700"}`}>{r.kind === "income" ? "+" : "-"} R$ {Number(r.amount).toFixed(2)}</td>
                  <td className="p-3 text-right"><Button size="icon" variant="ghost" onClick={() => remove(r.id)}><Trash2 className="w-4 h-4 text-red-600" /></Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
