import { useEffect, useState } from "react";
import { api } from "@/lib/apiClient";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";

const COLORS = {
  free: "bg-stone-100",
  pending: "bg-orange-400",
  confirmed: "bg-emerald-600",
  checked_in: "bg-sky-500",
  checked_out: "bg-purple-500",
  blocked: "bg-stone-500",
  maintenance: "bg-amber-800",
  cancelled: "bg-stone-100",
};

const LABEL = {
  free: "Livre", pending: "Pendente", confirmed: "Confirmada",
  checked_in: "Check-in", checked_out: "Check-out",
  blocked: "Bloqueado", maintenance: "Manutenção",
};

export default function HeatmapPage() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get(`/reports/occupancy?year=${year}&month=${month}`).then((r) => setData(r.data));
  }, [year, month]);

  const prev = () => {
    let y = year, m = month - 1;
    if (m < 1) { m = 12; y -= 1; }
    setYear(y); setMonth(m);
  };
  const next = () => {
    let y = year, m = month + 1;
    if (m > 12) { m = 1; y += 1; }
    setYear(y); setMonth(m);
  };

  const label = new Date(year, month - 1, 1).toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
  const dayNums = data ? Array.from({ length: data.days }, (_, i) => i + 1) : [];

  // Occupancy % overall
  let filled = 0, total = 0;
  if (data) {
    data.rooms.forEach((r) => r.cells.forEach((c) => {
      total += 1;
      if (["confirmed", "checked_in", "checked_out", "blocked", "maintenance", "pending"].includes(c)) filled += 1;
    }));
  }
  const occ = total ? Math.round((filled / total) * 100) : 0;

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-6">
        <div>
          <span className="text-xs uppercase tracking-widest text-amber-800/70">Relatório</span>
          <h1 className="font-serif text-3xl sm:text-4xl capitalize">Ocupação · {label}</h1>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-sm text-stone-600">Ocupação geral: <span className="font-mono text-[color:var(--pousada-terracotta)] font-semibold">{occ}%</span></div>
          <Button variant="outline" size="icon" onClick={prev} data-testid="heat-prev"><ChevronLeft className="w-4 h-4" /></Button>
          <Button variant="outline" size="icon" onClick={next} data-testid="heat-next"><ChevronRight className="w-4 h-4" /></Button>
        </div>
      </div>

      {!data ? <p className="text-stone-500">Carregando...</p> : data.rooms.length === 0 ? (
        <p className="text-stone-500">Cadastre quartos para ver o mapa de ocupação.</p>
      ) : (
        <div className="rounded-2xl bg-white border border-stone-200/70 shadow-warm p-4 overflow-x-auto">
          <table className="text-xs">
            <thead>
              <tr>
                <th className="p-1 sticky left-0 bg-white text-left"></th>
                {dayNums.map((d) => <th key={d} className="p-1 font-mono text-stone-500 text-[10px] w-6 text-center">{d}</th>)}
              </tr>
            </thead>
            <tbody>
              {data.rooms.map((room) => (
                <tr key={room.id}>
                  <td className="p-1 sticky left-0 bg-white pr-3 font-medium whitespace-nowrap max-w-[160px] truncate" title={room.name}>{room.name}</td>
                  {room.cells.map((c, i) => (
                    <td key={i} className="p-0.5">
                      <div title={`Dia ${i + 1} — ${LABEL[c] || c}`} className={`w-6 h-6 rounded ${COLORS[c] || "bg-stone-100"}`} data-testid={`cell-${room.id}-${i + 1}`} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-3 text-xs">
        {Object.entries(LABEL).map(([k, v]) => (
          <div key={k} className="flex items-center gap-1.5"><span className={`inline-block w-3 h-3 rounded ${COLORS[k]}`} /> {v}</div>
        ))}
      </div>
    </div>
  );
}
