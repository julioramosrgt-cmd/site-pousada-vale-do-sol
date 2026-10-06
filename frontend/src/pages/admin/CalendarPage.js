import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/apiClient";
import { ChevronLeft, ChevronRight, User, BedDouble, Phone, Mail, MessageSquare } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

const STATUS_LABEL = {
  pending: "Pendente", confirmed: "Confirmada", cancelled: "Cancelada",
  blocked: "Bloqueado", maintenance: "Manutenção", checked_in: "Check-in", checked_out: "Check-out",
};
const STATUS_COLOR = {
  pending: "#ED6C02", confirmed: "#2E7D32", cancelled: "#D32F2F",
  blocked: "#616161", maintenance: "#8D6E63", checked_in: "#0288D1", checked_out: "#7B1FA2",
};
const SOURCE_LABEL = { direct: "Direto", public_form: "Site", ota_import: "OTA" };

function fmtDateTime(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }); }
  catch { return iso; }
}

function ymd(d) { return d.toISOString().slice(0, 10); }
function monthMatrix(year, month) {
  const first = new Date(year, month, 1);
  const start = new Date(first); start.setDate(first.getDate() - first.getDay());
  const weeks = [];
  for (let w = 0; w < 6; w++) {
    const row = [];
    for (let d = 0; d < 7; d++) row.push(new Date(start.getFullYear(), start.getMonth(), start.getDate() + w * 7 + d));
    weeks.push(row);
  }
  return weeks;
}

