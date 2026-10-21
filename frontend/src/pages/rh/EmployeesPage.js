import { useEffect, useState } from "react";
import { api } from "@/lib/apiClient";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Plus, Edit, Trash2, Key } from "lucide-react";

const WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
const EMPTY = {
  name: "", cpf: "", role_title: "Camareira", email: "", phone: "",
  hire_date: new Date().toISOString().slice(0, 10),
  base_salary: 1518.0, weekly_hours: 44, weekly_rest_days: [5, 6],
  default_shift_start: "08:00", default_shift_end: "17:00", status: "active",
  dependents: 0, sunday_rest_every_weeks: 3, sunday_offset: 0,
};

export default function EmployeesPage() {
  const [rows, setRows] = useState([]);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [open, setOpen] = useState(false);
  const [pwdFor, setPwdFor] = useState(null);
  const [pwd, setPwd] = useState("");

  const load = () => api.get("/hr/employees").then((r) => setRows(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const openCreate = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (r) => { setEditing(r); setForm({ ...EMPTY, ...r }); setOpen(true); };
  const toggleRest = (d) => setForm((f) => ({
    ...f,
    weekly_rest_days: f.weekly_rest_days.includes(d) ? f.weekly_rest_days.filter((x) => x !== d) : [...f.weekly_rest_days, d].sort(),
  }));

  const save = async () => {
    try {
      if (form.weekly_rest_days.length !== 2) return toast.error("Selecione exatamente 2 folgas semanais (5×2)");
      if (editing) await api.put(`/hr/employees/${editing.id}`, form);
      else await api.post("/hr/employees", form);
      toast.success("Colaborador salvo");
      setOpen(false);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Falha ao salvar"); }
  };

  const remove = async (r) => {
    if (!window.confirm(`Excluir ${r.name}? O colaborador ficará inativo; escala, ponto e férias são mantidos no histórico.`)) return;
    await api.delete(`/hr/employees/${r.id}`);
    toast.success("Removido");
    load();
  };

  const setPassword = async () => {
    try {
      await api.post(`/hr/employees/${pwdFor.id}/portal-password`, { password: pwd });
      toast.success("Senha definida — compartilhe com o colaborador.");
      setPwdFor(null); setPwd("");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Falha"); }
  };

  return (
    <div className="space-y-5" data-testid="employees-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-serif text-2xl text-stone-900">Colaboradores</h1>
          <p className="text-sm text-stone-500">{rows.length} cadastrado(s)</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button onClick={openCreate} className="btn-terra" data-testid="btn-new-employee"><Plus className="w-4 h-4 mr-1" />Novo colaborador</Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle>{editing ? "Editar colaborador" : "Novo colaborador"}</DialogTitle><DialogDescription className="sr-only">Dados do colaborador</DialogDescription></DialogHeader>
            <div className="grid sm:grid-cols-2 gap-3">
              <div className="sm:col-span-2"><Label>Nome completo *</Label>
                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="emp-name" /></div>
              <div><Label>CPF</Label>
                <Input value={form.cpf} onChange={(e) => setForm({ ...form, cpf: e.target.value })} data-testid="emp-cpf" /></div>
              <div><Label>Cargo</Label>
                <Input value={form.role_title} onChange={(e) => setForm({ ...form, role_title: e.target.value })} data-testid="emp-role" /></div>
              <div><Label>E-mail (login do portal)</Label>
                <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="emp-email" /></div>
              <div><Label>Telefone</Label>
                <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></div>
              <div><Label>Data de admissão *</Label>
                <Input type="date" value={form.hire_date} onChange={(e) => setForm({ ...form, hire_date: e.target.value })} data-testid="emp-hire-date" /></div>
              <div><Label>Salário base (R$)</Label>
                <Input type="number" step="0.01" value={form.base_salary} onChange={(e) => setForm({ ...form, base_salary: Number(e.target.value) })} data-testid="emp-salary" /></div>
              <div><Label>Jornada semanal (h)</Label>
                <Input type="number" value={form.weekly_hours} onChange={(e) => setForm({ ...form, weekly_hours: Number(e.target.value) })} /></div>
              <div><Label>Início do turno</Label>
                <Input type="time" value={form.default_shift_start} onChange={(e) => setForm({ ...form, default_shift_start: e.target.value })} /></div>
              <div><Label>Fim do turno</Label>
                <Input type="time" value={form.default_shift_end} onChange={(e) => setForm({ ...form, default_shift_end: e.target.value })} /></div>
              <div><Label>Dependentes (IRRF)</Label>
                <Input type="number" min={0} value={form.dependents} onChange={(e) => setForm({ ...form, dependents: Number(e.target.value) })} data-testid="emp-dependents" /></div>
              <div><Label>Domingo de folga a cada (semanas)</Label>
                <Input type="number" min={1} max={7} value={form.sunday_rest_every_weeks} onChange={(e) => setForm({ ...form, sunday_rest_every_weeks: Number(e.target.value) })} data-testid="emp-sunday-every" /></div>
              <div><Label>Defasagem do rodízio (0, 1, 2…)</Label>
                <Input type="number" min={0} value={form.sunday_offset} onChange={(e) => setForm({ ...form, sunday_offset: Number(e.target.value) })} data-testid="emp-sunday-offset" /></div>
              <div className="sm:col-span-2">
                <Label>Folgas semanais (selecione 2 dias) *</Label>
                <div className="flex flex-wrap gap-2 mt-2" data-testid="emp-rest-days">
                  {WEEKDAYS.map((lbl, i) => (
                    <button key={i} type="button" onClick={() => toggleRest(i)}
                      className={`px-3 py-1.5 rounded-full text-sm border ${form.weekly_rest_days.includes(i) ? "bg-[color:var(--pousada-palm)]/10 border-[color:var(--pousada-palm)] text-[color:var(--pousada-palm)]" : "bg-white border-stone-200 text-stone-600 hover:border-stone-300"}`}
                      data-testid={`rest-day-${i}`}>{lbl}</button>
                  ))}
                </div>
                <p className="text-xs text-stone-500 mt-1">Se domingo não for folga fixa, o gerador aplica o rodízio (padrão: 1 domingo a cada 3 semanas — Lei 10.101 art. 6º). Use a defasagem para alternar domingos entre a equipe.</p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setOpen(false)}>Cancelar</Button>
              <Button className="btn-terra" onClick={save} data-testid="btn-save-employee">Salvar</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="rounded-2xl bg-white border border-stone-200 overflow-x-auto">
        <table className="w-full text-sm min-w-[760px]">
          <thead className="bg-stone-50 text-xs uppercase tracking-widest text-stone-500">
            <tr>
              <th className="text-left p-3">Nome</th><th className="text-left p-3">Cargo</th>
              <th className="text-left p-3">Admissão</th><th className="text-left p-3">Jornada</th>
              <th className="text-left p-3">Folgas</th><th className="text-left p-3">Portal</th>
              <th className="text-right p-3">Ações</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={7} className="p-6 text-center text-stone-500">Nenhum colaborador — cadastre o primeiro.</td></tr>}
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-stone-100" data-testid={`emp-row-${r.id}`}>
                <td className="p-3">
                  <div className="font-medium">{r.name}</div>
                  <div className="text-xs text-stone-500">{r.email || "sem e-mail"}</div>
                </td>
                <td className="p-3">{r.role_title}</td>
                <td className="p-3 font-mono text-xs">{r.hire_date}</td>
                <td className="p-3 font-mono text-xs">{r.weekly_hours}h · {r.default_shift_start}–{r.default_shift_end}</td>
                <td className="p-3 text-xs">{(r.weekly_rest_days || []).map((d) => WEEKDAYS[d]).join(" + ")}</td>
                <td className="p-3 text-xs">{r.portal_password_set ? <span className="text-emerald-700">Ativo</span> : <span className="text-stone-400">Sem senha</span>}</td>
                <td className="p-3 text-right">
                  <div className="inline-flex gap-1">
                    <Button size="icon" variant="ghost" onClick={() => setPwdFor(r)} title="Definir senha do portal" data-testid={`emp-pwd-${r.id}`}><Key className="w-4 h-4" /></Button>
                    <Button size="icon" variant="ghost" onClick={() => openEdit(r)} title="Editar" data-testid={`emp-edit-${r.id}`}><Edit className="w-4 h-4" /></Button>
                    <Button size="icon" variant="ghost" onClick={() => remove(r)} title="Remover" data-testid={`emp-del-${r.id}`}><Trash2 className="w-4 h-4 text-red-600" /></Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={!!pwdFor} onOpenChange={(v) => { if (!v) { setPwdFor(null); setPwd(""); } }}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Senha do portal — {pwdFor?.name}</DialogTitle><DialogDescription className="sr-only">Definir senha de acesso</DialogDescription></DialogHeader>
          <div className="space-y-2">
            <Label>Nova senha (mín. 4 caracteres)</Label>
            <Input type="text" value={pwd} onChange={(e) => setPwd(e.target.value)} data-testid="pwd-input" />
            <p className="text-xs text-stone-500">O colaborador acessa em <code>/colaborador</code> com o e-mail cadastrado + esta senha.</p>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => { setPwdFor(null); setPwd(""); }}>Cancelar</Button>
            <Button className="btn-terra" onClick={setPassword} disabled={pwd.length < 4} data-testid="pwd-save">Definir senha</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
