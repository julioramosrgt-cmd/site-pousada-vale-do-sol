import { fmtMin, fmtDate, WEEKDAYS, PUNCH_LABELS } from "@/lib/hrUtils";
import { X } from "lucide-react";

const Summary = ({ s }) => (
  <div className="grid grid-cols-3 sm:grid-cols-6 gap-2" data-testid="timesheet-summary">
    {[["Previsto", fmtMin(s.expected_min)], ["Trabalhado", fmtMin(s.worked_min)], ["HE 50%", fmtMin(s.extra50_min)],
      ["HE 100%", fmtMin(s.extra100_min)], ["Noturno", fmtMin(s.night_min)], ["Faltas", s.absences]].map(([l, v]) => (
      <div key={l} className="rounded-xl bg-stone-50 border border-stone-200 px-3 py-2">
        <div className="text-[10px] uppercase tracking-widest text-stone-500">{l}</div>
        <div className="font-mono text-sm text-stone-900" data-testid={`ts-sum-${l.toLowerCase().replace(/[^a-z0-9]/g, "")}`}>{v}</div>
      </div>
    ))}
  </div>
);

const Mark = ({ r, onVoid }) => (
  <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded font-mono text-[11px] ${r.voided ? "line-through bg-stone-100 text-stone-400" : r.source === "portal" ? "bg-stone-100 text-stone-800" : "bg-sky-50 text-sky-800"}`}
    title={`${PUNCH_LABELS[r.type]} · NSR ${r.nsr} · IP ${r.ip || "-"}${r.reason ? ` · Ajuste: ${r.reason}` : ""}${r.void_reason ? ` · Desconsiderada: ${r.void_reason}` : ""}`}
    data-testid={`mark-${r.id}`}>
    {r.time.slice(0, 5)}{r.source !== "portal" && "*"}
    {onVoid && !r.voided && <button onClick={() => onVoid(r)} className="hover:text-red-600" data-testid={`void-${r.id}`} aria-label="Desconsiderar"><X className="w-3 h-3" /></button>}
  </span>
);

export const TimesheetTable = ({ data, onVoid }) => (
  <div className="space-y-3">
    <Summary s={data.summary} />
    <div className="rounded-2xl bg-white border border-stone-200 overflow-x-auto">
      <table className="w-full text-sm min-w-[640px]" data-testid="timesheet-table">
        <thead className="bg-stone-50 text-[10px] uppercase tracking-widest text-stone-500">
          <tr><th className="text-left px-3 py-2">Dia</th><th className="text-left px-3">Marcações</th><th className="px-2">Previsto</th><th className="px-2">Trab.</th><th className="px-2">HE</th><th className="text-left px-3">Obs.</th></tr>
        </thead>
        <tbody className="divide-y divide-stone-100">
          {data.days.map((d) => {
            const wd = (new Date(d.date + "T12:00").getDay() + 6) % 7;
            const marks = onVoid ? d.all_records : d.records;
            const obs = [d.is_vacation ? "Férias" : d.is_rest ? "Folga" : "", d.holiday, ...d.flags].filter(Boolean);
            return (
              <tr key={d.date} className={d.is_rest ? "bg-emerald-50/40" : ""} data-testid={`ts-row-${d.date}`}>
                <td className="px-3 py-1.5 font-mono text-xs whitespace-nowrap">{fmtDate(d.date).slice(0, 5)} <span className="text-stone-400">{WEEKDAYS[wd]}</span></td>
                <td className="px-3 py-1.5"><div className="flex flex-wrap gap-1">{marks.map((r) => <Mark key={r.id} r={r} onVoid={onVoid} />)}</div></td>
                <td className="px-2 text-center font-mono text-xs">{fmtMin(d.expected_min)}</td>
                <td className="px-2 text-center font-mono text-xs">{fmtMin(d.worked_min)}</td>
                <td className="px-2 text-center font-mono text-xs">{d.extra50_min + d.extra100_min ? fmtMin(d.extra50_min + d.extra100_min) : "-"}</td>
                <td className="px-3 text-xs">{obs.map((o) => <span key={o} className={`mr-1 ${o === "Falta" || o.startsWith("Marcação") || o.startsWith("Intervalo") ? "text-red-600" : "text-stone-500"}`}>{o}</span>)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
    <p className="text-[11px] text-stone-500">* marcação incluída pelo RH. Passe o mouse para ver NSR, IP e justificativa. Tolerância de 10 min/dia (art. 58 §1º).</p>
  </div>
);
