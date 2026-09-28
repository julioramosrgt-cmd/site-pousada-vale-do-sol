import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Eye, EyeOff, ArrowLeft } from "lucide-react";

export default function AdminLogin() {
  const [email, setEmail] = useState("admin@pousada.com");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const nav = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      toast.success("Bem-vindo!");
      nav("/admin");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Falha no login");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[color:var(--pousada-bg)] px-4 paper-grain">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-warm border border-stone-200/70">
        <Link to="/" className="inline-flex items-center gap-1 text-sm text-stone-500 hover:text-stone-800 mb-4"><ArrowLeft className="w-4 h-4" /> Voltar ao site</Link>
        <span className="text-xs uppercase tracking-widest text-amber-800/70">Painel do anfitrião</span>
        <h1 className="font-serif text-3xl mt-1">Entrar</h1>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <div>
            <Label>E-mail</Label>
            <Input data-testid="login-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <Label>Senha</Label>
            <div className="relative">
              <Input data-testid="login-password" type={show ? "text" : "password"} required value={password} onChange={(e) => setPassword(e.target.value)} />
              <button type="button" onClick={() => setShow((s) => !s)} className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-700">
                {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <Button data-testid="login-submit" type="submit" disabled={loading} className="btn-terra w-full rounded-xl h-11">{loading ? "Entrando..." : "Entrar"}</Button>
        </form>
        <p className="text-xs text-stone-500 mt-4">Senha padrão: <span className="font-mono">pousada2024</span>. Altere após o primeiro login.</p>
      </div>
    </div>
  );
}
