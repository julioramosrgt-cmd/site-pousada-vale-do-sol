"""Regras CLT puras (sem I/O): escala, ponto, férias e folha (prévia)."""
import calendar as cal
from datetime import date, datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

from holidays import is_brazilian_holiday

BR_TZ = ZoneInfo("America/Sao_Paulo")
PUNCH_SEQUENCE = ["entrada", "inicio_intervalo", "fim_intervalo", "saida"]
PUNCH_LABELS = {"entrada": "Entrada", "inicio_intervalo": "Início do intervalo",
                "fim_intervalo": "Fim do intervalo", "saida": "Saída"}
TOLERANCE_MIN = 10  # art. 58 §1º CLT
NIGHT_START, NIGHT_END = 22 * 60, 5 * 60  # art. 73 CLT

# Tabelas 2026 (Portaria Interministerial MPS/MF 13/2026 · Lei 15.270/2025)
INSS_TABLE = [(1621.00, 0.075), (2902.84, 0.09), (4354.27, 0.12), (8475.55, 0.14)]
IRRF_TABLE = [(2428.80, 0.0, 0.0), (2826.65, 0.075, 182.16), (3751.05, 0.15, 394.16),
              (4664.68, 0.225, 675.49), (float("inf"), 0.275, 908.73)]
IRRF_DEPENDENT = 189.59
IRRF_SIMPLIFIED = 607.20
TABLES_REF = "INSS 2026 (Portaria MPS/MF 13/2026) · IRRF 2026 + redutor Lei 15.270/2025"


