import { useState } from "react";
import { api } from "@/lib/apiClient";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { KeyRound } from "lucide-react";

export default function AccountPage() {
  const { user } = useAuth();
  const [cur, setCur] = useState(""); const [np, setNp] = useState(""); const [np2, setNp2] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (np.length < 6) return toast.error("A nova senha precisa ter ao menos 6 caracteres");
    if (np !== np2) return toast.error("As senhas não conferem");
    setSaving(true);
    try {
      await api.post("/auth/change-password", { current_password: cur, new_password: np });
      toast.success("Senha alterada");
      setCur(""); setNp(""); setNp2("");
    } catch (e) { toast.error(e?.response?.data?.detail || "Erro"); }
    finally { setSaving(false); }
  };

  return (
    <div>
      <div className="mb-6">
        <span className="text-xs uppercase tracking-widest text-amber-800/70">Segurança</span>
        <h1 className="font-serif text-3xl sm:text-4xl">Conta</h1>
      </div>
      <div className="max-w-lg rounded-2xl bg-white border border-stone-200/70 shadow-warm p-6">
        <p className="text-stone-600">Usuário: <span className="font-mono">{user?.email}</span></p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <div><Label>Senha atual</Label><Input type="password" required value={cur} onChange={(e) => setCur(e.target.value)} data-testid="pwd-cur" /></div>
          <div><Label>Nova senha</Label><Input type="password" required value={np} onChange={(e) => setNp(e.target.value)} data-testid="pwd-new" /></div>
          <div><Label>Confirme a nova senha</Label><Input type="password" required value={np2} onChange={(e) => setNp2(e.target.value)} data-testid="pwd-new2" /></div>
          <Button type="submit" disabled={saving} className="btn-terra rounded-xl" data-testid="pwd-submit"><KeyRound className="w-4 h-4 mr-1" />{saving ? "Salvando..." : "Alterar senha"}</Button>
        </form>
      </div>
    </div>
  );
}
