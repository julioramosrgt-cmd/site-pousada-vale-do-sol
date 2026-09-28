import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/apiClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ArrowLeft, CheckCircle2 } from "lucide-react";

export default function PublicReservation() {
  const [rooms, setRooms] = useState([]);
  const [settings, setSettings] = useState({});
  const [done, setDone] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    room_id: "",
    guest_name: "", guest_document: "", guest_email: "", guest_phone: "",
    guest_birthdate: "", guest_address: "", travel_reason: "", transport: "",
    checkin_date: "", checkout_date: "", adults: 1, children: 0,
    estimated_arrival: "", notes: "", accepted_terms: false,
  });

  useEffect(() => {
    api.get("/public/rooms").then((r) => setRooms(r.data)).catch(() => {});
    api.get("/public/settings").then((r) => setSettings(r.data)).catch(() => {});
  }, []);

  const upd = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.accepted_terms) return toast.error("Aceite os termos para continuar");
    if (form.checkin_date && form.checkout_date && form.checkout_date <= form.checkin_date)
      return toast.error("Data de saída deve ser após a chegada");
    setSaving(true);
    try {
      const payload = { ...form, room_id: form.room_id || null };
      const r = await api.post("/public/pre-reservation", payload);
      setDone(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Erro ao enviar");
    } finally { setSaving(false); }
  };

  if (done) {
    const wa = (settings.whatsapp || "").replace(/\D/g, "");
    const msg = encodeURIComponent(`Olá! Acabei de enviar uma pré-reserva no site em nome de ${form.guest_name} para ${form.checkin_date} a ${form.checkout_date}.`);
    return (
      <div className="min-h-screen flex items-center justify-center px-4 bg-[color:var(--pousada-bg)]">
        <div className="max-w-lg w-full rounded-2xl bg-white p-8 shadow-warm border border-stone-200/70 text-center">
          <CheckCircle2 className="w-14 h-14 mx-auto text-[color:var(--pousada-palm)]" />
          <h1 className="font-serif text-3xl mt-4">Pré-reserva enviada!</h1>
          <p className="text-stone-600 mt-2">Aguarde nosso contato para confirmar disponibilidade e receber a chave PIX.</p>
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
      <div className="max-w-2xl mx-auto px-4">
        <Link to="/" className="inline-flex items-center gap-1 text-sm text-stone-600 hover:text-stone-900 mb-6"><ArrowLeft className="w-4 h-4" /> Voltar</Link>
        <div className="rounded-2xl bg-white shadow-warm border border-stone-200/70 p-6 sm:p-8">
          <span className="text-xs uppercase tracking-widest text-amber-800/70">Ficha Nacional de Registro de Hóspedes (FNRH)</span>
          <h1 className="font-serif text-3xl sm:text-4xl mt-1">Pré-reserva</h1>
          <p className="text-stone-600 mt-2">Preencha seus dados. A confirmação ocorre após envio do comprovante PIX.</p>

          <form onSubmit={submit} className="mt-8 space-y-5" data-testid="fnrh-form">
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <Label>Nome completo *</Label>
                <Input data-testid="fnrh-name" required value={form.guest_name} onChange={(e) => upd("guest_name", e.target.value)} />
              </div>
              <div>
                <Label>CPF ou Passaporte *</Label>
                <Input data-testid="fnrh-doc" required value={form.guest_document} onChange={(e) => upd("guest_document", e.target.value)} />
              </div>
              <div>
                <Label>E-mail *</Label>
                <Input data-testid="fnrh-email" type="email" required value={form.guest_email} onChange={(e) => upd("guest_email", e.target.value)} />
              </div>
              <div>
                <Label>Telefone/WhatsApp *</Label>
                <Input data-testid="fnrh-phone" required value={form.guest_phone} onChange={(e) => upd("guest_phone", e.target.value)} />
              </div>
              <div>
                <Label>Data de nascimento *</Label>
                <Input data-testid="fnrh-birth" type="date" required value={form.guest_birthdate} onChange={(e) => upd("guest_birthdate", e.target.value)} />
              </div>
              <div>
                <Label>Endereço residencial</Label>
                <Input value={form.guest_address} onChange={(e) => upd("guest_address", e.target.value)} />
              </div>
              <div>
                <Label>Motivo da viagem</Label>
                <Input placeholder="Lazer, negócios..." value={form.travel_reason} onChange={(e) => upd("travel_reason", e.target.value)} />
              </div>
              <div>
                <Label>Meio de transporte</Label>
                <Input placeholder="Carro, avião, ônibus..." value={form.transport} onChange={(e) => upd("transport", e.target.value)} />
              </div>
            </div>

            <div className="pt-4 border-t border-stone-100" />
            <h3 className="font-serif text-xl">Estadia</h3>

            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <Label>Quarto preferido</Label>
                <Select value={form.room_id} onValueChange={(v) => upd("room_id", v)}>
                  <SelectTrigger data-testid="fnrh-room"><SelectValue placeholder="Sem preferência" /></SelectTrigger>
                  <SelectContent>
                    {rooms.map((r) => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Horário previsto de chegada</Label>
                <Input type="time" value={form.estimated_arrival} onChange={(e) => upd("estimated_arrival", e.target.value)} />
              </div>
              <div>
                <Label>Check-in *</Label>
                <Input data-testid="fnrh-checkin" type="date" required value={form.checkin_date} onChange={(e) => upd("checkin_date", e.target.value)} />
              </div>
              <div>
                <Label>Check-out *</Label>
                <Input data-testid="fnrh-checkout" type="date" required value={form.checkout_date} onChange={(e) => upd("checkout_date", e.target.value)} />
              </div>
              <div>
                <Label>Adultos</Label>
                <Input type="number" min="1" value={form.adults} onChange={(e) => upd("adults", parseInt(e.target.value || "1", 10))} />
              </div>
              <div>
                <Label>Crianças</Label>
                <Input type="number" min="0" value={form.children} onChange={(e) => upd("children", parseInt(e.target.value || "0", 10))} />
              </div>
            </div>

            <div>
              <Label>Observações</Label>
              <Textarea rows={3} value={form.notes} onChange={(e) => upd("notes", e.target.value)} placeholder="Restrições alimentares, pedidos especiais..." />
            </div>

            <label className="flex items-start gap-3 text-sm text-stone-700">
              <Checkbox data-testid="fnrh-terms" checked={form.accepted_terms} onCheckedChange={(v) => upd("accepted_terms", !!v)} />
              <span>Li e aceito as políticas de cancelamento e regras de convivência da pousada. Autorizo o tratamento dos meus dados conforme LGPD para fins de reserva.</span>
            </label>

            <Button data-testid="fnrh-submit" type="submit" disabled={saving} className="btn-terra w-full rounded-xl h-11 font-medium">
              {saving ? "Enviando..." : "Enviar pré-reserva"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