export default function CalendarPage() {
  const [cursor, setCursor] = useState(() => { const d = new Date(); d.setDate(1); return d; });
  const [reservations, setReservations] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [roomFilter, setRoomFilter] = useState("all");
  const [selectedDay, setSelectedDay] = useState(null);

  const load = () => {
    const from = new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1);
    const to = new Date(cursor.getFullYear(), cursor.getMonth() + 2, 0);
    api.get(`/reservations?from_date=${ymd(from)}&to_date=${ymd(to)}`).then((r) => setReservations(r.data));
    api.get("/rooms").then((r) => setRooms(r.data));
  };
  useEffect(load, [cursor]);

  const filtered = useMemo(() => roomFilter === "all" ? reservations : reservations.filter((r) => r.room_id === roomFilter), [roomFilter, reservations]);

  const byDay = useMemo(() => {
    const map = {};
    filtered.forEach((r) => {
      try {
        const ci = new Date(r.checkin_date); const co = new Date(r.checkout_date);
        for (let d = new Date(ci); d < co; d.setDate(d.getDate() + 1)) {
          const k = ymd(d);
          if (!map[k]) map[k] = [];
          map[k].push(r);
        }
      } catch {}
    });
    return map;
  }, [filtered]);

  const roomName = (id) => rooms.find((r) => r.id === id)?.name || "—";
  const weeks = monthMatrix(cursor.getFullYear(), cursor.getMonth());
  const monthLabel = cursor.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
  const dayItems = selectedDay ? (byDay[selectedDay] || []) : [];

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6">
        <div>
          <span className="text-xs uppercase tracking-widest text-amber-800/70">Ocupação</span>
          <h1 className="font-serif text-3xl sm:text-4xl capitalize">{monthLabel}</h1>
        </div>
        <div className="flex items-center gap-3">
          <Select value={roomFilter} onValueChange={setRoomFilter}>
            <SelectTrigger className="w-48" data-testid="calendar-room-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos os quartos</SelectItem>
              {rooms.map((r) => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}
            </SelectContent>
          </Select>
          <button data-testid="cal-prev" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))} className="rounded-lg border border-stone-200 p-2 hover:bg-stone-100"><ChevronLeft className="w-4 h-4" /></button>
          <button data-testid="cal-next" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))} className="rounded-lg border border-stone-200 p-2 hover:bg-stone-100"><ChevronRight className="w-4 h-4" /></button>
        </div>
      </div>

      <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm overflow-hidden">
        <div className="grid grid-cols-7 bg-stone-50 border-b border-stone-100 text-xs uppercase tracking-widest text-stone-500">
          {["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"].map((d) => <div key={d} className="p-3 text-center">{d}</div>)}
        </div>
        <div className="grid grid-cols-7">
          {weeks.flat().map((d, i) => {
            const inMonth = d.getMonth() === cursor.getMonth();
            const key = ymd(d);
            const items = byDay[key] || [];
            const clickable = items.length > 0;
            return (
              <button
                key={i}
                onClick={() => clickable && setSelectedDay(key)}
                className={`text-left min-h-[100px] border-b border-r border-stone-100 p-2 ${inMonth ? "bg-white" : "bg-stone-50/60"} ${clickable ? "hover:bg-orange-50 cursor-pointer" : "cursor-default"}`}
                data-testid={`cal-cell-${key}`}
              >
                <div className={`text-xs font-mono ${inMonth ? "text-stone-700" : "text-stone-400"}`}>{d.getDate()}</div>
                <div className="mt-1 space-y-1">
                  {items.slice(0, 3).map((r) => {
                    const srcShort = SOURCE_LABEL[r.source] || r.source;
                    const tip = `${r.guest_name || "Reservado"}\nOrigem: ${srcShort}${r.ota_source ? ` · ${r.ota_source}` : ""}\nReservado em: ${fmtDateTime(r.created_at)}\nStatus: ${STATUS_LABEL[r.status]}`;
                    return (
                      <div key={r.id} className="px-1.5 py-0.5 rounded text-[10px] text-white truncate" title={tip} style={{ background: STATUS_COLOR[r.status] || "#78716C" }}>
                        {r.guest_name || "Reservado"}
                      </div>
                    );
                  })}
                  {items.length > 3 && <div className="text-[10px] text-stone-500">+{items.length - 3}</div>}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-4 text-xs text-stone-600">
        {Object.entries(STATUS_LABEL).map(([k, v]) => (
          <div key={k} className="flex items-center gap-1.5"><span className={`status-dot status-${k}`} /> {v}</div>
        ))}
      </div>

      <Dialog open={!!selectedDay} onOpenChange={(v) => !v && setSelectedDay(null)}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Reservas em {selectedDay && new Date(selectedDay + "T12:00").toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long", year: "numeric" })}</DialogTitle></DialogHeader>
          {dayItems.length === 0 ? <p className="text-stone-500">Sem reservas.</p> : (
            <ul className="space-y-3">
              {dayItems.map((r) => {
                const wa = (r.guest_phone || "").replace(/\D/g, "");
                return (
                  <li key={r.id} className="rounded-xl border border-stone-200 p-4" data-testid={`day-res-${r.id}`}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2"><User className="w-4 h-4 text-[color:var(--pousada-terracotta)]" /><span className="font-medium">{r.guest_name || "Sem nome"}</span></div>
                      <span className="text-xs px-2 py-0.5 rounded-full text-white" style={{ background: STATUS_COLOR[r.status] || "#78716C" }}>{STATUS_LABEL[r.status]}</span>
                    </div>
                    <div className="text-sm text-stone-600 space-y-1">
                      <div className="flex items-center gap-2"><BedDouble className="w-4 h-4 text-stone-500" />{roomName(r.room_id)}</div>
                      <div className="font-mono text-xs">{r.checkin_date} → {r.checkout_date}</div>
                      <div className="text-xs text-stone-500" data-testid={`day-res-source-${r.id}`}>
                        <span className="uppercase tracking-widest">{SOURCE_LABEL[r.source] || r.source}</span>
                        {r.ota_source ? ` · ${r.ota_source}` : ""} · reservado em {fmtDateTime(r.created_at)}
                      </div>
                      {r.guest_phone && <div className="flex items-center gap-2"><Phone className="w-4 h-4 text-stone-500" />{r.guest_phone}</div>}
                      {r.guest_email && <div className="flex items-center gap-2"><Mail className="w-4 h-4 text-stone-500" />{r.guest_email}</div>}
                    </div>
                    {wa && (
                      <div className="mt-3">
                        <a href={`https://wa.me/${wa}`} target="_blank" rel="noreferrer">
                          <Button size="sm" variant="outline" className="rounded-xl"><MessageSquare className="w-3 h-3 mr-1" />Abrir WhatsApp</Button>
                        </a>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