def hhmm_to_min(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    h, m = s.split(":")[:2]
    return int(h) * 60 + int(m)


def shift_expected_minutes(shift: Optional[dict]) -> int:
    if not shift or shift.get("is_rest") or not shift.get("start_time") or not shift.get("end_time"):
        return 0
    span = hhmm_to_min(shift["end_time"]) - hhmm_to_min(shift["start_time"])
    if span <= 0:
        span += 24 * 60
    return span - 60 if span > 6 * 60 else span


# ---------------------------------------------------------------- Escala
def generate_shifts(employee: dict, year: int, month: int, new_id) -> List[dict]:
    """5x2 com rodízio de domingos (1 domingo de folga a cada N semanas)."""
    _, days = cal.monthrange(year, month)
    rest_days = set(employee.get("weekly_rest_days") or [5, 6])
    start_t = employee.get("default_shift_start") or "08:00"
    end_t = employee.get("default_shift_end") or "17:00"
    shifts = []
    for day in range(1, days + 1):
        d = date(year, month, day)
        wd = d.weekday()
        is_rest = wd in rest_days
        hol, hol_name = is_brazilian_holiday(d)
        shifts.append({"id": new_id(), "employee_id": employee["id"], "date": d.isoformat(), "weekday": wd,
                       "start_time": None if is_rest else start_t, "end_time": None if is_rest else end_t,
                       "is_rest": is_rest, "is_dsr": is_rest and wd == 6, "is_vacation": False,
                       "is_holiday": hol, "source": "auto", "notes": hol_name or ""})
    if 6 not in rest_days:
        _sunday_rotation(shifts, employee, start_t, end_t)
    for s in shifts:
        if s["is_holiday"] and not s["is_rest"]:
            s.update(is_rest=True, start_time=None, end_time=None)
    return shifts


def _sunday_rotation(shifts: List[dict], employee: dict, start_t: str, end_t: str):
    every = int(employee.get("sunday_rest_every_weeks") or 3)
    sundays = [s for s in shifts if s["weekday"] == 6]
    offset = int(employee.get("sunday_offset") or 0) % every
    for idx, sun in enumerate(sundays):
        if idx % every != offset:
            continue
        sun.update(is_rest=True, is_dsr=True, start_time=None, end_time=None)
        sun_d = date.fromisoformat(sun["date"])
        week = [s for s in shifts if sun_d - timedelta(days=6) <= date.fromisoformat(s["date"]) < sun_d]
        swap = next((s for s in reversed(week) if s["is_rest"]), None)
        if not swap:
            nxt = [s for s in shifts if sun_d < date.fromisoformat(s["date"]) <= sun_d + timedelta(days=6)]
            swap = next((s for s in nxt if s["is_rest"] and s["weekday"] != 6), None)
        if swap:
            swap.update(is_rest=False, is_dsr=False, start_time=start_t, end_time=end_t)


def validate_schedule(shifts: List[dict], employee: dict) -> List[dict]:
    """Retorna violações CLT: interjornada, dias consecutivos, rodízio de domingos, jornada."""
    out = []
    ordered = sorted(shifts, key=lambda s: s["date"])
    work = [s for s in ordered if not s.get("is_rest") and s.get("start_time") and s.get("end_time")]
    for prev, cur in zip(work, work[1:]):
        prev_end = datetime.fromisoformat(f"{prev['date']}T{prev['end_time']}")
        if prev["end_time"] < prev["start_time"]:
            prev_end += timedelta(days=1)
        gap = (datetime.fromisoformat(f"{cur['date']}T{cur['start_time']}") - prev_end).total_seconds() / 3600
        if gap < 11:
            out.append({"rule": "interjornada", "date": cur["date"],
                        "message": f"Interjornada de {gap:.1f}h entre {prev['date']} e {cur['date']} (mín. 11h — art. 66)"})
    streak = 0
    for s in ordered:
        streak = 0 if s.get("is_rest") else streak + 1
        if streak == 7:
            out.append({"rule": "dsr_7dias", "date": s["date"],
                        "message": f"7º dia consecutivo de trabalho em {s['date']} (DSR — art. 67 / OJ 410 TST)"})
    every = int(employee.get("sunday_rest_every_weeks") or 3)
    sunday_streak = 0
    for s in ordered:
        if s["weekday"] != 6:
            continue
        sunday_streak = 0 if s.get("is_rest") else sunday_streak + 1
        if sunday_streak == every:
            out.append({"rule": "rodizio_domingo", "date": s["date"],
                        "message": f"{every} domingos seguidos trabalhados até {s['date']} (rodízio — Lei 10.101 art. 6º)"})
    for s in work:
        if shift_expected_minutes(s) > 10 * 60:
            out.append({"rule": "jornada_diaria", "date": s["date"],
                        "message": f"Jornada acima de 10h em {s['date']} (8h + 2h extras — art. 59)"})
    weekly_limit = int(employee.get("weekly_hours") or 44) * 60
    weeks: dict = {}
    for s in work:
        iso = date.fromisoformat(s["date"]).isocalendar()
        weeks[(iso[0], iso[1])] = weeks.get((iso[0], iso[1]), 0) + shift_expected_minutes(s)
    for (y, w), mins in weeks.items():
        if mins > weekly_limit + 120:
            out.append({"rule": "jornada_semanal", "date": f"{y}-W{w:02d}",
                        "message": f"Semana {w}: {mins / 60:.1f}h escaladas (limite {weekly_limit // 60}h)"})
    return out


# ---------------------------------------------------------------- Ponto
def to_local(ts_iso: str) -> datetime:
    return datetime.fromisoformat(ts_iso).astimezone(BR_TZ)


def _night_minutes(start: datetime, end: datetime) -> int:
    total, cur = 0, start
    while cur < end:
        m = cur.hour * 60 + cur.minute
        if m >= NIGHT_START or m < NIGHT_END:
            total += 1
        cur += timedelta(minutes=1)
    return total


def compute_day(records: List[dict], shift: Optional[dict], day: str) -> dict:
    valid = sorted([r for r in records if not r.get("voided")], key=lambda r: r["ts"])
    worked = night = 0
    breaks = []
    for i in range(0, len(valid) - 1, 2):
        a, b = to_local(valid[i]["ts"]), to_local(valid[i + 1]["ts"])
        worked += int((b - a).total_seconds() // 60)
        night += _night_minutes(a, b)
        if i + 2 < len(valid):
            breaks.append(int((to_local(valid[i + 2]["ts"]) - b).total_seconds() // 60))
    expected = shift_expected_minutes(shift)
    is_rest = bool(shift and shift.get("is_rest"))
    is_vacation = bool(shift and shift.get("is_vacation"))
    is_hol, hol_name = is_brazilian_holiday(date.fromisoformat(day))
    diff = worked - expected
    if abs(diff) <= TOLERANCE_MIN:
        diff = 0
    flags = []
    if len(valid) % 2 == 1:
        flags.append("Marcação ímpar — falta registro")
    if worked > 6 * 60 and (not breaks or max(breaks) < 60):
        flags.append("Intervalo < 1h (art. 71)")
    past = day < datetime.now(BR_TZ).date().isoformat()
    absent = expected > 0 and not valid and not is_vacation and not is_hol and past
    if absent:
        flags.append("Falta")
    if diff > 120:
        flags.append("HE acima de 2h (art. 59)")
    extra = max(diff, 0) if not absent else 0
    extra_100 = worked if (is_rest or is_hol) and worked else 0
    return {
        "date": day, "records": valid, "worked_min": worked, "expected_min": expected,
        "extra50_min": 0 if extra_100 else extra, "extra100_min": extra_100,
        "missing_min": max(-diff, 0) if valid and past else 0, "night_min": night,
        "absent": absent, "is_rest": is_rest, "is_vacation": is_vacation,
        "holiday": hol_name, "flags": flags,
    }


def summarize_month(days: List[dict]) -> dict:
    keys = ["worked_min", "expected_min", "extra50_min", "extra100_min", "missing_min", "night_min"]
    s = {k: sum(d[k] for d in days) for k in keys}
    s["absences"] = sum(1 for d in days if d["absent"])
    s["absence_weeks"] = len({date.fromisoformat(d["date"]).isocalendar()[1] for d in days if d["absent"]})
    return s


# ---------------------------------------------------------------- Férias
def _add_years(d: date, n: int) -> date:
    try:
        return d.replace(year=d.year + n)
    except ValueError:
        return d.replace(year=d.year + n, day=28)


def vacation_periods(employee: dict, vacations: List[dict], today: date) -> List[dict]:
    hire = date.fromisoformat(employee["hire_date"])
    out, k = [], 0
    while _add_years(hire, k) <= today:
        start = _add_years(hire, k)
        end = _add_years(hire, k + 1) - timedelta(days=1)
        concess_end = _add_years(hire, k + 2) - timedelta(days=1)
        related = [v for v in vacations if v.get("period_start") == start.isoformat()
                   and v.get("status") in ("approved", "pending")]
        used = sum(v["days"] + v.get("sell_days", 0) for v in related if v["status"] == "approved")
        pending = sum(v["days"] + v.get("sell_days", 0) for v in related if v["status"] == "pending")
        balance = 30 - used
        if end >= today:
            status = "em_aquisicao"
        elif balance <= 0:
            status = "quitado"
        elif concess_end < today:
            status = "vencido"
        elif (concess_end - today).days <= 60:
            status = "vencendo"
        else:
            status = "disponivel"
        out.append({"period_start": start.isoformat(), "period_end": end.isoformat(),
                    "concessive_end": concess_end.isoformat(), "used_days": used, "pending_days": pending,
                    "balance": balance, "status": status, "fractions": len(related),
                    "has_14": any(v["days"] >= 14 for v in related)})
        k += 1
    return out


def validate_vacation_request(period: dict, start: date, days: int, sell_days: int, today: date) -> Optional[str]:
    if period["status"] == "em_aquisicao":
        return "Período aquisitivo ainda não completado"
    if start <= today:
        return "A data de início deve ser futura"
    if days < 5 or days > 30:
        return "Cada período deve ter entre 5 e 30 dias (art. 134 §1º)"
    if sell_days < 0 or sell_days > 10:
        return "Abono pecuniário limitado a 1/3 (10 dias — art. 143)"
    available = period["balance"] - period["pending_days"]
    if days + sell_days > available:
        return f"Saldo insuficiente: {available} dia(s) disponíveis"
    if period["fractions"] >= 3:
        return "Máximo de 3 períodos por aquisitivo (art. 134 §1º)"
    remaining = available - days - sell_days
    if not period["has_14"] and days < 14 and remaining < 14:
        return "Um dos períodos precisa ter no mínimo 14 dias (art. 134 §1º)"
    for i in (1, 2):
        d = start + timedelta(days=i)
        if d.weekday() == 6 or is_brazilian_holiday(d)[0]:
            return "Férias não podem iniciar nos 2 dias que antecedem feriado ou DSR (art. 134 §3º)"
    return None


# ---------------------------------------------------------------- Folha (prévia)
def calc_inss(base: float) -> float:
    total, prev = 0.0, 0.0
    for limit, rate in INSS_TABLE:
        if base <= prev:
            break
        total += (min(base, limit) - prev) * rate
        prev = limit
    return round(total, 2)


def calc_irrf(gross: float, inss: float, dependents: int) -> dict:
    legal = inss + dependents * IRRF_DEPENDENT
    deduction = max(legal, IRRF_SIMPLIFIED)
    base = max(gross - deduction, 0)
    tax = 0.0
    for limit, rate, ded in IRRF_TABLE:
        if base <= limit:
            tax = max(base * rate - ded, 0)
            break
    if gross <= 5000:
        reduction = min(312.89, tax)
    elif gross < 7350:
        reduction = min(max(978.62 - 0.133145 * gross, 0), tax)
    else:
        reduction = 0
    return {"base": round(base, 2), "deduction": "simplificado" if deduction == IRRF_SIMPLIFIED and IRRF_SIMPLIFIED > legal else "legal",
            "tax_table": round(tax, 2), "reduction": round(reduction, 2), "value": round(tax - reduction, 2)}


def calc_payroll(employee: dict, summary: dict, working_days: int, rest_days: int, month: str = "") -> dict:
    salary = float(employee.get("base_salary") or 0)
    hire = employee.get("hire_date") or ""
    salary_due, days_ref = salary, 30
    if month and hire[:7] == month:
        days_ref = max(30 - int(hire[8:10]) + 1, 0)
        salary_due = salary / 30 * days_ref
    divisor = int(employee.get("weekly_hours") or 44) * 5
    hour = salary / divisor if divisor else 0
    day_value = salary / 30
    e50 = round(summary["extra50_min"] / 60 * hour * 1.5, 2)
    e100 = round(summary["extra100_min"] / 60 * hour * 2.0, 2)
    night_hours = summary["night_min"] / 52.5  # hora noturna reduzida
    night = round(night_hours * hour * 0.20, 2)
    dsr = round((e50 + e100 + night) / working_days * rest_days, 2) if working_days else 0.0
    absences = round(summary["absences"] * day_value + summary["absence_weeks"] * day_value, 2)
    delays = round(summary["missing_min"] / 60 * hour, 2)
    gross = round(max(salary_due + e50 + e100 + night + dsr - absences - delays, 0), 2)
    inss = calc_inss(gross)
    irrf = calc_irrf(gross, inss, int(employee.get("dependents") or 0))
    return {
        "employee_id": employee["id"], "employee_name": employee["name"], "role_title": employee.get("role_title"),
        "base_salary": round(salary, 2), "hour_value": round(hour, 2),
        "earnings": [
            {"code": "001", "label": "Salário base" + (" (proporcional)" if days_ref < 30 else ""), "ref": f"{days_ref}d", "value": round(salary_due, 2)},
            {"code": "010", "label": "Horas extras 50%", "ref": f"{summary['extra50_min'] / 60:.2f}h", "value": e50},
            {"code": "011", "label": "Horas extras 100%", "ref": f"{summary['extra100_min'] / 60:.2f}h", "value": e100},
            {"code": "020", "label": "Adicional noturno 20%", "ref": f"{night_hours:.2f}h", "value": night},
            {"code": "030", "label": "DSR s/ variáveis", "ref": f"{rest_days}d", "value": dsr},
        ],
        "deductions": [
            {"code": "101", "label": "Faltas + DSR perdido", "ref": f"{summary['absences']}d", "value": absences},
            {"code": "102", "label": "Atrasos/saídas antecipadas", "ref": f"{summary['missing_min'] / 60:.2f}h", "value": delays},
            {"code": "201", "label": "INSS", "ref": "progressivo", "value": inss},
            {"code": "202", "label": "IRRF", "ref": irrf["deduction"], "value": irrf["value"]},
        ],
        "gross": gross, "inss": inss, "irrf": irrf,
        "net": round(gross - inss - irrf["value"], 2),
        "fgts": round(gross * 0.08, 2),
        "summary": summary, "preview": True, "tables": TABLES_REF,
    }
