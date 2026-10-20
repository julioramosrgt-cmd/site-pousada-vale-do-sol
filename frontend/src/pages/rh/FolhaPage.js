import { useEffect, useState } from "react";
import { api } from "@/lib/apiClient";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { brl, currentMonth, downloadPdf } from "@/lib/hrUtils";
import { FileDown, Info } from "lucide-react";

export default function FolhaPage() {
  const [month, setMonth] = useState(currentMonth());
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get(`/hr/payroll?month=${month}`).then((r) => setData(r.data)).catch((e) => toast.error(e?.response?.data?.detail || "Falha"));
  }, [month]);

  const pdf = (r) => downloadPdf(api, `/hr/payroll/pdf?employee_id=${r.employee_id}&month=${month}`, `holerite-previa-${r.employee_name}-${month}.pdf`)
    .catch(() => toast.error("Falha ao gerar PDF"));
  const val = (r, code) => [...r.earnings, ...r.deductions].find((x) => x.code === code)?.value || 0;

  return (
    <div className="space-y-5" data-testid="folha-page">
      <div className="flex flex-wrap items-end gap-3">
        <div className="mr-auto">
          <h1 className="font-serif text-2xl text-stone-900">Folha de pagamento <span className="ml-1 align-middle text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-800" data-testid="folha-preview-badge">PRÉVIA</span></h1>
          <p className="text-sm text-stone-500">Calculada a partir do ponto eletrônico.</p>
        </div>
        <div><Label className="text-xs">Competência</Label><Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="w-40" data-testid="folha-month" /></div>
      </div>

      <div className="rounded-2xl bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900 flex gap-2" data-testid="folha-disclaimer">
        <Info className="w-4 h-4 shrink-0" />
        <span>Estimativa sem valor fiscal. {data?.tables}. Não inclui férias, 13º, VT, benefícios ou convenção coletiva — confira com a contabilidade.</span>
      </div>

      {data && (
        <div className="rounded-2xl bg-white border border-stone-200 overflow-x-auto">
          <table className="w-full text-sm min-w-[900px]" data-testid="folha-table">
            <thead className="bg-stone-50 text-[10px] uppercase tracking-widest text-stone-500">
              <tr>{["Colaborador", "Base", "HE 50%", "HE 100%", "Noturno", "DSR", "Faltas/atrasos", "Bruto", "INSS", "IRRF", "Líquido", "FGTS", ""].map((h) => <th key={h} className="px-3 py-2 text-right first:text-left">{h}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {data.rows.length === 0 && <tr><td colSpan={13} className="px-3 py-3 text-stone-400">Nenhum colaborador ativo.</td></tr>}
              {data.rows.map((r) => (
                <tr key={r.employee_id} data-testid={`folha-row-${r.employee_id}`}>
                  <td className="px-3 py-2"><div className="font-medium">{r.employee_name}</div><div className="text-xs text-stone-500">{r.role_title}</div></td>
                  {[r.base_salary, val(r, "010"), val(r, "011"), val(r, "020"), val(r, "030"), val(r, "101") + val(r, "102"), r.gross, r.inss, r.irrf.value].map((v, i) => <td key={i} className="px-3 text-right font-mono text-xs">{brl(v)}</td>)}
                  <td className="px-3 text-right font-mono text-xs font-semibold" data-testid={`folha-net-${r.employee_id}`}>{brl(r.net)}</td>
                  <td className="px-3 text-right font-mono text-xs text-stone-500">{brl(r.fgts)}</td>
                  <td className="px-3 text-right"><Button size="sm" variant="ghost" onClick={() => pdf(r)} data-testid={`folha-pdf-${r.employee_id}`}><FileDown className="w-4 h-4" /></Button></td>
                </tr>
              ))}
            </tbody>
            {data.rows.length > 0 && (
              <tfoot className="bg-stone-50 font-medium" data-testid="folha-totals">
                <tr><td className="px-3 py-2">Totais</td><td colSpan={6} /><td className="px-3 text-right font-mono text-xs">{brl(data.totals.gross)}</td>
                  <td className="px-3 text-right font-mono text-xs">{brl(data.totals.inss)}</td><td className="px-3 text-right font-mono text-xs">{brl(data.totals.irrf)}</td>
                  <td className="px-3 text-right font-mono text-xs">{brl(data.totals.net)}</td><td className="px-3 text-right font-mono text-xs">{brl(data.totals.fgts)}</td><td /></tr>
              </tfoot>
            )}
          </table>
        </div>
      )}
    </div>
  );
}
