import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useColabAuth } from "@/lib/colabAuth";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { UserCircle2 } from "lucide-react";

export default function ColabLogin() {
  const nav = useNavigate();
  const { login } = useColabAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      nav("/colaborador");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Credenciais inválidas");
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50 p-4" data-testid="colab-login">
      <form onSubmit={submit} className="w-full max-w-sm bg-white border border-stone-200 rounded-2xl shadow-warm p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[color:var(--pousada-terracotta)]/10 flex items-center justify-center">
            <UserCircle2 className="w-5 h-5 text-[color:var(--pousada-terracotta)]" />
          </div>
          <div>
            <h1 className="font-serif text-xl text-stone-900">Portal do Colaborador</h1>
            <p className="text-xs text-stone-500">Pousada Vale do Sol</p>
          </div>
        </div>
        <div className="space-y-2"><Label>E-mail</Label>
          <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} data-testid="colab-login-email" /></div>
        <div className="space-y-2"><Label>Senha</Label>
          <Input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} data-testid="colab-login-password" /></div>
        <Button type="submit" disabled={busy} className="w-full btn-terra" data-testid="colab-login-submit">
          {busy ? "Entrando..." : "Entrar"}
        </Button>
        <div className="text-center text-xs text-stone-500">
          Sem acesso? Fale com o gestor para liberar seu login.
          <br /><Link to="/" className="text-[color:var(--pousada-palm)] hover:underline">Voltar ao site</Link>
        </div>
      </form>
    </div>
  );
}
