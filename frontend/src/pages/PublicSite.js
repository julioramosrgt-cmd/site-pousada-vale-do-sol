import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/apiClient";
import { Copy, MapPin, Mail, Phone, Instagram, Facebook, MessageCircle, Clock, ArrowRight, Navigation, ExternalLink, ChevronLeft, ChevronRight, CreditCard } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";

const FALLBACK_HERO = "https://images.unsplash.com/photo-1683914791856-040e5de792b3?crop=entropy&cs=srgb&fm=jpg&w=1600&q=80";

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function HeroCarousel({ images, fallback }) {
  const items = images.length ? images : [{ id: "fallback", url: fallback }];
  const [order, setOrder] = useState(() => shuffle(items.map((_, i) => i)));
  const [idx, setIdx] = useState(0);

  useEffect(() => { setOrder(shuffle(items.map((_, i) => i))); setIdx(0); /* eslint-disable-next-line */ }, [images.length]);

  useEffect(() => {
    if (items.length < 2) return;
    const id = setInterval(() => setIdx((i) => (i + 1) % order.length), 6000);
    return () => clearInterval(id);
  }, [order.length, items.length]);

  const active = items[order[idx] ?? 0];

  return (
    <div className="absolute inset-0" data-testid="hero-carousel">
      {items.map((it, i) => (
        <img
          key={it.id}
          src={it.url}
          alt=""
          className="absolute inset-0 w-full h-full object-cover transition-opacity duration-1000"
          style={{ opacity: items[order[idx]]?.id === it.id ? 1 : 0 }}
        />
      ))}
      <div className="absolute inset-0 bg-gradient-to-b from-black/25 via-black/35 to-black/70" />
      {items.length > 1 && (
        <div className="absolute bottom-5 left-1/2 -translate-x-1/2 z-20 flex gap-2">
          {order.map((_, i) => (
            <button
              key={i}
              onClick={() => setIdx(i)}
              data-testid={`hero-dot-${i}`}
              className={`h-2 rounded-full transition-all duration-300 ${i === idx ? "w-8 bg-white" : "w-2 bg-white/60 hover:bg-white/90"}`}
              aria-label={`Foto ${i + 1}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

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

  const heroImages = useMemo(() => {
    if (gallery && gallery.length) return gallery.map((g) => ({ id: g.id, url: g.url }));
    if (settings?.cover_image) return [{ id: "cover", url: settings.cover_image }];
    return [];
  }, [gallery, settings?.cover_image]);

  if (!settings) return <div className="p-10">Carregando...</div>;

  const wa = (settings.whatsapp || "").replace(/\D/g, "");
  const waLink = wa ? `https://wa.me/${wa}` : "#";
  const payLinkMsg = encodeURIComponent("Olá! Gostaria de solicitar um link de pagamento via cartão de crédito para a minha reserva na Pousada Vale do Sol.");
  const payLink = wa ? `https://wa.me/${wa}?text=${payLinkMsg}` : "#";
  const tel = (settings.phone || settings.whatsapp || "").replace(/\D/g, "");
  const telLink = tel ? `tel:+${tel}` : "#";

  const copyPix = async () => {
    try { await navigator.clipboard.writeText(settings.pix_key || ""); toast.success("Chave PIX copiada!"); }
    catch { toast.error("Não foi possível copiar"); }
  };

  const addr = encodeURIComponent(settings.address || settings.name || "");
  const hasCoords = settings.latitude && settings.longitude;
  const mapsEmbed = hasCoords
    ? `https://www.google.com/maps?q=${settings.latitude},${settings.longitude}&hl=pt-BR&z=16&output=embed`
    : `https://www.google.com/maps?q=${addr}&hl=pt-BR&z=15&output=embed`;
  const googleDir = hasCoords
    ? `https://www.google.com/maps/dir/?api=1&destination=${settings.latitude},${settings.longitude}`
    : `https://www.google.com/maps/dir/?api=1&destination=${addr}`;
  const wazeDir = hasCoords
    ? `https://waze.com/ul?ll=${settings.latitude},${settings.longitude}&navigate=yes`
    : `https://waze.com/ul?q=${addr}&navigate=yes`;

  return (
    <div className="min-h-screen bg-[color:var(--pousada-bg)]" data-testid="public-site">
      {/* Nav */}
      <nav className="sticky top-0 z-40 backdrop-blur-md bg-white/80 border-b border-stone-200/70">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            {settings.logo_url ? (
              <img src={settings.logo_url} alt={settings.name} className="h-10 w-10 rounded-full object-cover border border-stone-200" data-testid="brand-logo" />
            ) : (
              <div className="h-10 w-10 rounded-full bg-[color:var(--pousada-terracotta)] text-white flex items-center justify-center font-serif">{(settings.name || "P").charAt(0)}</div>
            )}
            <div className="font-serif text-xl text-stone-900 truncate" data-testid="brand-name">{settings.name}</div>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <a href="#galeria" className="hidden sm:inline text-stone-700 hover:text-stone-900">Galeria</a>
            <a href="#localizacao" className="hidden sm:inline text-stone-700 hover:text-stone-900">Como chegar</a>
            <a href="#pagamento" data-testid="nav-pagamento" className="hidden sm:inline text-stone-700 hover:text-stone-900">Pagamento</a>
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
          <HeroCarousel images={heroImages} fallback={FALLBACK_HERO} />
          <div className="relative z-10 max-w-4xl mx-auto px-6 h-full flex flex-col justify-end pb-14">
            <span className="uppercase tracking-[0.28em] text-xs text-amber-200 mb-3">Bem-vindo</span>
            <h1 className="font-serif text-4xl sm:text-6xl text-white leading-tight drop-shadow-lg">{settings.name}</h1>
            {settings.tagline && <p className="text-white/90 mt-3 max-w-2xl">{settings.tagline}</p>}
            <div className="mt-6 flex flex-wrap gap-3">
              <Link to="/reservar" data-testid="hero-reserve" className="btn-terra rounded-xl px-6 py-3 font-medium">Fazer Pré-reserva</Link>
              <a href={waLink} target="_blank" rel="noreferrer" data-testid="hero-whatsapp" className="rounded-xl px-6 py-3 bg-white/10 text-white border border-white/25 backdrop-blur-md hover:bg-white/20">Falar no WhatsApp</a>
            </div>
          </div>
        </div>
      </header>

      {/* OTAs strip */}
      {(settings.airbnb_url || settings.booking_url || settings.triplar_url) && (
        <section className="bg-white border-b border-stone-200/70">
          <div className="max-w-5xl mx-auto px-6 py-4 flex flex-wrap items-center justify-center gap-3 text-sm">
            <span className="text-stone-500 mr-2">Reserve também em:</span>
            {settings.airbnb_url && <a href={settings.airbnb_url} target="_blank" rel="noreferrer" data-testid="ota-airbnb" className="rounded-full px-4 py-1.5 bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 inline-flex items-center gap-1"><ExternalLink className="w-3 h-3" />Airbnb</a>}
            {settings.booking_url && <a href={settings.booking_url} target="_blank" rel="noreferrer" data-testid="ota-booking" className="rounded-full px-4 py-1.5 bg-sky-50 text-sky-700 border border-sky-200 hover:bg-sky-100 inline-flex items-center gap-1"><ExternalLink className="w-3 h-3" />Booking.com</a>}
            {settings.triplar_url && <a href={settings.triplar_url} target="_blank" rel="noreferrer" data-testid="ota-triplar" className="rounded-full px-4 py-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 inline-flex items-center gap-1"><ExternalLink className="w-3 h-3" />TripLar</a>}
          </div>
        </section>
      )}

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
                    <div className="text-right">
                      <span className="font-mono text-[color:var(--pousada-terracotta)]">R$ {Number(r.daily_rate || 0).toFixed(0)}</span>
                      <div className="text-[10px] uppercase tracking-widest text-stone-500">{r.rate_per_guest ? "por hóspede/noite" : "por diária"}</div>
                    </div>
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

      {/* Location & Map */}
      <section id="localizacao" className="bg-[color:var(--pousada-elev)] paper-grain py-14">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-6">
            <div>
              <span className="text-xs uppercase tracking-widest text-amber-800/70">Localização</span>
              <h2 className="font-serif text-3xl text-stone-900">Como chegar</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              <a href={googleDir} target="_blank" rel="noreferrer" data-testid="btn-google-route" className="btn-terra rounded-xl px-4 py-2 text-sm inline-flex items-center gap-1"><Navigation className="w-4 h-4" />Rota Google Maps</a>
              <a href={wazeDir} target="_blank" rel="noreferrer" data-testid="btn-waze-route" className="rounded-xl px-4 py-2 text-sm inline-flex items-center gap-1 bg-[#33CCFF] text-white hover:bg-[#00B7ED]"><Navigation className="w-4 h-4" />Rota Waze</a>
            </div>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            <div className="md:col-span-2 rounded-2xl overflow-hidden border border-stone-200 shadow-warm bg-white">
              {settings.address || hasCoords ? (
                <iframe
                  title="Mapa da pousada"
                  src={mapsEmbed}
                  className="w-full h-72 md:h-96"
                  loading="lazy"
                  referrerPolicy="no-referrer-when-downgrade"
                  data-testid="map-iframe"
                />
              ) : <div className="h-72 flex items-center justify-center text-stone-500">Configure o endereço no painel para exibir o mapa</div>}
            </div>
            <div className="rounded-2xl bg-white p-6 border border-stone-200/70 shadow-warm">
              <h3 className="font-serif text-xl text-stone-900 mb-3">Endereço</h3>
              <p className="text-stone-700 flex items-start gap-2" data-testid="full-address"><MapPin className="w-4 h-4 mt-0.5 text-[color:var(--pousada-terracotta)] shrink-0" />{settings.address || "Endereço a ser configurado"}</p>
              {tel && <a href={telLink} data-testid="phone-clickable" className="mt-4 flex items-center gap-2 hover:text-[color:var(--pousada-palm)]"><Phone className="w-4 h-4 text-[color:var(--pousada-palm)]" />{settings.phone || settings.whatsapp}</a>}
              {settings.whatsapp && <a href={waLink} target="_blank" rel="noreferrer" className="mt-2 flex items-center gap-2 hover:text-[color:var(--pousada-palm)]"><MessageCircle className="w-4 h-4 text-[#25D366]" />WhatsApp</a>}
            </div>
          </div>
        </div>
      </section>

      {/* Contact */}
      <section id="contato" className="max-w-5xl mx-auto px-6 py-14 grid md:grid-cols-2 gap-8">
        <div>
          <span className="text-xs uppercase tracking-widest text-amber-800/70">Contato</span>
          <h2 className="font-serif text-3xl text-stone-900">Fale conosco</h2>
          <p className="text-stone-700 mt-3">Reservas, dúvidas e informações da estadia.</p>
          <div className="mt-6 space-y-3">
            {settings.email && <a href={`mailto:${settings.email}`} className="flex items-center gap-3 hover:text-[color:var(--pousada-terracotta)]"><Mail className="w-4 h-4 text-[color:var(--pousada-terracotta)]" /><span data-testid="contact-email">{settings.email}</span></a>}
            {tel && <a href={telLink} className="flex items-center gap-3 hover:text-[color:var(--pousada-palm)]" data-testid="contact-phone"><Phone className="w-4 h-4 text-[color:var(--pousada-palm)]" /><span>{settings.phone || settings.whatsapp}</span></a>}
            {settings.whatsapp && <a href={waLink} target="_blank" rel="noreferrer" className="flex items-center gap-3 hover:text-[color:var(--pousada-palm)]" data-testid="contact-whatsapp"><MessageCircle className="w-4 h-4 text-[#25D366]" /><span>WhatsApp {settings.whatsapp}</span></a>}
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
      </section>

      {/* Payment Methods */}
      <section id="pagamento" className="bg-[color:var(--pousada-elev)] paper-grain py-14 border-t border-stone-200/70" data-testid="payment-methods-section">
        <div className="max-w-4xl mx-auto px-6">
          <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm p-6 sm:p-10">
            <div className="flex items-start gap-4">
              <div className="shrink-0 w-12 h-12 rounded-xl bg-[color:var(--pousada-terracotta)]/10 flex items-center justify-center">
                <CreditCard className="w-6 h-6 text-[color:var(--pousada-terracotta)]" />
              </div>
              <div className="flex-1">
                <span className="text-xs uppercase tracking-widest text-amber-800/70">Pagamento</span>
                <h2 className="font-serif text-3xl text-stone-900 mt-1">Formas de Pagamento</h2>
                <p className="text-stone-700 mt-3 leading-relaxed">
                  Aceitamos pagamentos por <strong>cartão de débito</strong> e <strong>cartão de crédito</strong>.
                  Se preferir pagar pelo cartão de crédito, clique no botão abaixo para solicitar o seu link de pagamento com segurança.
                </p>
                <div className="mt-5 flex items-center gap-3 flex-wrap" aria-label="Bandeiras aceitas" data-testid="payment-badges">
                  {/* Visa */}
                  <span title="Visa" className="inline-flex items-center justify-center h-9 w-14 rounded-md bg-white border border-stone-200 shadow-sm">
                    <svg viewBox="0 0 48 16" aria-hidden="true" className="h-4"><text x="0" y="13" fontFamily="Arial,Helvetica,sans-serif" fontWeight="900" fontStyle="italic" fontSize="16" fill="#1A1F71">VISA</text></svg>
                  </span>
                  {/* Mastercard */}
                  <span title="Mastercard" className="inline-flex items-center justify-center h-9 w-14 rounded-md bg-white border border-stone-200 shadow-sm">
                    <svg viewBox="0 0 36 22" aria-hidden="true" className="h-5">
                      <circle cx="14" cy="11" r="9" fill="#EB001B" />
                      <circle cx="22" cy="11" r="9" fill="#F79E1B" />
                      <path d="M18 4.5a9 9 0 0 1 0 13 9 9 0 0 1 0-13z" fill="#FF5F00" />
                    </svg>
                  </span>
                  {/* Elo */}
                  <span title="Elo" className="inline-flex items-center justify-center h-9 w-14 rounded-md bg-black border border-stone-900 shadow-sm">
                    <svg viewBox="0 0 48 20" aria-hidden="true" className="h-4">
                      <circle cx="10" cy="10" r="7" fill="none" stroke="#FFF200" strokeWidth="2.4" />
                      <circle cx="10" cy="10" r="2.4" fill="#EC1C24" />
                      <text x="20" y="14" fontFamily="Arial,Helvetica,sans-serif" fontWeight="900" fontSize="12" fill="#FFF">elo</text>
                    </svg>
                  </span>
                </div>
                {wa ? (
                  <a
                    href={payLink}
                    target="_blank"
                    rel="noreferrer"
                    data-testid="btn-request-payment-link"
                    className="mt-6 inline-flex items-center gap-2 rounded-xl bg-[#25D366] hover:bg-[#1ea856] text-white px-5 py-3 font-medium shadow-warm transition hover:scale-[1.02]"
                  >
                    <MessageCircle className="w-5 h-5" />
                    Solicitar Link de Pagamento via WhatsApp
                  </a>
                ) : (
                  <p className="mt-6 text-sm text-stone-500">WhatsApp indisponível no momento — fale conosco pelos canais acima.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      <footer className="py-8 text-center text-stone-500 text-sm border-t border-stone-200/60 bg-white">
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
