import { VAC_STATUS, Badge, fmtDate } from "@/lib/hrUtils";

export const VacationPeriods = ({ periods, testid = "vac-periods" }) => (
  <div className="overflow-x-auto" data-testid={testid}>
    <table className="w-full text-sm min-w-[520px]">
      <thead className="text-[10px] uppercase tracking-widest text-stone-500">
        <tr><th className="text-left py-1">Aquisitivo</th><th className="text-left">Concessivo até</th><th>Usado</th><th>Pendente</th><th>Saldo</th><th>Situação</th></tr>
      </thead>
      <tbody className="divide-y divide-stone-100">
        {periods.length === 0 && <tr><td colSpan={6} className="py-2 text-stone-400">Sem períodos aquisitivos ainda.</td></tr>}
        {periods.map((p) => (
          <tr key={p.period_start} data-testid={`period-${p.period_start}`}>
            <td className="py-1.5 font-mono text-xs">{fmtDate(p.period_start)} – {fmtDate(p.period_end)}</td>
            <td className="font-mono text-xs">{fmtDate(p.concessive_end)}</td>
            <td className="text-center">{p.used_days}d</td>
            <td className="text-center">{p.pending_days}d</td>
            <td className="text-center font-semibold">{p.balance}d</td>
            <td className="text-center"><Badge map={VAC_STATUS} value={p.status} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);
