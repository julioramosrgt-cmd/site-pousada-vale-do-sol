import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/apiClient";
import { Copy, MapPin, Mail, Phone, Instagram, Facebook, MessageCircle, Clock, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";

export default function PublicSite() {
  const [settings, setSettings] = useState(null);
  const [gallery, setGallery] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [preview, setPreview] = useState(null);

  useEffect(() => {
    Promise.all([
      api.get("/public/settings"),
      api.get("/public/gallery"),
      api.get("/public/rooms"),
    ]).then(([s, g, r]) => { setSettings(s.data); setGallery(g.data); setRooms(r.data); });
  }, []);

  if (!settings) return <div className="p-10">Carregando...</div>;

  const wa = (settings.whatsapp || "").replace(/\D/g, "");
  const waLink = wa ? `https://wa.me/${wa}` : "#";

  const copyPix = async () => {
    try { await navigator.clipboard.writeText(settings.pix_key || ""); toast.success("Chave PIX copiada!"); }
    catch { toast.error("Não foi possível copiar"); }
  };

  const hero = settings.cover_image || "https://images.unsplash.com/photo-1683914791856-040e5de792b3?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NzV8MHwxfHNlYXJjaHszfHxib3V0aXF1ZSUyMGhvdGVsJTIwdHJvcGljYWx8ZW58MHx8fHwxNzkwNTU0NTkwfDA&ixlib=rb-4.1.0&q=85";

  return (
    <div className="min-h-screen bg-[color:var(--pousada-bg)]" data-testid="public-site">
      {/* Nav */}
      <nav className="sticky top-0 z-40 backdrop-blur-md bg-white/70 border-b border-stone-200/70">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="font-serif text-xl text-stone-900" data-testid="brand-name">{settings.name}</div>
          <div className="flex items-center gap-3 text-sm">
            <a href="#galeria" className="hidden sm:inline text-stone-700 hover:text-stone-900">Galeria</a>
            <a href="#contato" className="hidden sm:inline text-stone-700 hover:text-stone-900">Contato</a>
            <Link to="/reservar" data-testid="btn-reserve-now" className="btn-terra rounded-xl px-4 py-2 text-sm font-medium inline-flex items-center gap-1">
              Reservar <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <header className="relative">
        <div className="relative h-[62vh] min-h-[420px] overflow-hidden">
          <img src={hero} alt="capa" className="absolute inset-0 w-full h-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-b from-black/20 via-black/30 to-black/60" />
          <div className="relative z-10 max-w-4xl mx-auto px-6 h-full flex flex-col justify-end pb-14">
            <span className="uppercase tracking-[0.28em] text-xs text-amber-200 mb-3">Bem-vindo</span>
            <h1 className="font-serif text-4xl sm:text-6xl text-white leading-tight">{settings.name}</h1>
            {settings.tagline && <p className="text-white/90 mt-3 max-w-2xl">{settings.tagline}</p>}
            <div className="mt-6 flex flex-wrap gap-3">
              <Link to="/reservar" data-testid="hero-reserve" className="btn-terra rounded-xl px-6 py-3 font-medium">Fazer Pré-reserva</Link>
              <a href={waLink} target="_blank" rel="noreferrer" data-testid="hero-whatsapp" className="rounded-xl px-6 py-3 bg-white/10 text-white border border-white/25 backdrop-blur-md hover:bg-white/20">Falar no WhatsApp</a>
            </div>
          </div>
        </div>
      </header>

      {/* Description */}
      <section className="max-w-5xl mx-auto px-6 py-14">
        <div className="grid md:grid-cols-3 gap-10">
          <div className="md:col-span-2">
            <h2 className="font-serif text-3xl text-stone-900">Sobre a pousada</h2>
            <p className="text-stone-700 mt-4 leading-relaxed whitespace-pre-line" data-testid="pousada-description">{settings.description || "Uma experiência de hospedagem acolhedora e memorável."}</p>
          </div>
          <div className="rounded-2xl bg-white p-6 shadow-warm border border-stone-200/70">
            <h3 className="font-serif text-xl text-stone-900 mb-4">Horários</h3>
            <div className="flex items-center gap-3 py-2 border-b border-stone-100">
              <Clock className="w-4 h-4 text-[color:var(--pousada-terracotta)]" />
              <span className="text-stone-600 text-sm">Check-in</span>
              <span className="ml-auto font-mono">{settings.checkin_time || "14:00"}</span>
            </div>
            <div className="flex items-center gap-3 py-2">
              <Clock className="w-4 h-4 text-[color:var(--pousada-palm)]" />
              <span className="text-stone-600 text-sm">Check-out</span>
              <span className="ml-auto font-mono">{settings.checkout_time || "11:00"}</span>
            </div>
          </div>
        </div>
      </section>

      {/* Rooms */}
      {rooms.length > 0 && (
        <section className="max-w-6xl mx-auto px-6 py-8">
          <h2 className="font-serif text-3xl text-stone-900 mb-6">Acomodações</h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {rooms.map((r) => (
              <div key={r.id} data-testid={`room-card-${r.id}`} className="rounded-2xl overflow-hidden bg-white border border-stone-200/70 shadow-warm">
                {r.cover_image && <img src={r.cover_image} alt={r.name} className="h-44 w-full object-cover" />}
                <div className="p-5">
                  <div className="flex items-center justify-between">
                    <h3 className="font-serif text-xl">{r.name}</h3>
                    <span className="font-mono text-[color:var(--pousada-terracotta)]">R$ {Number(r.daily_rate || 0).toFixed(0)}</span>
                  </div>
                  <p className="text-stone-600 text-sm mt-1">{r.category} · {r.max_adults} adultos{r.max_children ? ` + ${r.max_children} crianças` : ""}</p>
                  {r.description && <p className="text-stone-600 text-sm mt-3 line-clamp-3">{r.description}</p>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Gallery */}
      <section id="galeria" className="max-w-6xl mx-auto px-6 py-14">
        <div className="flex items-end justify-between mb-6">
          <h2 className="font-serif text-3xl text-stone-900">Galeria</h2>
          <span className="text-xs uppercase tracking-widest text-amber-800/70">{gallery.length} fotos</span>
        </div>
        {gallery.length === 0 ? (
          <p className="text-stone-500">Ainda não há fotos publicadas.</p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {gallery.map((g) => (
              <button key={g.id} data-testid={`gallery-item-${g.id}`} onClick={() => setPreview(g)} className="group relative aspect-square overflow-hidden rounded-xl bg-stone-200">
                <img src={g.url} alt={g.caption || ""} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
              </button>
            ))}
          </div>
        )}
      </section>

      {/* Contact */}
      <section id="contato" className="bg-[color:var(--pousada-elev)] paper-grain py-14">
        <div className="max-w-5xl mx-auto px-6 grid md:grid-cols-2 gap-8">
          <div>
            <h2 className="font-serif text-3xl text-stone-900">Fale conosco</h2>
            <p className="text-stone-700 mt-3">Reservas, dúvidas e informações da estadia.</p>
            <div className="mt-6 space-y-3">
              {settings.email && <div className="flex items-center gap-3"><Mail className="w-4 h-4 text-[color:var(--pousada-terracotta)]" /><span data-testid="contact-email">{settings.email}</span></div>}
              {settings.whatsapp && <a href={waLink} target="_blank" rel="noreferrer" className="flex items-center gap-3 hover:text-[color:var(--pousada-palm)]" data-testid="contact-whatsapp"><Phone className="w-4 h-4 text-[color:var(--pousada-palm)]" /><span>{settings.whatsapp}</span></a>}
              {settings.address && <div className="flex items-center gap-3"><MapPin className="w-4 h-4 text-[color:var(--pousada-terracotta)]" /><span>{settings.address}</span></div>}
              <div className="flex items-center gap-4 pt-2">
                {settings.instagram && <a href={settings.instagram} target="_blank" rel="noreferrer" className="hover:text-[color:var(--pousada-terracotta)]"><Instagram className="w-5 h-5" /></a>}
                {settings.facebook && <a href={settings.facebook} target="_blank" rel="noreferrer" className="hover:text-[color:var(--pousada-terracotta)]"><Facebook className="w-5 h-5" /></a>}
              </div>
            </div>
          </div>
          <div className="rounded-2xl bg-white p-6 border border-stone-200/70 shadow-warm">
            <h3 className="font-serif text-xl text-stone-900">Chave PIX</h3>
            <p className="text-stone-500 text-sm mt-1">Pagamento de sinal ou diária</p>
            <div className="mt-4 rounded-xl bg-stone-50 border border-dashed border-stone-300 p-4 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-xs uppercase tracking-widest text-amber-800/70">{settings.pix_key_type || "chave"}</div>
                <div className="font-mono text-sm truncate" data-testid="pix-key">{settings.pix_key || "-"}</div>
              </div>
              <Button data-testid="btn-copy-pix" onClick={copyPix} variant="outline" className="rounded-xl"><Copy className="w-4 h-4 mr-1" />Copiar</Button>
            </div>
            <Link to="/reservar" className="btn-terra mt-5 inline-flex rounded-xl px-4 py-2 font-medium">Iniciar Pré-reserva</Link>
          </div>
        </div>
      </section>

      <footer className="py-8 text-center text-stone-500 text-sm">
        © {new Date().getFullYear()} {settings.name} · <Link to="/admin/login" className="hover:text-stone-800" data-testid="footer-admin-link">Painel</Link>
      </footer>

      {/* Floating WhatsApp */}
      {settings.whatsapp && (
        <a href={waLink} target="_blank" rel="noreferrer" data-testid="floating-whatsapp" className="fixed bottom-5 right-5 z-50 rounded-full bg-[#25D366] p-4 shadow-lg hover:scale-105 transition">
          <MessageCircle className="w-6 h-6 text-white" />
        </a>
      )}

      <Dialog open={!!preview} onOpenChange={() => setPreview(null)}>
        <DialogContent className="max-w-4xl bg-black/95 border-0 p-0">
          {preview && <img src={preview.url} alt="" className="w-full max-h-[85vh] object-contain" />}
        </DialogContent>
      </Dialog>
    </div>
  );
}
