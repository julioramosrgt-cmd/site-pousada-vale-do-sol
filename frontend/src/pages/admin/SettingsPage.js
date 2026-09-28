import { useEffect, useRef, useState } from "react";
import { api, API } from "@/lib/apiClient";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Save, Trash2, Upload, ImagePlus, X, QrCode, Copy, Download } from "lucide-react";

export default function SettingsPage() {
  const [s, setS] = useState(null);
  const [gallery, setGallery] = useState([]);
  const [newUrl, setNewUrl] = useState("");
  const [qr, setQr] = useState(null);
  const fileRef = useRef(null);
  const coverRef = useRef(null);
  const logoRef = useRef(null);

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
      } else if (target === "logo") {
        setS((x) => ({ ...x, logo_url: url }));
        toast.success("Logo enviada. Clique em Salvar.");
      }
    } catch { toast.error("Falha no upload"); }
    e.target.value = "";
  };

  const removeItem = async (id) => {
    await api.delete(`/gallery/${id}`);
    toast.success("Removida"); load();
  };

  const publicReserveUrl = `${window.location.origin}/reservar`;
  const genQR = async () => {
    try {
      const r = await api.post("/qr/link", { url: publicReserveUrl });
      setQr(r.data);
      toast.success("QR gerado");
    } catch { toast.error("Falha ao gerar QR"); }
  };
  const downloadQR = () => {
    if (!qr) return;
    const a = document.createElement("a");
    a.href = qr.qr_png_base64;
    a.download = `qr-reservar-${(s?.name || "pousada").toLowerCase().replace(/\s+/g, "-")}.png`;
    a.click();
  };

  if (!s) return <p>Carregando...</p>;

  return (
    <div className="space-y-8">
      <div>
        <span className="text-xs uppercase tracking-widest text-amber-800/70">Site público</span>
        <h1 className="font-serif text-3xl sm:text-4xl">Site & Galeria</h1>
      </div>

      {/* Logo */}
      <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm p-6">
        <h3 className="font-serif text-xl mb-2">Logomarca</h3>
        <p className="text-sm text-stone-500 mb-4">Aparece no topo do site público e do painel.</p>
        <div className="flex items-center gap-6 flex-wrap">
          {s.logo_url ? (
            <div className="relative">
              <img src={s.logo_url} alt="logo" className="h-24 w-24 rounded-full object-cover border border-stone-300" data-testid="logo-preview" />
              <button type="button" onClick={() => { upd("logo_url", ""); toast.info("Clique em Salvar para remover"); }} className="absolute -top-2 -right-2 bg-white border border-stone-300 rounded-full p-1"><X className="w-3 h-3" /></button>
            </div>
          ) : (
            <div className="h-24 w-24 rounded-full bg-stone-100 border-2 border-dashed border-stone-300 flex items-center justify-center text-stone-400 text-xs text-center">Sem logo</div>
          )}
          <div className="flex-1 min-w-[240px]">
            <Label>URL da logo (ou envie um arquivo)</Label>
            <div className="flex gap-2 mt-1">
              <Input value={s.logo_url || ""} onChange={(e) => upd("logo_url", e.target.value)} placeholder="https://..." data-testid="set-logo-url" />
              <input ref={logoRef} type="file" accept="image/*" hidden onChange={(e) => upload(e, "logo")} />
              <Button type="button" variant="outline" onClick={() => logoRef.current?.click()} data-testid="btn-upload-logo"><Upload className="w-4 h-4 mr-1" />Enviar</Button>
            </div>
            <Button type="button" onClick={saveSettings} className="btn-terra rounded-xl mt-3" data-testid="btn-save-logo"><Save className="w-4 h-4 mr-1" />Salvar logo</Button>
          </div>
        </div>
      </div>

      <form onSubmit={saveSettings} className="rounded-2xl bg-white border border-stone-200/70 shadow-warm p-6 grid sm:grid-cols-2 gap-4">
        <h3 className="sm:col-span-2 font-serif text-xl">Informações da pousada</h3>
        <div><Label>Nome da pousada</Label><Input value={s.name} onChange={(e) => upd("name", e.target.value)} data-testid="set-name" /></div>
        <div><Label>Slogan / tagline</Label><Input value={s.tagline} onChange={(e) => upd("tagline", e.target.value)} /></div>
        <div className="sm:col-span-2"><Label>Descrição</Label><Textarea rows={4} value={s.description} onChange={(e) => upd("description", e.target.value)} /></div>

        <h3 className="sm:col-span-2 font-serif text-xl pt-4 border-t border-stone-100">Contato</h3>
        <div><Label>E-mail</Label><Input value={s.email} onChange={(e) => upd("email", e.target.value)} data-testid="set-email" /></div>
        <div><Label>Telefone (clicável)</Label><Input value={s.phone || ""} onChange={(e) => upd("phone", e.target.value)} placeholder="+55 11 99999-9999" data-testid="set-phone" /></div>
        <div><Label>WhatsApp (só números com DDI)</Label><Input value={s.whatsapp} onChange={(e) => upd("whatsapp", e.target.value)} placeholder="5511999999999" data-testid="set-whatsapp" /></div>
        <div>
          <Label>Webhook WhatsApp (opcional — CallMeBot, n8n)</Label>
          <Input value={s.whatsapp_webhook_url || ""} onChange={(e) => upd("whatsapp_webhook_url", e.target.value)} placeholder="https://api.callmebot.com/whatsapp.php?phone=...&apikey=..." data-testid="set-wa-webhook" />
          <p className="text-xs text-stone-500 mt-1">Recebe notificação no seu WhatsApp a cada pré-reserva.</p>
        </div>

        <h3 className="sm:col-span-2 font-serif text-xl pt-4 border-t border-stone-100">PIX</h3>
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

        <h3 className="sm:col-span-2 font-serif text-xl pt-4 border-t border-stone-100">Localização</h3>
        <div className="sm:col-span-2"><Label>Endereço completo</Label><Input value={s.address} onChange={(e) => upd("address", e.target.value)} placeholder="Rua, número, bairro, cidade, UF, CEP" data-testid="set-address" /></div>
        <div><Label>Latitude (opcional)</Label><Input value={s.latitude || ""} onChange={(e) => upd("latitude", e.target.value)} placeholder="-23.5505" /></div>
        <div><Label>Longitude (opcional)</Label><Input value={s.longitude || ""} onChange={(e) => upd("longitude", e.target.value)} placeholder="-46.6333" /></div>

        <h3 className="sm:col-span-2 font-serif text-xl pt-4 border-t border-stone-100">Horários</h3>
        <div><Label>Check-in</Label><Input type="time" value={s.checkin_time} onChange={(e) => upd("checkin_time", e.target.value)} /></div>
        <div><Label>Check-out</Label><Input type="time" value={s.checkout_time} onChange={(e) => upd("checkout_time", e.target.value)} /></div>

        <h3 className="sm:col-span-2 font-serif text-xl pt-4 border-t border-stone-100">Redes & OTAs</h3>
        <div><Label>Instagram (URL)</Label><Input value={s.instagram} onChange={(e) => upd("instagram", e.target.value)} /></div>
        <div><Label>Facebook (URL)</Label><Input value={s.facebook} onChange={(e) => upd("facebook", e.target.value)} /></div>
        <div><Label>Airbnb (URL da listagem)</Label><Input value={s.airbnb_url || ""} onChange={(e) => upd("airbnb_url", e.target.value)} data-testid="set-airbnb" /></div>
        <div><Label>Booking.com (URL)</Label><Input value={s.booking_url || ""} onChange={(e) => upd("booking_url", e.target.value)} data-testid="set-booking" /></div>
        <div><Label>TripLar (URL)</Label><Input value={s.triplar_url || ""} onChange={(e) => upd("triplar_url", e.target.value)} data-testid="set-triplar" /></div>

        <h3 className="sm:col-span-2 font-serif text-xl pt-4 border-t border-stone-100">Foto de capa (fallback)</h3>
        <div className="sm:col-span-2">
          <p className="text-sm text-stone-500 mb-2">Usada quando a galeria estiver vazia. O carrossel do hero usa as fotos da galeria abaixo.</p>
          <div className="flex gap-2 items-center">
            <Input value={s.cover_image} onChange={(e) => upd("cover_image", e.target.value)} placeholder="URL da imagem" />
            <input ref={coverRef} type="file" accept="image/*" hidden onChange={(e) => upload(e, "cover")} />
            <Button type="button" variant="outline" onClick={() => coverRef.current?.click()} data-testid="btn-upload-cover"><Upload className="w-4 h-4 mr-1" />Enviar</Button>
          </div>
          {s.cover_image && <img src={s.cover_image} alt="capa" className="mt-3 h-32 rounded-xl object-cover" />}
        </div>
        <div className="sm:col-span-2"><Label>Políticas / regras</Label><Textarea rows={3} value={s.policies} onChange={(e) => upd("policies", e.target.value)} /></div>
        <div className="sm:col-span-2"><Button type="submit" className="btn-terra rounded-xl" data-testid="btn-save-settings"><Save className="w-4 h-4 mr-1" />Salvar alterações</Button></div>
      </form>

      <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm p-6">
        <h3 className="font-serif text-xl mb-1">QR Code para reservas</h3>
        <p className="text-sm text-stone-500 mb-4">Cole na porta da recepção, folder ou balcão. Ao escanear, o hóspede abre o formulário público no celular.</p>
        <div className="flex flex-col sm:flex-row gap-4 items-start">
          <div className="flex-1 min-w-0">
            <Label>URL do formulário</Label>
            <div className="flex gap-2 mt-1">
              <Input readOnly value={publicReserveUrl} className="font-mono text-xs" data-testid="qr-url" />
              <Button type="button" variant="outline" onClick={() => { navigator.clipboard.writeText(publicReserveUrl); toast.success("Link copiado"); }}><Copy className="w-4 h-4" /></Button>
            </div>
            <div className="mt-3 flex gap-2">
              <Button type="button" onClick={genQR} className="btn-terra rounded-xl" data-testid="btn-gen-qr"><QrCode className="w-4 h-4 mr-1" />Gerar QR</Button>
              {qr && <Button type="button" variant="outline" onClick={downloadQR} data-testid="btn-download-qr"><Download className="w-4 h-4 mr-1" />Baixar PNG</Button>}
            </div>
          </div>
          {qr && <img src={qr.qr_png_base64} alt="QR" className="w-40 h-40 rounded-xl border border-stone-200 bg-white p-2" data-testid="qr-img" />}
        </div>
      </div>

      <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm p-6">
        <h3 className="font-serif text-xl mb-1">Galeria (carrossel do site)</h3>
        <p className="text-sm text-stone-500 mb-4">O hero do site rotaciona automaticamente entre estas fotos (6s, ordem aleatória) com indicadores clicáveis.</p>
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
