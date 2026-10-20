import { useEffect, useMemo, useState } from "react";
import { colabApi } from "@/lib/colabAuth";
import { PunchCard } from "@/components/hr/PunchCard";
import { CalendarDays, Clock, Coffee } from "lucide-react";

const WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
const monthMatrix = (month) => {
  const [y, m] = month.split("-").map(Number);
  const days = new Date(y, m, 0).getDate();
  return Array.from({ length: days }, (_, i) => {
    const d = new Date(y, m - 1, i + 1);
    return { date: d.toISOString().slice(0, 10), weekday: (d.getDay() + 6) % 7, dayNum: i + 1 };
  });
};

export default function ColabDashboard() {
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "America/Sao_Paulo" });
  const [month, setMonth] = useState(today.slice(0, 7));
  const [shifts, setShifts] = useState([]);

  useEffect(() => {
    colabApi.get(`/employee/schedule?month=${month}`).then((r) => setShifts(r.data)).catch(() => {});
  }, [month]);

  const todayShift = shifts.find((s) => s.date === today);
  const grid = useMemo(() => monthMatrix(month), [month]);
  const byDate = useMemo(() => Object.fromEntries(shifts.map((s) => [s.date, s])), [shifts]);

  return (
    <div className="space-y-5" data-testid="colab-dashboard">
      <PunchCard />
      <section className="rounded-2xl bg-white border border-stone-200 p-5" data-testid="today-shift">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-[color:var(--pousada-terracotta)]/10 flex items-center justify-center">
            {todayShift?.is_rest ? <Coffee className="w-6 h-6 text-emerald-600" /> : <Clock className="w-6 h-6 text-[color:var(--pousada-terracotta)]" />}
          </div>
          <div>
            <div className="text-xs text-stone-500 uppercase tracking-widest">Hoje · {new Date(today + "T00:00").toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" })}</div>
            <div className="font-serif text-xl text-stone-900">
              {!todayShift ? "Sem escala para hoje" :
                todayShift.is_rest ? (todayShift.is_vacation ? "Férias" : todayShift.is_dsr ? "Folga — DSR (domingo)" : "Folga rotativa") :
                `${todayShift.start_time} às ${todayShift.end_time}`}
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-2xl bg-white border border-stone-200 p-5" data-testid="month-grid">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-stone-900 font-medium"><CalendarDays className="w-5 h-5" /> Minha escala do mês</div>
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="rounded-md border border-stone-200 px-2 py-1 text-sm" data-testid="colab-month" />
        </div>
        <div className="grid grid-cols-7 gap-1 text-[10px] uppercase tracking-widest text-stone-500 mb-1">
          {WEEKDAYS.map((d) => <div key={d} className="text-center">{d}</div>)}
        </div>
        <div className="grid grid-cols-7 gap-1">
          {Array.from({ length: grid[0]?.weekday || 0 }).map((_, i) => <div key={`pad-${i}`} />)}
          {grid.map((cell) => {
            const s = byDate[cell.date];
            const isRest = s?.is_rest;
            const bg = !s ? "bg-stone-50 text-stone-400 border-stone-100" :
              isRest ? "bg-emerald-50 text-emerald-800 border-emerald-200" :
              "bg-[color:var(--pousada-terracotta)]/10 text-[color:var(--pousada-terracotta)] border-[color:var(--pousada-terracotta)]/30";
            return (
              <div key={cell.date} className={`rounded-lg border p-1.5 h-16 text-left ${bg}`} title={s ? (isRest ? "Folga" : `${s.start_time}–${s.end_time}`) : ""} data-testid={`colab-cell-${cell.date}`}>
                <div className="text-[10px] font-mono">{cell.dayNum}</div>
                {s && (isRest
                  ? <div className="text-[9px] font-medium mt-0.5">{s.is_vacation ? "Férias" : s.is_dsr ? "DSR" : "Folga"}</div>
                  : <div className="text-[9px] font-mono mt-0.5">{s.start_time}</div>)}
              </div>
            );
          })}
        </div>
      </section>

    </div>
  );
}
