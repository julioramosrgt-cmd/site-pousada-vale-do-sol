"""HR module tests: employees, escala/CLT violations, ponto (punch/adjust/void/timesheet/pdf),
férias rules & decisions, folha prévia (INSS/IRRF 2026), dashboard, auth isolation."""
import os
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

STATE = {}


def _emp_payload(name, email, salary=2500.0, rest=(2, 3), dependents=0, every=3, offset=0):
    return {"name": name, "cpf": "00011122233", "role_title": "Camareira", "email": email,
            "hire_date": "2024-03-01", "base_salary": salary, "weekly_hours": 44,
            "weekly_rest_days": list(rest), "default_shift_start": "08:00", "default_shift_end": "17:00",
            "dependents": dependents, "sunday_rest_every_weeks": every, "sunday_offset": offset}


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@pousada.com", "password": "pousada2024"}, timeout=15)
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


@pytest.fixture(scope="module", autouse=True)
def cleanup(admin):
    yield
    for eid in STATE.get("created", []):
        admin.delete(f"{API}/hr/employees/{eid}")
        mdb.time_records.delete_many({"employee_id": eid})
        mdb.vacations.delete_many({"employee_id": eid})
        mdb.shifts.delete_many({"employee_id": eid})


def _create(admin, payload):
    r = admin.post(f"{API}/hr/employees", json=payload)
    assert r.status_code == 200, r.text
    STATE.setdefault("created", []).append(r.json()["id"])
    return r.json()


# ---------------- Employees CRUD
class TestEmployees:
    def test_create_get_update(self, admin):
        e = _create(admin, _emp_payload("TEST_Joao", "test_joao_hr@pousada.com", dependents=2, every=2, offset=1))
        assert e["dependents"] == 2 and e["sunday_rest_every_weeks"] == 2 and e["sunday_offset"] == 1
        assert "portal_password_hash" not in e
        STATE["emp"] = e
        g = admin.get(f"{API}/hr/employees/{e['id']}").json()
        assert g["dependents"] == 2 and g["sunday_offset"] == 1
        upd = _emp_payload("TEST_Joao", "test_joao_hr@pousada.com", dependents=0, every=3, offset=0)
        assert admin.put(f"{API}/hr/employees/{e['id']}", json=upd).status_code == 200
        g = admin.get(f"{API}/hr/employees/{e['id']}").json()
        assert g["dependents"] == 0 and g["sunday_rest_every_weeks"] == 3 and g["sunday_offset"] == 0

    def test_invalid_every(self, admin):
        r = admin.post(f"{API}/hr/employees", json=_emp_payload("TEST_X", "x@x.com", every=0))
        assert r.status_code == 422

    def test_set_portal_password(self, admin):
        r = admin.post(f"{API}/hr/employees/{STATE['emp']['id']}/portal-password", json={"password": "4321"})
        assert r.status_code == 200
        r = requests.post(f"{API}/employee/auth/login", json={"email": "TEST_JOAO_HR@pousada.com", "password": "4321"})
        assert r.status_code == 200, r.text
        STATE["emp_token"] = r.json()["access_token"]
        assert "portal_password_hash" not in r.json()["employee"]


