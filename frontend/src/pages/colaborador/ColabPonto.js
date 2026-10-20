import { useEffect, useState } from "react";
import { colabApi } from "@/lib/colabAuth";
import { TimesheetTable } from "@/components/hr/TimesheetTable";
import { currentMonth } from "@/lib/hrUtils";

export default function ColabPonto() {
  const [month, setMonth] = useState(currentMonth());
  const [data, setData] = useState(null);

  useEffect(() => {
    colabApi.get(`/employee/timesheet?month=${month}`).then((r) => setData(r.data)).catch(() => {});
  }, [month]);

  return (
    <div className="space-y-4" data-testid="colab-ponto">
      <div className="flex items-center justify-between">
        <h1 className="font-serif text-xl text-stone-900">Meu espelho de ponto</h1>
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="rounded-md border border-stone-200 px-2 py-1 text-sm" data-testid="colab-ponto-month" />
      </div>
      {data && <TimesheetTable data={data} />}
    </div>
  );
}
