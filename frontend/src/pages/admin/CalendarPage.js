import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/apiClient";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const STATUS_LABEL = {
  pending: "Pendente", confirmed: "Confirmada", cancelled: "Cancelada",
  blocked: "Bloqueado", maintenance: "Manutenção", checked_in: "Check-in", checked_out: "Check-out",
};

function ymd(d) { return d.toISOString().slice(0, 10); }
function monthMatrix(year, month) {
  const first = new Date(year, month, 1);
  const start = new Date(first); start.setDate(first.getDate() - first.getDay());
  const weeks = [];
  for (let w = 0; w < 6; w++) {
    const row = [];
    for (let d = 0; d < 7; d++) {
      row.push(new Date(start.getFullYear(), start.getMonth(), start.getDate() + w * 7 + d));
    }
    weeks.push(row);
  }
  return weeks;
}

export default function CalendarPage() {
  const [cursor, setCursor] = useState(() => { const d = new Date(); d.setDate(1); return d; });
  const [reservations, setReservations] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [roomFilter, setRoomFilter] = useState("all");

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
      } catch { /* ignore */ }
    });
    return map;
  }, [filtered]);

  const weeks = monthMatrix(cursor.getFullYear(), cursor.getMonth());
  const monthLabel = cursor.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });

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
            return (
              <div key={i} className={`min-h-[100px] border-b border-r border-stone-100 p-2 ${inMonth ? "bg-white" : "bg-stone-50/60"}`} data-testid={`cal-cell-${key}`}>
                <div className={`text-xs font-mono ${inMonth ? "text-stone-700" : "text-stone-400"}`}>{d.getDate()}</div>
                <div className="mt-1 space-y-1">
                  {items.slice(0, 3).map((r) => (
                    <div key={r.id} className={`px-1.5 py-0.5 rounded text-[10px] text-white truncate`} title={`${r.guest_name} · ${STATUS_LABEL[r.status]}`}
                      style={{ background: {
                        pending: "#ED6C02", confirmed: "#2E7D32", cancelled: "#D32F2F",
                        blocked: "#616161", maintenance: "#8D6E63", checked_in: "#0288D1", checked_out: "#7B1FA2"
                      }[r.status] || "#78716C" }}>
                      {r.guest_name || "Reservado"}
                    </div>
                  ))}
                  {items.length > 3 && <div className="text-[10px] text-stone-500">+{items.length - 3}</div>}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-4 text-xs text-stone-600">
        {Object.entries(STATUS_LABEL).map(([k, v]) => (
          <div key={k} className="flex items-center gap-1.5"><span className={`status-dot status-${k}`} /> {v}</div>
        ))}
      </div>
    </div>
  );
}