# ---------------- Escala
class TestSchedule:
    def test_generate_nov_rotation(self, admin):
        eid = STATE["emp"]["id"]
        r = admin.post(f"{API}/hr/employees/{eid}/schedule/generate?month=2026-11")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["created"] == 30 and isinstance(d["violations"], list)
        STATE["gen_violations"] = d["violations"]
        shifts = {s["date"]: s for s in admin.get(f"{API}/hr/schedule?month=2026-11&employee_id={eid}").json()}
        STATE["shifts"] = shifts
        # Sundays Nov 1 and Nov 22 off (idx 0 and 3, every=3)
        assert shifts["2026-11-01"]["is_rest"] and shifts["2026-11-22"]["is_rest"]
        assert not shifts["2026-11-08"]["is_rest"] and not shifts["2026-11-15"]["is_rest"]
        # swap: Thu Nov 19 becomes work, Wed Nov 18 stays rest
        assert shifts["2026-11-18"]["is_rest"] and not shifts["2026-11-19"]["is_rest"]
        assert d["violations"] == [], d["violations"]

    def test_invalid_month(self, admin):
        r = admin.post(f"{API}/hr/employees/{STATE['emp']['id']}/schedule/generate?month=2026-13")
        assert r.status_code == 400

    def test_shift_invalid_time(self, admin):
        sid = STATE["shifts"]["2026-11-02"]["id"]
        r = admin.put(f"{API}/hr/shifts/{sid}", json={"start_time": "25:00", "end_time": "17:00"})
        assert r.status_code == 400

    def test_interjornada(self, admin):
        s = STATE["shifts"]
        assert admin.put(f"{API}/hr/shifts/{s['2026-11-02']['id']}", json={"start_time": "14:00", "end_time": "23:00"}).status_code == 200
        assert admin.put(f"{API}/hr/shifts/{s['2026-11-03']['id']}", json={"start_time": "07:00", "end_time": "16:00"}).status_code == 200
        v = admin.get(f"{API}/hr/schedule/violations?month=2026-11&employee_id={STATE['emp']['id']}").json()
        rules = [x["rule"] for x in v]
        assert "interjornada" in rules and any(x["date"] == "2026-11-03" for x in v if x["rule"] == "interjornada")

    def test_7days_sunday_streak_10h(self, admin):
        s = STATE["shifts"]
        eid = STATE["emp"]["id"]
        for d in ("2026-11-04", "2026-11-05", "2026-11-22"):
            r = admin.put(f"{API}/hr/shifts/{s[d]['id']}", json={"is_rest": False})
            assert r.status_code == 200
        admin.put(f"{API}/hr/shifts/{s['2026-11-10']['id']}", json={"start_time": "08:00", "end_time": "20:00"})
        sh = {x["date"]: x for x in admin.get(f"{API}/hr/schedule?month=2026-11&employee_id={eid}").json()}
        assert sh["2026-11-04"]["start_time"] == "08:00" and sh["2026-11-04"]["is_rest"] is False
        v = admin.get(f"{API}/hr/schedule/violations?month=2026-11&employee_id={eid}").json()
        rules = {x["rule"] for x in v}
        assert {"dsr_7dias", "rodizio_domingo", "jornada_diaria"} <= rules, v

    def test_set_rest_clears_times(self, admin):
        sid = STATE["shifts"]["2026-11-22"]["id"]
        assert admin.put(f"{API}/hr/shifts/{sid}", json={"is_rest": True}).status_code == 200
        sh = {x["date"]: x for x in admin.get(f"{API}/hr/schedule?month=2026-11&employee_id={STATE['emp']['id']}").json()}
        assert sh["2026-11-22"]["is_rest"] and sh["2026-11-22"]["start_time"] is None and sh["2026-11-22"]["is_dsr"]


# ---------------- Auth isolation
class TestAuthIsolation:
    def test_emp_cannot_hr(self):
        h = {"Authorization": f"Bearer {STATE['emp_token']}"}
        assert requests.get(f"{API}/hr/employees", headers=h).status_code in (401, 403)
        assert requests.get(f"{API}/hr/dashboard", headers=h).status_code in (401, 403)

    def test_admin_cannot_employee(self, admin):
        assert admin.get(f"{API}/employee/me").status_code == 401
        assert admin.post(f"{API}/employee/punch").status_code == 401


