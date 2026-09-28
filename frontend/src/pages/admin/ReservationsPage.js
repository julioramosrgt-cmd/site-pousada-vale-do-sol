import { useEffect, useState } from "react";
import { api } from "@/lib/apiClient";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Trash2, MessageSquare, Paperclip } from "lucide-react";

const STATUS_LABEL = { pending: "Pendente", confirmed: "Confirmada", cancelled: "Cancelada", blocked: "Bloqueado", maintenance: "Manutenção", checked_in: "Check-in", checked_out: "Check-out" };

export default function ReservationsPage() {
  const [rows, setRows] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [settings, setSettings] = useState({});
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(newForm());

  function newForm() {
    return {
      room_id: "", guest_name: "", guest_document: "", guest_email: "", guest_phone: "",
      checkin_date: "", checkout_date: "", adults: 1, children: 0, total_amount: 0, deposit_amount: 0,
      status: "confirmed", source: "direct", notes: "",
    };
  }

  const load = () => {
    const q = filter === "all" ? "" : `?status=${filter}`;
    api.get(`/reservations${q}`).then((r) => setRows(r.data));
  };
  useEffect(() => {
    load();
    api.get("/rooms").then((r) => setRooms(r.data));
    api.get("/settings").then((r) => setSettings(r.data));
  }, [filter]); // eslint-disable-line

  const save = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...form, room_id: form.room_id || null };
      await api.post("/reservations", payload);
      toast.success("Reserva criada");
      setOpen(false); setForm(newForm()); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Erro"); }
  };

  const setStatus = async (r, status) => {
    await api.patch(`/reservations/${r.id}/status`, { status });
    toast.success("Status atualizado");
    load();
  };

  const remove = async (r) => {
    if (!window.confirm("Excluir esta reserva?")) return;
    await api.delete(`/reservations/${r.id}`);
    toast.success("Excluída");
    load();
  };

  const sendPix = (r) => {
    const room = rooms.find((x) => x.id === r.room_id);
    const nights = Math.max(1, Math.round((new Date(r.checkout_date) - new Date(r.checkin_date)) / 86400000));
    const guests = (r.adults || 1) + (r.children || 0);
    const rate = room ? Number(room.daily_rate) : 0;
    const val = r.total_amount || (room && room.rate_per_guest ? rate * guests * nights : rate * nights);
    const msg = `Olá ${r.guest_name}! Para confirmar sua reserva (${r.checkin_date} a ${r.checkout_date})${room ? ` no quarto ${room.name}` : ""}, envie R$ ${val.toFixed(2)} via PIX para: ${settings.pix_key || "-"} (${settings.pix_key_type || "chave"}). Após o envio, nos encaminhe o comprovante. Obrigado!`;
    const wa = (r.guest_phone || settings.whatsapp || "").replace(/\D/g, "");
    window.open(`https://wa.me/${wa}?text=${encodeURIComponent(msg)}`, "_blank");
  };

  const priceOf = (r) => {
    const room = rooms.find((x) => x.id === r.room_id);
    if (!room) return null;
    const nights = Math.max(0, Math.round((new Date(r.checkout_date) - new Date(r.checkin_date)) / 86400000));
    const guests = (r.adults || 1) + (r.children || 0);
    const rate = Number(room.daily_rate || 0);
    const total = room.rate_per_guest ? rate * guests * nights : rate * nights;
    return { room, nights, guests, rate, total, perGuest: !!room.rate_per_guest };
  };

  const roomName = (id) => rooms.find((r) => r.id === id)?.name || "—";

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6">
        <div>
          <span className="text-xs uppercase tracking-widest text-amber-800/70">Ocupação</span>
          <h1 className="font-serif text-3xl sm:text-4xl">Reservas</h1>
        </div>
        <div className="flex gap-3">
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-40" data-testid="res-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas</SelectItem>
              {Object.entries(STATUS_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
            </SelectContent>
          </Select>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button data-testid="btn-new-reservation" className="btn-terra rounded-xl"><Plus className="w-4 h-4 mr-1" /> Nova reserva</Button></DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
              <DialogHeader><DialogTitle>Nova reserva direta</DialogTitle></DialogHeader>
              <form onSubmit={save} className="grid sm:grid-cols-2 gap-3">
                <div className="sm:col-span-2"><Label>Hóspede *</Label><Input required value={form.guest_name} onChange={(e) => setForm({ ...form, guest_name: e.target.value })} /></div>
                <div><Label>CPF/Passaporte</Label><Input value={form.guest_document} onChange={(e) => setForm({ ...form, guest_document: e.target.value })} /></div>
                <div><Label>WhatsApp</Label><Input value={form.guest_phone} onChange={(e) => setForm({ ...form, guest_phone: e.target.value })} /></div>
                <div><Label>E-mail</Label><Input value={form.guest_email} onChange={(e) => setForm({ ...form, guest_email: e.target.value })} /></div>
                <div><Label>Quarto</Label>
                  <Select value={form.room_id} onValueChange={(v) => setForm({ ...form, room_id: v })}>
                    <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
                    <SelectContent>{rooms.map((r) => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div><Label>Check-in *</Label><Input type="date" required value={form.checkin_date} onChange={(e) => setForm({ ...form, checkin_date: e.target.value })} /></div>
                <div><Label>Check-out *</Label><Input type="date" required value={form.checkout_date} onChange={(e) => setForm({ ...form, checkout_date: e.target.value })} /></div>
                <div><Label>Adultos</Label><Input type="number" min="1" value={form.adults} onChange={(e) => setForm({ ...form, adults: parseInt(e.target.value || "1", 10) })} /></div>
                <div><Label>Crianças</Label><Input type="number" min="0" value={form.children} onChange={(e) => setForm({ ...form, children: parseInt(e.target.value || "0", 10) })} /></div>
                <div><Label>Valor total (R$)</Label><Input type="number" step="0.01" value={form.total_amount} onChange={(e) => setForm({ ...form, total_amount: parseFloat(e.target.value || "0") })} /></div>
                <div><Label>Sinal recebido (R$)</Label><Input type="number" step="0.01" value={form.deposit_amount} onChange={(e) => setForm({ ...form, deposit_amount: parseFloat(e.target.value || "0") })} /></div>
                <div className="sm:col-span-2"><Label>Status</Label>
                  <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{Object.entries(STATUS_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="sm:col-span-2"><Label>Observações</Label><Textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
                <div className="sm:col-span-2"><Button type="submit" className="btn-terra w-full rounded-xl">Salvar reserva</Button></div>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-xs uppercase tracking-widest text-stone-500">
              <tr>
                <th className="text-left p-3">Hóspede</th>
                <th className="text-left p-3">Quarto</th>
                <th className="text-left p-3">Datas</th>
                <th className="text-left p-3">Origem</th>
                <th className="text-left p-3">Status</th>
                <th className="text-right p-3">Ações</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && <tr><td colSpan={6} className="p-6 text-center text-stone-500">Nenhuma reserva</td></tr>}
              {rows.map((r) => {
                const p = priceOf(r);
                return (
                <tr key={r.id} className="border-t border-stone-100" data-testid={`res-row-${r.id}`}>
                  <td className="p-3">
                    <div className="font-medium">{r.guest_name || "Sem nome"}</div>
                    <div className="text-xs text-stone-500">{r.guest_phone} {r.guest_email && `· ${r.guest_email}`}</div>
                  </td>
                  <td className="p-3">
                    <div>{roomName(r.room_id)}</div>
                    {p && p.nights > 0 && (
                      <div className="text-[10px] text-stone-500 font-mono" data-testid={`res-breakdown-${r.id}`}>
                        {p.perGuest ? `R$${p.rate}×${p.guests}h×${p.nights}n` : `R$${p.rate}×${p.nights}n`} = <span className="text-[color:var(--pousada-terracotta)]">R$ {p.total.toFixed(2)}</span>
                      </div>
                    )}
                  </td>
                  <td className="p-3 font-mono text-xs">{r.checkin_date} → {r.checkout_date}</td>
                  <td className="p-3 text-xs uppercase text-stone-500">{r.source}{r.ota_source ? `/${r.ota_source}` : ""}</td>
                  <td className="p-3">
                    <Select value={r.status} onValueChange={(v) => setStatus(r, v)}>
                      <SelectTrigger className="w-36 h-8" data-testid={`status-${r.id}`}><SelectValue /></SelectTrigger>
                      <SelectContent>{Object.entries(STATUS_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent>
                    </Select>
                  </td>
                  <td className="p-3 text-right">
                    <div className="inline-flex gap-1">
                      {r.payment_receipt_url && (
                        <a href={r.payment_receipt_url} target="_blank" rel="noreferrer" title="Ver comprovante PIX" data-testid={`receipt-${r.id}`}>
                          <Button size="icon" variant="ghost"><Paperclip className="w-4 h-4 text-[color:var(--pousada-palm)]" /></Button>
                        </a>
                      )}
                      <Button size="icon" variant="ghost" title="Enviar PIX no WhatsApp" onClick={() => sendPix(r)} data-testid={`send-pix-${r.id}`}><MessageSquare className="w-4 h-4" /></Button>
                      <Button size="icon" variant="ghost" onClick={() => remove(r)} data-testid={`del-${r.id}`}><Trash2 className="w-4 h-4 text-red-600" /></Button>
                    </div>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
