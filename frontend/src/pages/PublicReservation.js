import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, API } from "@/lib/apiClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ArrowLeft, CheckCircle2, Calculator, Upload, FileCheck2, X, AlertTriangle, PawPrint, CigaretteOff, Plus } from "lucide-react";

function brl(v) { return `R$ ${Number(v || 0).toFixed(2).replace(".", ",")}`; }
function nightsBetween(a, b) {
  if (!a || !b) return 0;
  const d = Math.round((new Date(b) - new Date(a)) / 86400000);
  return d > 0 ? d : 0;
}

const NumberField = ({ label, value, onChange, min = 0, testid }) => (
  <div className="flex items-center justify-between gap-3 py-2">
    <span className="text-sm text-stone-700">{label}</span>
    <div className="inline-flex items-center gap-2">
      <button type="button" className="w-8 h-8 rounded-full border border-stone-300 hover:bg-stone-50" onClick={() => onChange(Math.max(min, Number(value || 0) - 1))} data-testid={`${testid}-minus`}>−</button>
      <input type="number" min={min} value={value} onChange={(e) => onChange(e.target.value)} onBlur={(e) => onChange(Math.max(min, parseInt(e.target.value || String(min), 10)))} className="w-16 text-center rounded-lg border border-stone-300 h-9" data-testid={testid} />
      <button type="button" className="w-8 h-8 rounded-full border border-stone-300 hover:bg-stone-50" onClick={() => onChange(Number(value || 0) + 1)} data-testid={`${testid}-plus`}>+</button>
    </div>
  </div>
);

const SIZE_LABEL = { small: "Pequeno porte (20,7%)", medium: "Médio porte (27,6%)", large: "Grande porte (34,5%)" };

const normalize = (s) => (s || "")
  .toString()
  .toLowerCase()
  .normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "")
  .trim();