# ---------------- Ponto
class TestPunch:
    def _h(self):
        return {"Authorization": f"Bearer {STATE['emp_token']}"}

    def _backdate(self):
        eid = STATE["emp"]["id"]
        last = mdb.time_records.find_one({"employee_id": eid, "source": "portal"}, sort=[("ts", -1)])
        ts = datetime.fromisoformat(last["ts"]) - timedelta(minutes=2)
        mdb.time_records.update_one({"id": last["id"]}, {"$set": {"ts": ts.isoformat()}})

    def test_sequence(self, admin):
        h = self._h()
        t = requests.get(f"{API}/employee/punches/today", headers=h).json()
        assert t["next_type"] == "entrada" and t["records"] == []
        expected = ["entrada", "inicio_intervalo", "fim_intervalo", "saida"]
        recs = []
        for i, typ in enumerate(expected):
            if i:
                r = requests.post(f"{API}/employee/punch", headers=h)
                assert r.status_code == 429, r.text
                self._backdate()
            r = requests.post(f"{API}/employee/punch", headers=h)
            assert r.status_code == 200, r.text
            rec = r.json()
            assert rec["type"] == typ and rec["ip"] and rec["hash"] and isinstance(rec["nsr"], int)
            recs.append(rec)
            if i == 0:
                d = admin.get(f"{API}/hr/dashboard").json()
                assert any(x["employee"]["id"] == STATE["emp"]["id"] for x in d["working_now"])
            if i == 1:
                d = admin.get(f"{API}/hr/dashboard").json()
                assert any(x["employee"]["id"] == STATE["emp"]["id"] for x in d["on_break"])
        for a, b in zip(recs, recs[1:]):
            assert b["nsr"] > a["nsr"] and b["prev_hash"]
        self._backdate()
        r = requests.post(f"{API}/employee/punch", headers=h)
        assert r.status_code == 400
        t = requests.get(f"{API}/employee/punches/today", headers=h).json()
        assert len(t["records"]) == 4 and t["next_type"] is None

    def test_adjust_and_timesheet(self, admin):
        eid = STATE["emp"]["id"]
        assert admin.post(f"{API}/hr/employees/{eid}/schedule/generate?month=2026-10").status_code == 200
        ids = []
        for tm, typ in (("08:00", "entrada"), ("12:00", "inicio_intervalo"), ("13:00", "fim_intervalo"), ("19:00", "saida")):
            r = admin.post(f"{API}/hr/time-records", json={"employee_id": eid, "date": "2026-10-19", "time": tm,
                                                          "type": typ, "reason": "Esqueceu de bater"})
            assert r.status_code == 200, r.text
            assert r.json()["source"] == "ajuste_rh"
            ids.append(r.json()["id"])
        STATE["adj_ids"] = ids
        ts = admin.get(f"{API}/hr/timesheet?employee_id={eid}&month=2026-10").json()
        day = next(d for d in ts["days"] if d["date"] == "2026-10-19")
        assert day["worked_min"] == 600 and day["expected_min"] == 480 and day["extra50_min"] == 120
        assert ts["summary"]["absences"] > 0  # past working days without punches
        ets = requests.get(f"{API}/employee/timesheet?month=2026-10", headers=self._h()).json()
        assert next(d for d in ets["days"] if d["date"] == "2026-10-19")["worked_min"] == 600

    def test_night_minutes(self, admin):
        eid = STATE["emp"]["id"]
        for tm, typ in (("18:00", "entrada"), ("23:00", "saida")):
            admin.post(f"{API}/hr/time-records", json={"employee_id": eid, "date": "2026-10-16", "time": tm,
                                                      "type": typ, "reason": "Turno noturno teste"})
        ts = admin.get(f"{API}/hr/timesheet?employee_id={eid}&month=2026-10").json()
        day = next(d for d in ts["days"] if d["date"] == "2026-10-16")
        assert day["night_min"] == 60 and day["worked_min"] == 300

    def test_adjust_validation(self, admin):
        eid = STATE["emp"]["id"]
        r = admin.post(f"{API}/hr/time-records", json={"employee_id": eid, "date": "2026-10-19", "time": "10:00", "type": "entrada", "reason": "abc"})
        assert r.status_code == 422
        r = admin.post(f"{API}/hr/time-records", json={"employee_id": eid, "date": "2027-01-01", "time": "10:00", "type": "entrada", "reason": "Futuro teste"})
        assert r.status_code == 400
        r = admin.post(f"{API}/hr/time-records", json={"employee_id": eid, "date": "2026-10-19", "time": "10:00", "type": "xpto", "reason": "Tipo invalido"})
        assert r.status_code == 400

    def test_void(self, admin):
        eid = STATE["emp"]["id"]
        rid = STATE["adj_ids"][3]
        assert admin.post(f"{API}/hr/time-records/{rid}/void", json={"reason": "Lançado errado"}).status_code == 200
        assert admin.post(f"{API}/hr/time-records/{rid}/void", json={"reason": "Lançado errado"}).status_code == 404
        ts = admin.get(f"{API}/hr/timesheet?employee_id={eid}&month=2026-10").json()
        day = next(d for d in ts["days"] if d["date"] == "2026-10-19")
        assert len(day["records"]) == 3 and "Marcação ímpar — falta registro" in day["flags"]

    def test_timesheet_pdf(self, admin):
        r = admin.get(f"{API}/hr/timesheet/pdf?employee_id={STATE['emp']['id']}&month=2026-10")
        assert r.status_code == 200 and r.content[:4] == b"%PDF"


