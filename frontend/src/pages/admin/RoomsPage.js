import { useEffect, useState } from "react";
import { api } from "@/lib/apiClient";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Trash2, Pencil } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";

const emptyRoom = {
  name: "", category: "Quarto", max_adults: 2, max_children: 0,
  amenities: [], daily_rate: 0, rate_per_guest: false, min_stay: 1, status: "available",
  description: "", cover_image: "",
};

export default function RoomsPage() {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyRoom);

  const load = () => api.get("/rooms").then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm(emptyRoom); setOpen(true); };
  const openEdit = (r) => {
    setEditing(r);
    setForm({ ...r, amenities: r.amenities || [] });
    setOpen(true);
  };

  const save = async (e) => {
    e.preventDefault();
    const payload = {
      name: form.name,
      category: form.category || "Quarto",
      max_adults: parseInt(form.max_adults || 1, 10),
      max_children: parseInt(form.max_children || 0, 10),
      amenities: typeof form.amenities === "string"
        ? form.amenities.split(",").map((s) => s.trim()).filter(Boolean)
        : (form.amenities || []),
      daily_rate: parseFloat(form.daily_rate || 0),
      rate_per_guest: !!form.rate_per_guest,
      min_stay: parseInt(form.min_stay || 1, 10),
      status: form.status || "available",
      description: form.description || "",
      cover_image: form.cover_image || "",
    };
    try {
      if (editing) await api.put(`/rooms/${editing.id}`, payload);
      else await api.post("/rooms", payload);
      toast.success("Quarto salvo");
      setOpen(false); load();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Erro ao salvar");
    }
  };

  const remove = async (r) => {
    if (!window.confirm(`Excluir "${r.name}"?`)) return;
    await api.delete(`/rooms/${r.id}`);
    toast.success("Excluído"); load();
  };

  return (
    <div>
      <div className="flex items-end justify-between mb-6">
        <div>
          <span className="text-xs uppercase tracking-widest text-amber-800/70">Inventário</span>
          <h1 className="font-serif text-3xl sm:text-4xl">Quartos</h1>
        </div>
        <Button onClick={openNew} className="btn-terra rounded-xl" data-testid="btn-new-room"><Plus className="w-4 h-4 mr-1" />Novo quarto</Button>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {rows.length === 0 && <p className="text-stone-500">Nenhum quarto cadastrado. Comece adicionando o primeiro.</p>}
        {rows.map((r) => (
          <div key={r.id} className="rounded-2xl bg-white border border-stone-200/70 shadow-warm overflow-hidden" data-testid={`room-${r.id}`}>
            {r.cover_image && <img src={r.cover_image} alt={r.name} className="h-36 w-full object-cover" />}
            <div className="p-4">
              <div className="flex items-center justify-between">
                <h3 className="font-serif text-lg">{r.name}</h3>
                <span className="font-mono text-[color:var(--pousada-terracotta)]">R$ {Number(r.daily_rate).toFixed(0)}</span>
              </div>
              <div className="text-xs text-stone-500 mt-1">{r.category} · {r.max_adults} adultos + {r.max_children} crianças · min {r.min_stay}n{r.rate_per_guest ? " · por hóspede" : ""}</div>
              <div className="text-xs mt-2">
                <span className={`status-dot ${r.status === "maintenance" ? "status-maintenance" : "status-confirmed"}`} /> {r.status === "maintenance" ? " Em manutenção" : " Disponível"}
              </div>
              <div className="mt-3 flex gap-2">
                <Button size="sm" variant="outline" onClick={() => openEdit(r)} data-testid={`edit-room-${r.id}`}><Pencil className="w-3 h-3 mr-1" />Editar</Button>
                <Button size="sm" variant="ghost" onClick={() => remove(r)} data-testid={`del-room-${r.id}`}><Trash2 className="w-3 h-3 text-red-600" /></Button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{editing ? "Editar quarto" : "Novo quarto"}</DialogTitle></DialogHeader>
          <form onSubmit={save} className="grid sm:grid-cols-2 gap-3">
            <div className="sm:col-span-2"><Label>Nome *</Label><Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="room-name" /></div>
            <div><Label>Categoria</Label><Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} /></div>
            <div><Label>Diária (R$)</Label><Input type="number" step="0.01" value={form.daily_rate} onChange={(e) => setForm({ ...form, daily_rate: e.target.value })} /></div>
            <div className="sm:col-span-2 flex items-center gap-2 rounded-xl bg-stone-50 border border-stone-200 p-3">
              <Checkbox id="rate_per_guest" checked={!!form.rate_per_guest} onCheckedChange={(v) => setForm({ ...form, rate_per_guest: !!v })} data-testid="room-rate-per-guest" />
              <label htmlFor="rate_per_guest" className="text-sm">
                <div className="font-medium">Cobrar por hóspede</div>
                <div className="text-xs text-stone-500">Total = diária × nº hóspedes × noites. Desmarque para cobrar valor único por diária.</div>
              </label>
            </div>
            <div><Label>Máx. adultos</Label><Input type="number" min="1" value={form.max_adults} onChange={(e) => setForm({ ...form, max_adults: e.target.value })} /></div>
            <div><Label>Máx. crianças</Label><Input type="number" min="0" value={form.max_children} onChange={(e) => setForm({ ...form, max_children: e.target.value })} /></div>
            <div><Label>Estada mínima (noites)</Label><Input type="number" min="1" value={form.min_stay} onChange={(e) => setForm({ ...form, min_stay: e.target.value })} /></div>
            <div>
              <Label>Status</Label>
              <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="available">Disponível</SelectItem><SelectItem value="maintenance">Em manutenção</SelectItem></SelectContent>
              </Select>
            </div>
            <div className="sm:col-span-2"><Label>Comodidades (separadas por vírgula)</Label><Input value={Array.isArray(form.amenities) ? form.amenities.join(", ") : form.amenities} onChange={(e) => setForm({ ...form, amenities: e.target.value })} placeholder="Wi-Fi, ar-condicionado, café da manhã" /></div>
            <div className="sm:col-span-2"><Label>Foto de capa (URL)</Label><Input value={form.cover_image} onChange={(e) => setForm({ ...form, cover_image: e.target.value })} /></div>
            <div className="sm:col-span-2"><Label>Descrição</Label><Textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
            <div className="sm:col-span-2"><Button type="submit" className="btn-terra w-full rounded-xl">Salvar</Button></div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