const PetRow = ({ pet, index, onChange, onRemove, allBreeds }) => {
  const [status, setStatus] = useState({ loading: false, matched: pet.matched, message: pet.message });
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const wrapRef = useRef(null);

  useEffect(() => {
    const breed = (pet.breed || "").trim();
    if (!breed) { setStatus({ loading: false, matched: null, message: null }); return; }
    setStatus((s) => ({ ...s, loading: true }));
    const t = setTimeout(() => {
      api.get(`/pets/classify?breed=${encodeURIComponent(breed)}&pet_type=${encodeURIComponent(pet.type || "")}`)
        .then((r) => {
          const auto = r.data;
          setStatus({ loading: false, matched: auto.matched, message: auto.message });
          // Only auto-apply size if user hasn't manually overridden
          if (!pet._manual) onChange(index, { ...pet, size: auto.size, matched: auto.matched, message: auto.message });
        })
        .catch(() => setStatus({ loading: false, matched: false, message: "Não foi possível classificar. Selecione o porte manualmente." }));
    }, 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line
  }, [pet.breed, pet.type]);

  // Close suggestions on outside click
  useEffect(() => {
    const h = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setShowSuggestions(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const suggestions = useMemo(() => {
    const q = normalize(pet.breed);
    if (!q || !allBreeds?.length) return [];
    return allBreeds.filter((b) => normalize(b).includes(q)).slice(0, 8);
  }, [pet.breed, allBreeds]);

  const pickSuggestion = (b) => {
    onChange(index, { ...pet, breed: b, _manual: false });
    setShowSuggestions(false);
    setHighlight(-1);
  };

  const onKeyDown = (e) => {
    if (!showSuggestions || suggestions.length === 0) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setHighlight((h) => Math.min(suggestions.length - 1, h + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setHighlight((h) => Math.max(0, h - 1)); }
    else if (e.key === "Enter" && highlight >= 0) { e.preventDefault(); pickSuggestion(suggestions[highlight]); }
    else if (e.key === "Escape") { setShowSuggestions(false); }
  };

  return (
    <div className="rounded-xl border border-stone-200 p-3" data-testid={`pet-row-${index}`}>
      <div className="grid sm:grid-cols-3 gap-2 mb-2">
        <div>
          <Label className="text-xs">Tipo *</Label>
          <Select value={pet.type} onValueChange={(v) => onChange(index, { ...pet, type: v })}>
            <SelectTrigger data-testid={`pet-type-${index}`}><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="cão">Cão</SelectItem>
              <SelectItem value="gato">Gato</SelectItem>
              <SelectItem value="outro">Outro</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="sm:col-span-2 relative" ref={wrapRef}>
          <Label className="text-xs">Raça *</Label>
          <Input
            value={pet.breed}
            required
            onChange={(e) => { onChange(index, { ...pet, breed: e.target.value, _manual: false }); setShowSuggestions(true); setHighlight(-1); }}
            onFocus={() => setShowSuggestions(true)}
            onKeyDown={onKeyDown}
            autoComplete="off"
            placeholder="Ex.: Golden Retriever, Yorkshire, Siamês..."
            data-testid={`pet-breed-${index}`}
          />
          {showSuggestions && suggestions.length > 0 && (
            <ul
              className="absolute z-20 left-0 right-0 mt-1 max-h-56 overflow-auto rounded-lg border border-stone-200 bg-white shadow-lg text-sm"
              data-testid={`pet-breed-suggestions-${index}`}
            >
              {suggestions.map((b, i) => (
                <li
                  key={b}
                  className={`px-3 py-1.5 cursor-pointer ${i === highlight ? "bg-amber-100" : "hover:bg-stone-50"}`}
                  onMouseDown={(e) => { e.preventDefault(); pickSuggestion(b); }}
                  onMouseEnter={() => setHighlight(i)}
                  data-testid={`pet-breed-suggestion-${index}-${i}`}
                >
                  {b}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2 justify-between">
        <div className="text-sm">
          <span className="text-stone-500 mr-2">Porte:</span>
          <select
            value={pet.size || "medium"}
            onChange={(e) => onChange(index, { ...pet, size: e.target.value, _manual: true })}
            className="rounded-lg border border-stone-300 px-2 py-1 text-sm"
            data-testid={`pet-size-${index}`}
          >
            <option value="small">Pequeno</option>
            <option value="medium">Médio</option>
            <option value="large">Grande</option>
          </select>
          {status.loading ? <span className="ml-2 text-xs text-stone-400">classificando...</span> :
            (pet.breed && status.matched === true) ? <span className="ml-2 text-xs text-emerald-700">✓ classificado por raça</span> :
            (pet.breed && status.matched === false) ? <span className="ml-2 text-xs text-amber-700">⚠ raça não reconhecida</span> : null}
        </div>
        <button type="button" onClick={() => onRemove(index)} className="text-stone-400 hover:text-red-600 text-xs inline-flex items-center gap-1" data-testid={`pet-remove-${index}`}>
          <X className="w-3.5 h-3.5" /> remover
        </button>
      </div>
      {pet.breed && status.matched === false && (
        <div className="mt-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-2" data-testid={`pet-warning-${index}`}>
          Raça não reconhecida na nossa base — definimos <strong>{SIZE_LABEL[pet.size] || SIZE_LABEL.medium}</strong> por padrão. Se sabe o porte correto, ajuste no seletor acima.
        </div>
      )}
    </div>
  );
};

export default function PublicReservation() {
  const [rooms, setRooms] = useState([]);
  const [settings, setSettings] = useState({});
  const [allBreeds, setAllBreeds] = useState([]);
  const [done, setDone] = useState(null);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [pricing, setPricing] = useState(null);
  const receiptRef = useRef(null);
  const [form, setForm] = useState({
    room_id: "",
    guest_name: "", guest_document: "", guest_email: "", guest_phone: "",
    guest_birthdate: "", guest_address: "", travel_reason: "", transport: "",
    checkin_date: "", checkout_date: "",
    adults: 1, children_0_3: 0, children_4_10: 0,
    pets: [],
    estimated_arrival: "", notes: "", accepted_terms: false,
    payment_receipt_url: "",
  });

  const petCounts = useMemo(() => {
    const c = { small: 0, medium: 0, large: 0 };
    (form.pets || []).forEach((p) => { const s = p.size || "medium"; if (c[s] !== undefined) c[s] += 1; });
    return c;
  }, [form.pets]);
  const totalPets = petCounts.small + petCounts.medium + petCounts.large;

  useEffect(() => {
    api.get("/public/rooms").then((r) => setRooms(r.data)).catch(() => {});
    api.get("/public/settings").then((r) => setSettings(r.data)).catch(() => {});
    api.get("/pets/breeds").then((r) => setAllBreeds(r.data?.breeds || [])).catch(() => {});
  }, []);

  const upd = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const updPet = (i, next) => setForm((f) => { const arr = [...(f.pets || [])]; arr[i] = next; return { ...f, pets: arr }; });
  const addPet = () => setForm((f) => ({ ...f, pets: [...(f.pets || []), { type: "cão", breed: "", size: "medium" }] }));
  const removePet = (i) => setForm((f) => { const arr = [...(f.pets || [])]; arr.splice(i, 1); return { ...f, pets: arr }; });

  const selectedRoom = useMemo(() => rooms.find((r) => r.id === form.room_id), [rooms, form.room_id]);
  const nights = nightsBetween(form.checkin_date, form.checkout_date);

  // Fetch live pricing from backend whenever inputs change
  useEffect(() => {
    if (!form.room_id || nights <= 0) { setPricing(null); return; }
    const controller = new AbortController();
    const t = setTimeout(() => {
      api.post("/pricing/calc", {
        room_id: form.room_id,
        checkin_date: form.checkin_date,
        checkout_date: form.checkout_date,
        adults: Math.max(1, parseInt(form.adults || "1", 10)),
        children_0_3: Math.max(0, parseInt(form.children_0_3 || "0", 10)),
        children_4_10: Math.max(0, parseInt(form.children_4_10 || "0", 10)),
        pets_small: petCounts.small,
        pets_medium: petCounts.medium,
        pets_large: petCounts.large,
      }, { signal: controller.signal }).then((r) => setPricing(r.data)).catch(() => {});
    }, 200);
    return () => { clearTimeout(t); controller.abort(); };
  }, [form.room_id, form.checkin_date, form.checkout_date, form.adults, form.children_0_3, form.children_4_10, petCounts.small, petCounts.medium, petCounts.large, nights]);

  const uploadReceipt = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 8 * 1024 * 1024) return toast.error("Arquivo maior que 8MB");
    setUploading(true);
    try {
      const fd = new FormData(); fd.append("file", f);
      const r = await api.post("/public/uploads/receipt", fd, { headers: { "Content-Type": "multipart/form-data" } });
      upd("payment_receipt_url", `${API}/files/${r.data.path}`);
      toast.success("Comprovante anexado");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Falha no envio");
    } finally { setUploading(false); e.target.value = ""; }
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.accepted_terms) return toast.error("Aceite os termos para continuar");
    if (nights <= 0) return toast.error("Data de saída deve ser após a chegada");
    // Validate pets
    for (let i = 0; i < (form.pets || []).length; i++) {
      const p = form.pets[i];
      if (!p.breed || !p.breed.trim()) return toast.error(`Preencha a raça do pet #${i + 1}`);
      if (!p.type) return toast.error(`Selecione o tipo do pet #${i + 1}`);
    }
    const adultsNum = Math.max(1, parseInt(form.adults || "1", 10));
    const k03 = Math.max(0, parseInt(form.children_0_3 || "0", 10));
    const k410 = Math.max(0, parseInt(form.children_4_10 || "0", 10));
    const guests = adultsNum + k03 + k410;
    if (selectedRoom && guests > (selectedRoom.max_adults + selectedRoom.max_children))
      return toast.error(`Este quarto acomoda no máximo ${selectedRoom.max_adults + selectedRoom.max_children} hóspedes`);
    setSaving(true);
    try {
      const payload = {
        ...form,
        adults: adultsNum,
        children_0_3: k03,
        children_4_10: k410,
        children: k03 + k410,
        pets: (form.pets || []).map((p) => ({ type: p.type || "cão", breed: (p.breed || "").trim(), size: p.size || "medium" })),
        pets_small: petCounts.small,
        pets_medium: petCounts.medium,
        pets_large: petCounts.large,
        room_id: form.room_id || null,
      };
      const r = await api.post("/public/pre-reservation", payload);
      setDone(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Erro ao enviar");
    } finally { setSaving(false); }
  };

  if (done) {
    const wa = (settings.whatsapp || "").replace(/\D/g, "");
    const msg = encodeURIComponent(`Olá! Acabei de enviar uma pré-reserva em nome de ${form.guest_name} para ${form.checkin_date} a ${form.checkout_date}. Valor estimado: ${brl(pricing?.total || 0)}.`);
    return (
      <div className="min-h-screen flex items-center justify-center px-4 bg-[color:var(--pousada-bg)]">
        <div className="max-w-lg w-full rounded-2xl bg-white p-8 shadow-warm border border-stone-200/70 text-center">
          <CheckCircle2 className="w-14 h-14 mx-auto text-[color:var(--pousada-palm)]" />
          <h1 className="font-serif text-3xl mt-4">Pré-reserva enviada!</h1>
          <p className="text-stone-600 mt-2">Aguarde nosso contato para confirmar disponibilidade e receber a chave PIX.</p>
          {pricing?.total > 0 && <p className="mt-3 font-mono text-lg text-[color:var(--pousada-terracotta)]">Estimativa: {brl(pricing.total)}</p>}
          <div className="mt-6 flex flex-col sm:flex-row gap-3 justify-center">
            {wa && <a href={`https://wa.me/${wa}?text=${msg}`} target="_blank" rel="noreferrer" className="btn-terra rounded-xl px-5 py-2.5 font-medium">Falar no WhatsApp</a>}
            <Link to="/" className="rounded-xl px-5 py-2.5 border border-stone-300">Voltar ao site</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[color:var(--pousada-bg)] py-8">
      <div className="max-w-3xl mx-auto px-4">
        <Link to="/" className="inline-flex items-center gap-1 text-sm text-stone-600 hover:text-stone-900 mb-6"><ArrowLeft className="w-4 h-4" /> Voltar</Link>
        <div className="rounded-2xl bg-white shadow-warm border border-stone-200/70 p-6 sm:p-8">
          <div className="flex items-center gap-3 mb-2">
            {settings.logo_url && <img src={settings.logo_url} alt="" className="h-10 w-10 rounded-full object-cover border border-stone-200" />}
            <div>
              <span className="text-xs uppercase tracking-widest text-amber-800/70">Ficha Nacional de Registro de Hóspedes (FNRH)</span>
              <h1 className="font-serif text-3xl sm:text-4xl">Pré-reserva</h1>
            </div>
          </div>
          <p className="text-stone-600 mt-2">Preencha seus dados. A confirmação ocorre após envio do comprovante PIX.</p>

          {/* Notices */}
          <div className="mt-5 rounded-xl bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900 flex items-start gap-2" data-testid="notice-nosmoking">
            <CigaretteOff className="w-4 h-4 mt-0.5 shrink-0" />
            <span><strong>Aviso:</strong> É totalmente proibido fumar dentro dos quartos.</span>
          </div>

          <form onSubmit={submit} className="mt-6 space-y-5" data-testid="fnrh-form">
            <div className="grid sm:grid-cols-2 gap-4">
              <div><Label>Nome completo *</Label><Input data-testid="fnrh-name" required value={form.guest_name} onChange={(e) => upd("guest_name", e.target.value)} /></div>
              <div><Label>CPF ou Passaporte *</Label><Input data-testid="fnrh-doc" required value={form.guest_document} onChange={(e) => upd("guest_document", e.target.value)} /></div>
              <div><Label>E-mail *</Label><Input data-testid="fnrh-email" type="email" required value={form.guest_email} onChange={(e) => upd("guest_email", e.target.value)} /></div>
              <div><Label>Telefone/WhatsApp *</Label><Input data-testid="fnrh-phone" required value={form.guest_phone} onChange={(e) => upd("guest_phone", e.target.value)} /></div>
              <div><Label>Data de nascimento *</Label><Input data-testid="fnrh-birth" type="date" required value={form.guest_birthdate} onChange={(e) => upd("guest_birthdate", e.target.value)} /></div>
              <div><Label>Endereço residencial</Label><Input value={form.guest_address} onChange={(e) => upd("guest_address", e.target.value)} /></div>
              <div><Label>Motivo da viagem</Label><Input placeholder="Lazer, negócios..." value={form.travel_reason} onChange={(e) => upd("travel_reason", e.target.value)} /></div>
              <div><Label>Meio de transporte</Label><Input placeholder="Carro, avião, ônibus..." value={form.transport} onChange={(e) => upd("transport", e.target.value)} /></div>
            </div>

            <div className="pt-4 border-t border-stone-100" />
            <h3 className="font-serif text-xl">Estadia</h3>

            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <Label>Quarto preferido</Label>
                <Select value={form.room_id} onValueChange={(v) => upd("room_id", v)}>
                  <SelectTrigger data-testid="fnrh-room"><SelectValue placeholder="Sem preferência" /></SelectTrigger>
                  <SelectContent>
                    {rooms.map((r) => <SelectItem key={r.id} value={r.id}>{r.name} — {brl(r.daily_rate)}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Horário previsto de chegada</Label><Input type="time" value={form.estimated_arrival} onChange={(e) => upd("estimated_arrival", e.target.value)} /></div>
              <div><Label>Check-in *</Label><Input data-testid="fnrh-checkin" type="date" required value={form.checkin_date} onChange={(e) => upd("checkin_date", e.target.value)} /></div>
              <div><Label>Check-out *</Label><Input data-testid="fnrh-checkout" type="date" required value={form.checkout_date} onChange={(e) => upd("checkout_date", e.target.value)} /></div>
            </div>

            {/* Hóspedes */}
            <div className="rounded-2xl border border-stone-200 p-4">
              <h4 className="font-serif text-lg mb-1">Hóspedes</h4>
              <p className="text-xs text-stone-500 mb-2">Segundo adulto e seguintes têm 10% de desconto. Primeira criança de 0-3 anos é isenta. Demais crianças pagam 65% da diária.</p>
              <div className="divide-y divide-stone-100">
                <NumberField label="Adultos" value={form.adults} onChange={(v) => upd("adults", v)} min={1} testid="fnrh-adults" />
                <NumberField label="Crianças de 0 a 3 anos" value={form.children_0_3} onChange={(v) => upd("children_0_3", v)} testid="fnrh-kids-03" />
                <NumberField label="Crianças de 4 a 10 anos" value={form.children_4_10} onChange={(v) => upd("children_4_10", v)} testid="fnrh-kids-410" />
              </div>
            </div>

            {/* Pets */}
            <div className="rounded-2xl border border-stone-200 p-4">
              <div className="flex items-center justify-between mb-1">
                <h4 className="font-serif text-lg flex items-center gap-2"><PawPrint className="w-4 h-4 text-[color:var(--pousada-terracotta)]" /> Pets</h4>
                <Button type="button" size="sm" variant="outline" onClick={addPet} className="rounded-xl" data-testid="btn-add-pet"><Plus className="w-3.5 h-3.5 mr-1" />Adicionar pet</Button>
              </div>
              <p className="text-xs text-stone-500 mb-3">Informe o <strong>tipo</strong> e a <strong>raça</strong>; classificamos o porte automaticamente. Pequeno {settings.pet_small_pct || 20.7}% · Médio {settings.pet_medium_pct || 27.6}% · Grande {settings.pet_large_pct || 34.5}% da diária de 1 hóspede.</p>
              {(form.pets || []).length === 0 ? (
                <p className="text-sm text-stone-500">Nenhum pet adicionado.</p>
              ) : (
                <div className="space-y-2">
                  {form.pets.map((p, i) => (
                    <PetRow key={i} pet={p} index={i} onChange={updPet} onRemove={removePet} allBreeds={allBreeds} />
                  ))}
                </div>
              )}
              {totalPets > 0 && (
                <div className="mt-3 rounded-xl bg-orange-50 border border-orange-200 p-3 text-sm text-orange-900 flex items-start gap-2" data-testid="notice-pet">
                  <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                  <span><strong>Aviso:</strong> O animal não pode dormir nas camas e qualquer dano ou avaria causada pelo animal é de inteira responsabilidade do tutor.</span>
                </div>
              )}
            </div>

            {/* Live pricing */}
            {selectedRoom && pricing && pricing.n_nights > 0 && (
              <div className="rounded-2xl bg-[color:var(--pousada-elev)] paper-grain p-5 border border-stone-200/70" data-testid="price-breakdown">
                <div className="flex items-center gap-2 mb-3"><Calculator className="w-4 h-4 text-[color:var(--pousada-terracotta)]" /><h4 className="font-serif text-lg">Estimativa detalhada</h4></div>
                <div className="text-sm space-y-1.5 text-stone-700">
                  <div className="flex justify-between"><span>Quarto</span><span className="font-medium">{selectedRoom.name}</span></div>
                  <div className="flex justify-between"><span>Diária base (por adulto)</span><span className="font-mono">{brl(pricing.base_rate)}</span></div>
                  <div className="flex justify-between"><span>Noites</span><span className="font-mono">{pricing.n_nights}</span></div>
                  <div className="flex justify-between"><span>Adultos</span><span className="font-mono">{pricing.adults}</span></div>
                  {pricing.free_children > 0 && <div className="flex justify-between text-emerald-700"><span>Criança 0-3 isenta</span><span className="font-mono">1</span></div>}
                  {pricing.paying_children > 0 && <div className="flex justify-between"><span>Crianças que pagam 65%</span><span className="font-mono">{pricing.paying_children}</span></div>}
                  <div className="pt-2 mt-2 border-t border-stone-300/70 max-h-40 overflow-y-auto">
                    <div className="text-xs uppercase tracking-widest text-stone-500 mb-1">Por noite</div>
                    {pricing.nights.map((n) => (
                      <div key={n.date} className="flex justify-between text-xs font-mono" data-testid={`night-row-${n.date}`}>
                        <span className="truncate">
                          {n.date}
                          {n.surcharge > 0 && <span className="ml-1 text-[color:var(--pousada-terracotta)]">+{n.surcharge}%</span>}
                          {n.is_national_holiday && <span className="ml-1 text-[color:var(--pousada-terracotta)]" title={n.holiday_name || "Feriado"}>🎉 {n.holiday_name || "Feriado"}</span>}
                        </span>
                        <span>{brl(n.total)}</span>
                      </div>
                    ))}
                  </div>
                  <div className="pt-3 flex justify-between text-base border-t border-stone-300/70">
                    <span className="font-medium">Total estimado</span>
                    <span className="font-mono text-[color:var(--pousada-terracotta)] font-semibold text-lg" data-testid="total-estimate">{brl(pricing.total)}</span>
                  </div>
                </div>
              </div>
            )}

            <div>
              <Label>Observações</Label>
              <Textarea rows={3} value={form.notes} onChange={(e) => upd("notes", e.target.value)} placeholder="Restrições alimentares, pedidos especiais..." />
            </div>

            {/* Receipt upload */}
            <div className="rounded-2xl border border-stone-200 p-4">
              <Label className="text-sm">Comprovante de pagamento PIX (opcional agora, pode enviar depois)</Label>
              <input ref={receiptRef} type="file" accept="image/*,application/pdf" hidden onChange={uploadReceipt} />
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <Button type="button" variant="outline" className="rounded-xl" onClick={() => receiptRef.current?.click()} disabled={uploading} data-testid="btn-upload-receipt">
                  <Upload className="w-4 h-4 mr-1" />{uploading ? "Enviando..." : "Anexar comprovante"}
                </Button>
                {form.payment_receipt_url && (
                  <div className="flex items-center gap-2 text-sm text-[color:var(--pousada-palm)]" data-testid="receipt-attached">
                    <FileCheck2 className="w-4 h-4" />
                    <a href={form.payment_receipt_url} target="_blank" rel="noreferrer" className="underline">Comprovante anexado</a>
                    <button type="button" onClick={() => upd("payment_receipt_url", "")} className="text-stone-400 hover:text-stone-700"><X className="w-3.5 h-3.5" /></button>
                  </div>
                )}
              </div>
              <p className="text-xs text-stone-500 mt-2">Imagem ou PDF, máx 8MB. Anexar agiliza a confirmação da reserva.</p>
            </div>

            <label className="flex items-start gap-3 text-sm text-stone-700">
              <Checkbox data-testid="fnrh-terms" checked={form.accepted_terms} onCheckedChange={(v) => upd("accepted_terms", !!v)} />
              <span>Li e aceito as políticas de cancelamento e regras de convivência da pousada (proibido fumar; regras de pets). Autorizo o tratamento dos meus dados conforme LGPD para fins de reserva.</span>
            </label>

            <Button data-testid="fnrh-submit" type="submit" disabled={saving} className="btn-terra w-full rounded-xl h-11 font-medium">
              {saving ? "Enviando..." : `Enviar pré-reserva${pricing?.total ? ` (${brl(pricing.total)})` : ""}`}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