# ---------------- Férias
class TestVacations:
    def _h(self):
        return {"Authorization": f"Bearer {STATE['emp_token']}"}

    def _req(self, **kw):
        body = {"period_start": "2025-03-01", "start_date": "2027-01-04", "days": 15, "sell_days": 0}
        body.update(kw)
        return requests.post(f"{API}/employee/vacations", headers=self._h(), json=body)

    def test_periods(self):
        d = requests.get(f"{API}/employee/vacations", headers=self._h()).json()
        st = {p["period_start"]: p["status"] for p in d["periods"]}
        assert st == {"2024-03-01": "vencido", "2025-03-01": "disponivel", "2026-03-01": "em_aquisicao"}, st

    def test_rules(self):
        assert self._req(period_start="2026-03-01").status_code == 400
        assert self._req(start_date="2026-10-01").status_code == 400
        assert self._req(days=4).status_code in (400, 422)
        assert self._req(sell_days=11).status_code in (400, 422)
        r = self._req(days=10, sell_days=10)
        assert r.status_code == 400 and "14" in r.json()["detail"]
        r = self._req(start_date="2026-11-06")  # Friday -> Sunday in 2 days
        assert r.status_code == 400 and "antecedem" in r.json()["detail"]
        r = self._req(start_date="2026-11-18")  # Nov 20 holiday
        assert r.status_code == 400, r.text

    def test_request_balance_cancel(self):
        r = self._req()
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending" and r.json()["end_date"] == "2027-01-18"
        STATE["vac1"] = r.json()["id"]
        r = self._req(start_date="2027-03-01", days=20)
        assert r.status_code == 400 and "Saldo" in r.json()["detail"]
        r = self._req(start_date="2027-01-11", days=5)
        assert r.status_code == 400  # overlap
        r = self._req(start_date="2027-05-03", days=10)
        assert r.status_code == 200, r.text
        vid = r.json()["id"]
        assert requests.post(f"{API}/employee/vacations/{vid}/cancel", headers=self._h()).status_code == 200
        d = requests.get(f"{API}/employee/vacations", headers=self._h()).json()
        assert next(v for v in d["requests"] if v["id"] == vid)["status"] == "cancelled"

    def test_hr_approve_sets_shifts(self, admin):
        eid = STATE["emp"]["id"]
        admin.post(f"{API}/hr/employees/{eid}/schedule/generate?month=2027-01")
        lst = admin.get(f"{API}/hr/vacations").json()
        mine = next(x for x in lst if x["employee"]["id"] == eid)
        assert any(v["id"] == STATE["vac1"] and v["status"] == "pending" for v in mine["requests"])
        r = admin.post(f"{API}/hr/vacations/{STATE['vac1']}/decision", json={"approve": True})
        assert r.status_code == 200 and r.json()["status"] == "approved"
        sh = admin.get(f"{API}/hr/schedule?month=2027-01&employee_id={eid}").json()
        in_range = [s for s in sh if "2027-01-04" <= s["date"] <= "2027-01-18"]
        assert len(in_range) == 15 and all(s["is_vacation"] for s in in_range)
        assert not any(s["is_vacation"] for s in sh if s["date"] > "2027-01-18")
        assert admin.post(f"{API}/hr/vacations/{STATE['vac1']}/decision", json={"approve": True}).status_code == 404

    def test_hr_reject_and_direct(self, admin):
        r = self._req(start_date="2027-02-01", days=15)
        assert r.status_code == 200, r.text
        r2 = admin.post(f"{API}/hr/vacations/{r.json()['id']}/decision", json={"approve": False, "notes": "Alta temporada"})
        assert r2.json()["status"] == "rejected"
        r = admin.post(f"{API}/hr/vacations", json={"employee_id": STATE["emp"]["id"], "period_start": "2024-03-01",
                                                   "start_date": "2027-03-01", "days": 30, "sell_days": 0})
        assert r.status_code == 200 and r.json()["status"] == "approved", r.text
        d = requests.get(f"{API}/employee/vacations", headers=self._h()).json()
        p = next(x for x in d["periods"] if x["period_start"] == "2024-03-01")
        assert p["balance"] == 0 and p["status"] == "quitado"


