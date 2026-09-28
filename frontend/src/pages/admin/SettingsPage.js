import { useEffect, useRef, useState } from "react";
import { api, API } from "@/lib/apiClient";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Save, Trash2, Upload, ImagePlus } from "lucide-react";

export default function SettingsPage() {
  const [s, setS] = useState(null);
  const [gallery, setGallery] = useState([]);
  const [newUrl, setNewUrl] = useState("");
  const fileRef = useRef(null);
  const coverRef = useRef(null);

  const load = async () => {
    const [sr, gr] = await Promise.all([api.get("/settings"), api.get("/gallery")]);
    setS(sr.data); setGallery(gr.data);
  };
  useEffect(() => { load(); }, []);

  const upd = (k, v) => setS((x) => ({ ...x, [k]: v }));

  const saveSettings = async (e) => {
    e.preventDefault();
    await api.put("/settings", s);
    toast.success("Configurações salvas");
  };

  const addUrl = async () => {
    if (!newUrl.trim()) return;
    await api.post("/gallery", { url: newUrl.trim(), sort_order: gallery.length });
    setNewUrl(""); toast.success("Foto adicionada"); load();
  };

  const upload = async (e, target) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    try {
      const r = await api.post("/uploads", fd, { headers: { "Content-Type": "multipart/form-data" } });
      const url = `${API}/files/${r.data.path}`;
      if (target === "gallery") {
        await api.post("/gallery", { url, sort_order: gallery.length });
        toast.success("Foto enviada"); load();
      } else if (target === "cover") {
        setS((x) => ({ ...x, cover_image: url }));
        toast.success("Capa enviada. Clique em Salvar.");
      }
    } catch { toast.error("Falha no upload"); }
    e.target.value = "";
  };

  const removeItem = async (id) => {
    await api.delete(`/gallery/${id}`);
    toast.success("Removida"); load();
  };

  if (!s) return <p>Carregando...</p>;

  return (
    <div className="space-y-8">
      <div>
        <span className="text-xs uppercase tracking-widest text-amber-800/70">Site público</span>
        <h1 className="font-serif text-3xl sm:text-4xl">Site & Galeria</h1>
      </div>

      <form onSubmit={saveSettings} className="rounded-2xl bg-white border border-stone-200/70 shadow-warm p-6 grid sm:grid-cols-2 gap-4">
        <div className="sm:col-span-2 grid sm:grid-cols-2 gap-4">
          <div><Label>Nome da pousada</Label><Input value={s.name} onChange={(e) => upd("name", e.target.value)} data-testid="set-name" /></div>
          <div><Label>Slogan / tagline</Label><Input value={s.tagline} onChange={(e) => upd("tagline", e.target.value)} /></div>
        </div>
        <div className="sm:col-span-2"><Label>Descrição</Label><Textarea rows={4} value={s.description} onChange={(e) => upd("description", e.target.value)} /></div>
        <div><Label>E-mail</Label><Input value={s.email} onChange={(e) => upd("email", e.target.value)} data-testid="set-email" /></div>
        <div><Label>WhatsApp (com DDI, ex. 5511999999999)</Label><Input value={s.whatsapp} onChange={(e) => upd("whatsapp", e.target.value)} data-testid="set-whatsapp" /></div>
        <div><Label>Chave PIX</Label><Input value={s.pix_key} onChange={(e) => upd("pix_key", e.target.value)} data-testid="set-pix" /></div>
        <div>
          <Label>Tipo da chave</Label>
          <Select value={s.pix_key_type || ""} onValueChange={(v) => upd("pix_key_type", v)}>
            <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="cpf">CPF</SelectItem>
              <SelectItem value="cnpj">CNPJ</SelectItem>
              <SelectItem value="email">E-mail</SelectItem>
              <SelectItem value="phone">Telefone</SelectItem>
              <SelectItem value="random">Aleatória</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div><Label>Endereço</Label><Input value={s.address} onChange={(e) => upd("address", e.target.value)} /></div>
        <div><Label>Check-in</Label><Input type="time" value={s.checkin_time} onChange={(e) => upd("checkin_time", e.target.value)} /></div>
        <div><Label>Check-out</Label><Input type="time" value={s.checkout_time} onChange={(e) => upd("checkout_time", e.target.value)} /></div>
        <div><Label>Instagram (URL)</Label><Input value={s.instagram} onChange={(e) => upd("instagram", e.target.value)} /></div>
        <div><Label>Facebook (URL)</Label><Input value={s.facebook} onChange={(e) => upd("facebook", e.target.value)} /></div>
        <div className="sm:col-span-2">
          <Label>Foto de capa</Label>
          <div className="flex gap-2 items-center">
            <Input value={s.cover_image} onChange={(e) => upd("cover_image", e.target.value)} placeholder="URL da imagem" />
            <input ref={coverRef} type="file" accept="image/*" hidden onChange={(e) => upload(e, "cover")} />
            <Button type="button" variant="outline" onClick={() => coverRef.current?.click()} data-testid="btn-upload-cover"><Upload className="w-4 h-4 mr-1" />Enviar arquivo</Button>
          </div>
          {s.cover_image && <img src={s.cover_image} alt="capa" className="mt-3 h-32 rounded-xl object-cover" />}
        </div>
        <div className="sm:col-span-2"><Label>Políticas / regras</Label><Textarea rows={3} value={s.policies} onChange={(e) => upd("policies", e.target.value)} /></div>
        <div className="sm:col-span-2"><Button type="submit" className="btn-terra rounded-xl" data-testid="btn-save-settings"><Save className="w-4 h-4 mr-1" />Salvar alterações</Button></div>
      </form>

      <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm p-6">
        <h3 className="font-serif text-xl mb-3">Galeria</h3>
        <div className="flex flex-col sm:flex-row gap-2 mb-4">
          <Input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="Cole uma URL de imagem" data-testid="gallery-url-input" />
          <Button type="button" onClick={addUrl} className="btn-terra rounded-xl" data-testid="gallery-add-url"><ImagePlus className="w-4 h-4 mr-1" />Adicionar URL</Button>
          <input ref={fileRef} type="file" accept="image/*" hidden onChange={(e) => upload(e, "gallery")} />
          <Button type="button" variant="outline" onClick={() => fileRef.current?.click()} data-testid="gallery-upload-file"><Upload className="w-4 h-4 mr-1" />Enviar arquivo</Button>
        </div>
        {gallery.length === 0 ? <p className="text-stone-500">Sem fotos ainda.</p> : (
          <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 gap-3">
            {gallery.map((g) => (
              <div key={g.id} className="relative group aspect-square rounded-xl overflow-hidden bg-stone-200" data-testid={`gallery-tile-${g.id}`}>
                <img src={g.url} alt="" className="w-full h-full object-cover" />
                <button onClick={() => removeItem(g.id)} className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 bg-white/90 rounded p-1"><Trash2 className="w-3 h-3 text-red-600" /></button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
