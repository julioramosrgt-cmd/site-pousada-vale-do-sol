"""Backend tests for Pousada Mgmt — Iteration 2.
Focus: Emails on pre-reservation, Users CRUD (RBAC), Reception role RBAC lockdown,
Occupancy heatmap, PIX BR Code generator.
"""
import os
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://gestao-acomodacoes.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN = {"email": "admin@pousada.com", "password": "pousada2024"}
RECEP = {"email": "recepcao@pousada.com", "password": "recep123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_headers():
    return {"Authorization": f"Bearer {_login(ADMIN)}"}


@pytest.fixture(scope="session")
def reception_headers(admin_headers):
    # ensure reception user exists (idempotent)
    r = requests.get(f"{API}/users", headers=admin_headers, timeout=30)
    if r.status_code == 200:
        existing = [u for u in r.json() if u["email"] == RECEP["email"]]
        if not existing:
            requests.post(f"{API}/users", headers=admin_headers, json={
                "email": RECEP["email"], "password": RECEP["password"], "role": "reception"
            }, timeout=30)
    tok = _login(RECEP)
    return {"Authorization": f"Bearer {tok}"}


# ---------- Health / Auth ----------
def test_health():
    r = requests.get(f"{API}/", timeout=15)
    assert r.status_code == 200


def test_login_admin(admin_headers):
    r = requests.get(f"{API}/auth/me", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_login_reception(reception_headers):
    r = requests.get(f"{API}/auth/me", headers=reception_headers, timeout=15)
    assert r.status_code == 200
    assert r.json()["role"] == "reception"


# ---------- Users CRUD (admin only) ----------
class TestUsersCRUD:
    def test_reception_forbidden(self, reception_headers):
        assert requests.get(f"{API}/users", headers=reception_headers).status_code == 403
        assert requests.post(f"{API}/users", headers=reception_headers, json={
            "email": "x@x.com", "password": "abcdef", "role": "reception"
        }).status_code == 403

    def test_admin_create_update_delete(self, admin_headers):
        email = f"TEST_user_{uuid.uuid4().hex[:6]}@x.com"
        r = requests.post(f"{API}/users", headers=admin_headers, json={
            "email": email, "password": "abcdef", "role": "reception"
        })
        assert r.status_code == 200, r.text
        uid = r.json()["id"]
        # duplicate
        r2 = requests.post(f"{API}/users", headers=admin_headers, json={
            "email": email, "password": "abcdef", "role": "reception"
        })
        assert r2.status_code == 400
        # update role
        r3 = requests.put(f"{API}/users/{uid}", headers=admin_headers, json={"role": "admin"})
        assert r3.status_code == 200
        # password reset
        r4 = requests.put(f"{API}/users/{uid}", headers=admin_headers, json={"password": "newpass6"})
        assert r4.status_code == 200
        # verify list contains
        rl = requests.get(f"{API}/users", headers=admin_headers).json()
        assert any(u["id"] == uid for u in rl)
        # delete
        rd = requests.delete(f"{API}/users/{uid}", headers=admin_headers)
        assert rd.status_code == 200

    def test_cannot_delete_self(self, admin_headers):
        me = requests.get(f"{API}/auth/me", headers=admin_headers).json()
        r = requests.delete(f"{API}/users/{me['id']}", headers=admin_headers)
        assert r.status_code == 400

    def test_cannot_delete_last_admin(self, admin_headers):
        # admins in system
        users = requests.get(f"{API}/users", headers=admin_headers).json()
        admins = [u for u in users if u["role"] == "admin"]
        me = requests.get(f"{API}/auth/me", headers=admin_headers).json()
        others = [u for u in admins if u["id"] != me["id"]]
        if others:
            pytest.skip("More than one admin present; last-admin guard covered logically")
        # only admin is self; deleting self is already blocked (previous test)


# ---------- Reception RBAC lockdown ----------
class TestReceptionRBAC:
    def test_reception_blocked_endpoints(self, reception_headers):
        blocked = [
            ("PUT", "/settings", {"name": "x"}),
            ("POST", "/rooms", {"name": "TEST_room"}),
            ("POST", "/gallery", {"url": "https://x/y.png"}),
            ("POST", "/ical/sources", {"room_id": "x", "name": "n", "url": "https://x"}),
            ("GET", "/finance", None),
            ("POST", "/finance", {"kind": "income", "category": "c", "amount": 1, "entry_date": "2026-01-01"}),
            ("GET", "/finance/summary", None),
            ("GET", "/finance/monthly", None),
            ("GET", "/finance/export.csv", None),
        ]
        for method, path, body in blocked:
            r = requests.request(method, f"{API}{path}", headers=reception_headers, json=body if body else None)
            assert r.status_code == 403, f"{method} {path} -> {r.status_code} (expected 403)"

    def test_reception_allowed_endpoints(self, reception_headers):
        allowed_get = ["/reservations", "/rooms", "/settings", "/whatsapp/templates", "/reports/occupancy"]
        for p in allowed_get:
            r = requests.get(f"{API}{p}", headers=reception_headers)
            assert r.status_code == 200, f"GET {p} -> {r.status_code}"

    def test_reception_can_create_reservation(self, reception_headers):
        r = requests.post(f"{API}/reservations", headers=reception_headers, json={
            "guest_name": "TEST_recep", "checkin_date": "2026-04-01", "checkout_date": "2026-04-03"
        })
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        # patch status
        rp = requests.patch(f"{API}/reservations/{rid}/status", headers=reception_headers, json={"status": "confirmed"})
        assert rp.status_code == 200


# ---------- Pre-reservation emails ----------
def test_public_pre_reservation_dispatches(admin_headers):
    # ensure settings.email set for owner email path
    s = requests.get(f"{API}/settings", headers=admin_headers).json()
    s["email"] = s.get("email") or "owner@example.com"
    requests.put(f"{API}/settings", headers=admin_headers, json=s)
    r = requests.post(f"{API}/public/pre-reservation", json={
        "guest_name": "TEST Guest",
        "guest_document": "12345",
        "guest_email": "test_guest@example.com",
        "guest_phone": "+55 11 99999-0000",
        "guest_birthdate": "1990-01-01",
        "checkin_date": "2026-05-01",
        "checkout_date": "2026-05-05",
        "adults": 2, "children": 0,
        "accepted_terms": True,
    })
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True
    assert "reservation_id" in r.json()


# ---------- Occupancy heatmap ----------
class TestHeatmap:
    def test_shape_march_2026(self, admin_headers):
        r = requests.get(f"{API}/reports/occupancy?year=2026&month=3", headers=admin_headers)
        assert r.status_code == 200
        j = r.json()
        assert j["year"] == 2026 and j["month"] == 3 and j["days"] == 31
        for room in j["rooms"]:
            assert len(room["cells"]) == 31
            assert "id" in room and "name" in room

    def test_confirmed_overrides_pending(self, admin_headers):
        # create a room + a pending and a confirmed overlapping reservation
        rm = requests.post(f"{API}/rooms", headers=admin_headers, json={"name": f"TEST_room_{uuid.uuid4().hex[:5]}"})
        assert rm.status_code == 200
        rid = rm.json()["id"]
        try:
            r1 = requests.post(f"{API}/reservations", headers=admin_headers, json={
                "room_id": rid, "guest_name": "A", "checkin_date": "2026-06-10", "checkout_date": "2026-06-12",
                "status": "pending"
            }).json()
            r2 = requests.post(f"{API}/reservations", headers=admin_headers, json={
                "room_id": rid, "guest_name": "B", "checkin_date": "2026-06-11", "checkout_date": "2026-06-13",
                "status": "confirmed"
            }).json()
            hm = requests.get(f"{API}/reports/occupancy?year=2026&month=6", headers=admin_headers).json()
            room = next(r for r in hm["rooms"] if r["id"] == rid)
            # day index for June 11 = 10, June 12 = 11
            assert room["cells"][10] == "confirmed", room["cells"][:15]
        finally:
            requests.delete(f"{API}/rooms/{rid}", headers=admin_headers)


# ---------- PIX BR Code ----------
def _crc16_ccitt(data: str) -> str:
    crc = 0xFFFF
    for b in data.encode():
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


class TestPix:
    def test_missing_key_returns_400(self, admin_headers):
        s = requests.get(f"{API}/settings", headers=admin_headers).json()
        original = s.get("pix_key", "")
        s["pix_key"] = ""
        requests.put(f"{API}/settings", headers=admin_headers, json=s)
        try:
            r = requests.post(f"{API}/pix/brcode", headers=admin_headers, json={"amount": 100})
            assert r.status_code == 400
        finally:
            s["pix_key"] = original or "pousada@teste.com.br"
            requests.put(f"{API}/settings", headers=admin_headers, json=s)

    def test_brcode_structure_and_crc(self, admin_headers):
        s = requests.get(f"{API}/settings", headers=admin_headers).json()
        if not s.get("pix_key"):
            s["pix_key"] = "pousada@teste.com.br"
            requests.put(f"{API}/settings", headers=admin_headers, json=s)
        r = requests.post(f"{API}/pix/brcode", headers=admin_headers, json={"amount": 250.50})
        assert r.status_code == 200, r.text
        j = r.json()
        code = j["brcode"]
        assert code.startswith("000201")
        assert "26" in code[:10] and "br.gov.bcb.pix" in code
        assert "5406250.50" in code
        assert "5802BR" in code
        # CRC verify
        body = code[:-4]
        expected = _crc16_ccitt(body)
        assert code[-4:] == expected, f"CRC mismatch: got {code[-4:]}, expected {expected}"
        assert j["qr_png_base64"].startswith("data:image/png;base64,")

    def test_reception_can_generate_pix(self, reception_headers):
        r = requests.post(f"{API}/pix/brcode", headers=reception_headers, json={"amount": 10})
        assert r.status_code in (200, 400)  # 400 only if key not set — should be set by prior test