# ---------------- Folha prévia
class TestPayroll:
    @pytest.mark.parametrize("salary,deps,inss,irrf", [
        (5000.0, 0, 501.51, 0.0),
        (3000.0, 0, 248.60, 0.0),
        (6000.0, 0, 641.51, 385.11),
        (8000.0, 0, 921.51, 1037.86),
        (8000.0, 2, 921.51, 933.59),
    ])
    def test_inss_irrf(self, admin, salary, deps, inss, irrf):
        e = _create(admin, _emp_payload(f"TEST_Folha{int(salary)}_{deps}", f"test_folha{int(salary)}{deps}@pousada.com", salary=salary, dependents=deps))
        # 2026-12 has no schedule -> no absences/extras -> gross == salary
        d = admin.get(f"{API}/hr/payroll?month=2026-12").json()
        row = next(r for r in d["rows"] if r["employee_id"] == e["id"])
        assert row["preview"] is True and row["gross"] == salary
        assert abs(row["inss"] - inss) <= 0.02, row["inss"]
        assert abs(row["irrf"]["value"] - irrf) <= 0.02, row["irrf"]
        assert abs(row["net"] - (salary - row["inss"] - row["irrf"]["value"])) <= 0.01
        assert row["fgts"] == round(salary * 0.08, 2)
        pdf = admin.get(f"{API}/hr/payroll/pdf?employee_id={e['id']}&month=2026-12")
        assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"

    def test_payroll_with_extras(self, admin):
        d = admin.get(f"{API}/hr/payroll?month=2026-10").json()
        row = next(r for r in d["rows"] if r["employee_id"] == STATE["emp"]["id"])
        e50 = next(x for x in row["earnings"] if x["code"] == "010")
        faltas = next(x for x in row["deductions"] if x["code"] == "101")
        assert faltas["value"] > 0 and "totals" in d

    def test_payroll_bad_month(self, admin):
        assert admin.get(f"{API}/hr/payroll?month=abc").status_code == 400


# ---------------- Dashboard alerts
class TestDashboard:
    def test_dashboard_alerts(self, admin):
        d = admin.get(f"{API}/hr/dashboard").json()
        for k in ("working_now", "on_break", "late", "resting_today", "alerts", "totals"):
            assert k in d
        types = {a["type"] for a in d["alerts"]}
        assert "ferias" in types or "escala" in types
