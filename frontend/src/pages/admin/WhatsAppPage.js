import { useEffect, useState } from "react";
import { api } from "@/lib/apiClient";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Copy, Plus, Trash2, Save, QrCode } from "lucide-react";

const TAGS = ["{nome}", "{quarto}", "{checkin}", "{checkout}", "{valor}", "{chave_pix}", "{pix_copia_cola}", "{checkin_time}", "{endereco}", "{whatsapp}"];

export default function WhatsAppPage() {
  const [rows, setRows] = useState([]);
  const [settings, setSettings] = useState({});
  const [vars, setVars] = useState({ nome: "", quarto: "", checkin: "", checkout: "", valor: "" });
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ title: "", body: "" });
  const [pix, setPix] = useState(null);
  const [genLoading, setGenLoading] = useState(false);

  const load = async () => {
    const [t, s] = await Promise.all([api.get("/whatsapp/templates"), api.get("/settings")]);
    setRows(t.data); setSettings(s.data);
  };
  useEffect(() => { load(); }, []);

  const startNew = () => { setEditing(null); setForm({ title: "", body: "" }); };
  const startEdit = (t) => { setEditing(t); setForm({ title: t.title, body: t.body }); };

  const save = async (e) => {
    e.preventDefault();
    if (editing) await api.put(`/whatsapp/templates/${editing.id}`, form);
    else await api.post("/whatsapp/templates", form);
    toast.success("Template salvo");
    setEditing(null); setForm({ title: "", body: "" });
    load();
  };

  const remove = async (t) => {
    if (!window.confirm("Excluir template?")) return;
    await api.delete(`/whatsapp/templates/${t.id}`); load();
  };

  const render = (body) => {
    const context = {
      ...vars,
      chave_pix: settings.pix_key || "",
      pix_copia_cola: pix?.brcode || "",
      checkin_time: settings.checkin_time || "",
      endereco: settings.address || "",
      whatsapp: settings.whatsapp || "",
    };
    let out = body;
    Object.entries(context).forEach(([k, v]) => { out = out.split(`{${k}}`).join(v || `{${k}}`); });
    return out;
  };

  const genPix = async () => {
    setGenLoading(true);
    try {
      const amount = vars.valor ? parseFloat(vars.valor) : null;
      const r = await api.post("/pix/brcode", { amount });
      setPix(r.data);
      toast.success("PIX Copia-e-Cola gerado");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Configure a chave PIX em Site & Galeria");
    } finally { setGenLoading(false); }
  };

  const copy = async (text) => { await navigator.clipboard.writeText(text); toast.success("Copiado"); };
  const openWhatsApp = (text) => {
    const wa = (settings.whatsapp || "").replace(/\D/g, "");
    window.open(`https://wa.me/${wa}?text=${encodeURIComponent(text)}`, "_blank");
  };

  return (
    <div>
      <div className="mb-6">
        <span className="text-xs uppercase tracking-widest text-amber-800/70">Comunicação</span>
        <h1 className="font-serif text-3xl sm:text-4xl">Templates WhatsApp</h1>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-serif text-xl">Meus templates</h3>
            <Button size="sm" onClick={startNew} className="btn-terra rounded-xl"><Plus className="w-3 h-3 mr-1" />Novo</Button>
          </div>
          <ul className="space-y-2">
            {rows.map((t) => (
              <li key={t.id} className={`p-3 rounded-xl border cursor-pointer ${editing?.id === t.id ? "border-[color:var(--pousada-terracotta)] bg-orange-50/40" : "border-stone-200 hover:bg-stone-50"}`} onClick={() => startEdit(t)} data-testid={`tpl-${t.id}`}>
                <div className="flex items-center justify-between">
                  <div className="font-medium">{t.title}</div>
                  <button onClick={(e) => { e.stopPropagation(); remove(t); }}><Trash2 className="w-4 h-4 text-red-600" /></button>
                </div>
                <div className="text-xs text-stone-500 line-clamp-2 mt-1">{t.body}</div>
              </li>
            ))}
          </ul>

          <form onSubmit={save} className="mt-6 space-y-3 border-t border-stone-100 pt-4">
            <div><Label>Título</Label><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required data-testid="tpl-title" /></div>
            <div>
              <Label>Mensagem</Label>
              <Textarea rows={5} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} required data-testid="tpl-body" />
              <div className="mt-2 flex flex-wrap gap-1">
                {TAGS.map((t) => (
                  <button key={t} type="button" onClick={() => setForm((f) => ({ ...f, body: f.body + " " + t }))} className="text-xs px-2 py-1 rounded-full bg-stone-100 hover:bg-stone-200">{t}</button>
                ))}
              </div>
            </div>
            <Button type="submit" className="btn-terra rounded-xl"><Save className="w-4 h-4 mr-1" />{editing ? "Atualizar" : "Criar"}</Button>
          </form>
        </div>

        <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm p-6">
          <h3 className="font-serif text-xl mb-3">Pré-visualizar</h3>
          <div className="grid grid-cols-2 gap-3 mb-4">
            {["nome", "quarto", "checkin", "checkout", "valor"].map((k) => (
              <div key={k}><Label className="capitalize">{k}</Label><Input value={vars[k]} onChange={(e) => setVars({ ...vars, [k]: e.target.value })} /></div>
            ))}
          </div>

          <div className="rounded-xl border border-dashed border-stone-300 p-3 mb-4 bg-stone-50/60">
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="text-xs uppercase tracking-widest text-amber-800/70">PIX Copia-e-Cola</div>
                <div className="text-xs text-stone-500">Cole `{`{pix_copia_cola}`}` no template para incluir no envio</div>
              </div>
              <Button size="sm" variant="outline" onClick={genPix} disabled={genLoading} data-testid="btn-gen-pix">
                <QrCode className="w-4 h-4 mr-1" />{genLoading ? "Gerando..." : "Gerar QR + código"}
              </Button>
            </div>
            {pix && (
              <div className="mt-3 flex flex-col sm:flex-row gap-4 items-start">
                <img src={pix.qr_png_base64} alt="QR PIX" className="w-40 h-40 rounded-lg border border-stone-200" data-testid="pix-qr-img" />
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-xs break-all bg-white border border-stone-200 rounded-lg p-3" data-testid="pix-brcode">{pix.brcode}</div>
                  <div className="mt-2 flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => { navigator.clipboard.writeText(pix.brcode); toast.success("Copia-e-Cola copiado"); }}><Copy className="w-3 h-3 mr-1" />Copiar código</Button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {editing || form.body ? (
            <div className="rounded-2xl bg-[#DCF8C6] p-4 whitespace-pre-line font-sans text-stone-800 shadow-inner break-words" data-testid="tpl-preview">
              {render(form.body)}
            </div>
          ) : <p className="text-stone-500">Selecione ou crie um template para pré-visualizar.</p>}
          <div className="mt-4 flex gap-2">
            <Button variant="outline" onClick={() => copy(render(form.body))} disabled={!form.body}><Copy className="w-4 h-4 mr-1" />Copiar</Button>
            <Button className="btn-terra rounded-xl" onClick={() => openWhatsApp(render(form.body))} disabled={!form.body}>Abrir no WhatsApp</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
