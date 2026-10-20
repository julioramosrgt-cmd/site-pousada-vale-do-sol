export const fmtMin = (m) => `${String(Math.floor((m || 0) / 60)).padStart(2, "0")}:${String((m || 0) % 60).padStart(2, "0")}`;
export const brl = (v) => (v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
export const fmtDate = (iso) => (iso ? iso.split("-").reverse().join("/") : "-");
export const currentMonth = () => new Date().toLocaleDateString("sv-SE", { timeZone: "America/Sao_Paulo" }).slice(0, 7);
export const WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
export const PUNCH_LABELS = { entrada: "Entrada", inicio_intervalo: "Início intervalo", fim_intervalo: "Fim intervalo", saida: "Saída" };
export const VAC_STATUS = {
  em_aquisicao: { label: "Em aquisição", cls: "bg-stone-100 text-stone-600" },
  disponivel: { label: "Disponível", cls: "bg-emerald-50 text-emerald-700" },
  vencendo: { label: "Vencendo", cls: "bg-amber-50 text-amber-700" },
  vencido: { label: "Vencido (dobro)", cls: "bg-red-50 text-red-700" },
  quitado: { label: "Quitado", cls: "bg-stone-100 text-stone-500" },
};
export const REQ_STATUS = {
  pending: { label: "Aguardando", cls: "bg-amber-50 text-amber-700" },
  approved: { label: "Aprovado", cls: "bg-emerald-50 text-emerald-700" },
  rejected: { label: "Recusado", cls: "bg-red-50 text-red-700" },
  cancelled: { label: "Cancelado", cls: "bg-stone-100 text-stone-500" },
};

export async function downloadPdf(client, url, filename) {
  const r = await client.get(url, { responseType: "blob" });
  const href = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = href; a.download = filename; a.click();
  URL.revokeObjectURL(href);
}

export const Badge = ({ map, value, testid }) => {
  const s = map[value] || { label: value, cls: "bg-stone-100" };
  return <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-medium ${s.cls}`} data-testid={testid}>{s.label}</span>;
};
