import { useEffect, useState } from "react";
import { api, API } from "@/lib/apiClient";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Copy, Plus, Trash2, RefreshCw } from "lucide-react";

export default function ICalPage() {
  const [rooms, setRooms] = useState([]);
  const [sources, setSources] = useState([]);
  const [form, setForm] = useState({ room_id: "", name: "Airbnb", url: "" });

  const load = async () => {
    const [r, s] = await Promise.all([api.get("/rooms"), api.get("/ical/sources")]);
    setRooms(r.data); setSources(s.data);
  };
  useEffect(() => { load(); }, []);

  const exportUrl = (room) => `${API}/ical/room/${room.id}/${room.ical_token}.ics`;

  const copy = async (t) => { try { await navigator.clipboard.writeText(t); toast.success("Link copiado"); } catch { toast.error("Não copiou"); } };

  const addSource = async (e) => {
    e.preventDefault();
    if (!form.room_id || !form.url) return toast.error("Preencha quarto e URL");
    await api.post("/ical/sources", form);
    setForm({ room_id: "", name: "Airbnb", url: "" });
    toast.success("Fonte adicionada"); load();
  };

  const syncOne = async (id) => {
    const r = await api.post(`/ical/sync/${id}`);
    if (r.data.ok) toast.success(`Sincronizado: ${r.data.count} eventos`); else toast.error(r.data.error || "Erro");
    load();
  };

  const syncAll = async () => {
    const r = await api.post("/ical/sync");
    toast.success(`Fontes sincronizadas: ${r.data.synced}`); load();
  };

  const remove = async (id) => {
    if (!window.confirm("Remover fonte?")) return;
    await api.delete(`/ical/sources/${id}`); load();
  };

  const roomName = (id) => rooms.find((r) => r.id === id)?.name || "—";

  return (
    <div>
      <div className="flex items-end justify-between mb-6">
        <div>
          <span className="text-xs uppercase tracking-widest text-amber-800/70">Integrações</span>
          <h1 className="font-serif text-3xl sm:text-4xl">iCal · Airbnb / Booking / TripLar</h1>
        </div>
        <Button onClick={syncAll} className="btn-terra rounded-xl" data-testid="btn-sync-all"><RefreshCw className="w-4 h-4 mr-1" />Sincronizar tudo</Button>
      </div>

      <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm p-6 mb-6">
        <h3 className="font-serif text-xl mb-1">Exportar (cole em Airbnb/Booking)</h3>
        <p className="text-sm text-stone-500 mb-4">Cada quarto possui um link .ics exclusivo. Cole nas configurações do canal externo.</p>
        {rooms.length === 0 ? <p className="text-stone-500">Cadastre quartos primeiro.</p> : (
          <div className="space-y-2">
            {rooms.map((r) => (
              <div key={r.id} className="flex items-center gap-2 flex-wrap" data-testid={`export-${r.id}`}>
                <div className="font-medium w-40 truncate">{r.name}</div>
                <Input readOnly value={exportUrl(r)} className="font-mono text-xs flex-1 min-w-[240px]" />
                <Button variant="outline" size="sm" onClick={() => copy(exportUrl(r))}><Copy className="w-3 h-3 mr-1" />Copiar</Button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm p-6">
        <h3 className="font-serif text-xl mb-4">Importar de OTAs</h3>
        <form onSubmit={addSource} className="grid sm:grid-cols-4 gap-3 mb-4">
          <div>
            <Label>Quarto</Label>
            <Select value={form.room_id} onValueChange={(v) => setForm({ ...form, room_id: v })}>
              <SelectTrigger data-testid="ical-room"><SelectValue placeholder="Selecione" /></SelectTrigger>
              <SelectContent>{rooms.map((r) => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label>Canal</Label>
            <Select value={form.name} onValueChange={(v) => setForm({ ...form, name: v })}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Airbnb">Airbnb</SelectItem>
                <SelectItem value="Booking">Booking</SelectItem>
                <SelectItem value="TripLar">TripLar</SelectItem>
                <SelectItem value="Outro">Outro</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="sm:col-span-2"><Label>URL do feed .ics</Label><Input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://..." data-testid="ical-url" /></div>
          <div className="sm:col-span-4"><Button type="submit" className="btn-terra rounded-xl" data-testid="btn-add-ical"><Plus className="w-4 h-4 mr-1" />Adicionar fonte</Button></div>
        </form>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-xs uppercase tracking-widest text-stone-500">
              <tr><th className="p-3 text-left">Canal</th><th className="p-3 text-left">Quarto</th><th className="p-3 text-left">URL</th><th className="p-3 text-left">Última sync</th><th className="p-3 text-right">Ações</th></tr>
            </thead>
            <tbody>
              {sources.length === 0 && <tr><td colSpan={5} className="p-6 text-center text-stone-500">Nenhuma fonte cadastrada.</td></tr>}
              {sources.map((s) => (
                <tr key={s.id} className="border-t border-stone-100">
                  <td className="p-3">{s.name}</td>
                  <td className="p-3">{roomName(s.room_id)}</td>
                  <td className="p-3 max-w-[240px] truncate font-mono text-xs">{s.url}</td>
                  <td className="p-3 text-xs">{s.last_sync ? new Date(s.last_sync).toLocaleString("pt-BR") : "—"}<div className="text-stone-500">{s.last_status || ""}</div></td>
                  <td className="p-3 text-right">
                    <Button size="sm" variant="outline" onClick={() => syncOne(s.id)} data-testid={`sync-${s.id}`}><RefreshCw className="w-3 h-3 mr-1" />Sync</Button>
                    <Button size="sm" variant="ghost" onClick={() => remove(s.id)}><Trash2 className="w-3 h-3 text-red-600" /></Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
