import { useEffect, useState } from "react";
import { api } from "@/lib/apiClient";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Plus, Trash2, KeyRound, ShieldCheck } from "lucide-react";

const ROLE_LABEL = { admin: "Administrador", reception: "Recepção" };

export default function UsersPage() {
  const { user: me } = useAuth();
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ email: "", password: "", role: "reception" });
  const [pwdUser, setPwdUser] = useState(null);
  const [pwdVal, setPwdVal] = useState("");

  const load = () => {
    api.get("/users").then((r) => setRows(r.data)).catch(() => toast.error("Acesso restrito ao Administrador"));
  };
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/users", form);
      toast.success("Usuário criado");
      setOpen(false); setForm({ email: "", password: "", role: "reception" }); load();
    } catch (err) { toast.error(err?.response?.data?.detail || "Erro"); }
  };

  const changeRole = async (u, role) => {
    try { await api.put(`/users/${u.id}`, { role }); toast.success("Perfil atualizado"); load(); }
    catch (err) { toast.error(err?.response?.data?.detail || "Erro"); }
  };

  const resetPwd = async (e) => {
    e.preventDefault();
    try {
      await api.put(`/users/${pwdUser.id}`, { password: pwdVal });
      toast.success("Senha redefinida"); setPwdUser(null); setPwdVal("");
    } catch (err) { toast.error(err?.response?.data?.detail || "Erro"); }
  };

  const remove = async (u) => {
    if (!window.confirm(`Remover ${u.email}?`)) return;
    try { await api.delete(`/users/${u.id}`); toast.success("Removido"); load(); }
    catch (err) { toast.error(err?.response?.data?.detail || "Erro"); }
  };

  return (
    <div>
      <div className="flex items-end justify-between mb-6">
        <div>
          <span className="text-xs uppercase tracking-widest text-amber-800/70">Segurança & Acesso</span>
          <h1 className="font-serif text-3xl sm:text-4xl">Usuários</h1>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button className="btn-terra rounded-xl" data-testid="btn-new-user"><Plus className="w-4 h-4 mr-1" />Novo usuário</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Novo usuário</DialogTitle></DialogHeader>
            <form onSubmit={create} className="space-y-3">
              <div><Label>E-mail</Label><Input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="user-email" /></div>
              <div><Label>Senha (mín 6)</Label><Input type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-testid="user-password" /></div>
              <div>
                <Label>Perfil</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                  <SelectTrigger data-testid="user-role"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="reception">Recepção (sem financeiro nem configurações)</SelectItem>
                    <SelectItem value="admin">Administrador (acesso total)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button type="submit" className="btn-terra w-full rounded-xl">Criar</Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-xs uppercase tracking-widest text-stone-500">
            <tr><th className="p-3 text-left">E-mail</th><th className="p-3 text-left">Perfil</th><th className="p-3 text-left">Criado em</th><th className="p-3 text-right">Ações</th></tr>
          </thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={4} className="p-6 text-center text-stone-500">Nenhum usuário</td></tr>}
            {rows.map((u) => (
              <tr key={u.id} className="border-t border-stone-100" data-testid={`user-row-${u.id}`}>
                <td className="p-3">{u.email}{u.id === me?.id && <span className="ml-2 text-xs text-[color:var(--pousada-terracotta)]">(você)</span>}</td>
                <td className="p-3">
                  <Select value={u.role} onValueChange={(v) => changeRole(u, v)} disabled={u.id === me?.id}>
                    <SelectTrigger className="w-40 h-8"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="reception">Recepção</SelectItem>
                      <SelectItem value="admin">Administrador</SelectItem>
                    </SelectContent>
                  </Select>
                </td>
                <td className="p-3 font-mono text-xs">{u.created_at?.slice(0, 10)}</td>
                <td className="p-3 text-right">
                  <Button size="sm" variant="outline" onClick={() => { setPwdUser(u); setPwdVal(""); }} data-testid={`reset-pwd-${u.id}`}><KeyRound className="w-3 h-3 mr-1" />Redefinir senha</Button>
                  {u.id !== me?.id && <Button size="icon" variant="ghost" onClick={() => remove(u)}><Trash2 className="w-4 h-4 text-red-600" /></Button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={!!pwdUser} onOpenChange={(v) => !v && setPwdUser(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Redefinir senha de {pwdUser?.email}</DialogTitle></DialogHeader>
          <form onSubmit={resetPwd} className="space-y-3">
            <div><Label>Nova senha</Label><Input type="password" required minLength={6} value={pwdVal} onChange={(e) => setPwdVal(e.target.value)} /></div>
            <Button type="submit" className="btn-terra w-full rounded-xl"><ShieldCheck className="w-4 h-4 mr-1" />Salvar</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
