import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Users } from "lucide-react";

export default function RhLogin() {
  const nav = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      nav("/rh");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Falha no login");
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50 p-4" data-testid="rh-login">
      <form onSubmit={onSubmit} className="w-full max-w-sm bg-white border border-stone-200 rounded-2xl shadow-warm p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[color:var(--pousada-palm)]/10 flex items-center justify-center">
            <Users className="w-5 h-5 text-[color:var(--pousada-palm)]" />
          </div>
          <div>
            <h1 className="font-serif text-xl text-stone-900">Gestão RH</h1>
            <p className="text-xs text-stone-500">Painel de recursos humanos</p>
          </div>
        </div>
        <div className="space-y-2">
          <Label>E-mail</Label>
          <Input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required data-testid="rh-login-email" />
        </div>
        <div className="space-y-2">
          <Label>Senha</Label>
          <Input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required data-testid="rh-login-password" />
        </div>
        <Button type="submit" disabled={busy} className="w-full btn-terra" data-testid="rh-login-submit">
          {busy ? "Entrando..." : "Entrar"}
        </Button>
        <div className="text-center text-xs text-stone-500">
          Acesso do colaborador? <Link to="/colaborador/login" className="text-[color:var(--pousada-palm)] hover:underline">clique aqui</Link>
        </div>
      </form>
    </div>
  );
}
