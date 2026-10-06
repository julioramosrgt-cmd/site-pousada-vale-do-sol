"""Tests for iteration 8: Stripe payment links, cron reminders, visibility fields."""
import os
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://gestao-acomodacoes.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

# Load cron secret from backend/.env
WEBHOOK_CRON_SECRET = None
with open("/app/backend/.env") as f:
    for line in f:
        if line.startswith("WEBHOOK_CRON_SECRET="):
            WEBHOOK_CRON_SECRET = line.split("=", 1)[1].strip()
            break


def _admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@pousada.com", "password": "pousada2024"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth_headers():
    return {"Authorization": f"Bearer {_admin_token()}"}


def _get_room_id():
    r = requests.get(f"{API}/public/rooms", timeout=15)
    assert r.status_code == 200, r.text
    rooms = r.json()
    assert len(rooms) > 0
    return rooms[0]["id"]


def _create_reservation(checkin_offset=3, total=500.0, status="confirmed"):
    today = datetime.now(timezone.utc).date()
    ci = (today + timedelta(days=checkin_offset)).isoformat()
    co = (today + timedelta(days=checkin_offset + 2)).isoformat()
    payload = {
        "room_id": _get_room_id(),
        "guest_name": "TEST_QA Hospede",
        "guest_phone": "5513999999999",
        "guest_email": "qa@test.com",
        "checkin_date": ci,
        "checkout_date": co,
        "adults": 2,
        "total_amount": total,
        "status": status,
    }
    r = requests.post(f"{API}/reservations", json=payload, headers=_auth_headers(), timeout=20)
    assert r.status_code in (200, 201), r.text
    return r.json()


# -------- Payment link ----------
def test_payment_link_unauthenticated():
    r = requests.post(f"{API}/reservations/some-id/payment-link", json={}, timeout=15)
    assert r.status_code == 401, r.status_code


def test_payment_link_admin_creates_url():
    res = _create_reservation(total=500.0)
    rid = res["id"]
    r = requests.post(f"{API}/reservations/{rid}/payment-link", json={}, headers=_auth_headers(), timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["url"].startswith("https://checkout.stripe.com/"), d["url"]
    assert d["session_id"]
    assert d["amount"] == 500.0

    # Verify persisted
    g = requests.get(f"{API}/reservations", headers=_auth_headers(), timeout=15)
    assert g.status_code == 200
    found = next((x for x in g.json() if x["id"] == rid), None)
    assert found is not None
    assert found.get("stripe_session_id") == d["session_id"]
    assert found.get("stripe_payment_url") == d["url"]
    assert found.get("stripe_payment_status") == "pending"
    assert float(found.get("stripe_amount") or 0) == 500.0


def test_payment_link_zero_amount_400():
    res = _create_reservation(total=0.0)
    rid = res["id"]
    r = requests.post(f"{API}/reservations/{rid}/payment-link", json={}, headers=_auth_headers(), timeout=20)
    assert r.status_code == 400, r.text


# -------- Stripe webhook (invalid signature) ---------
def test_stripe_webhook_bad_sig():
    r = requests.post(f"{API}/stripe/webhook", data=b"{}", timeout=15)
    assert r.status_code == 400, r.status_code


# -------- Cron reminder --------
def test_cron_without_auth():
    r = requests.post(f"{API}/cron/checkin-reminder", timeout=15)
    assert r.status_code == 401


def test_cron_with_secret_accepted():
    assert WEBHOOK_CRON_SECRET, "WEBHOOK_CRON_SECRET missing"
    r = requests.post(
        f"{API}/cron/checkin-reminder",
        headers={"Authorization": f"Bearer {WEBHOOK_CRON_SECRET}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "accepted"


def test_admin_manual_cron_run_and_sent_count():
    # Create reservation with checkin = today+3
    res = _create_reservation(checkin_offset=3, total=400.0, status="confirmed")
    r = requests.post(f"{API}/admin/cron/checkin-reminder/run", headers=_auth_headers(), timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "ok"
    expected = (datetime.now(timezone.utc) + timedelta(days=3)).date().isoformat()
    assert d["scanned_date"] == expected
    assert isinstance(d["sent"], int)
    assert d["sent"] >= 1


# -------- Regressions --------
def test_regression_holidays():
    r = requests.get(f"{API}/public/holidays?year=2025", timeout=15)
    assert r.status_code == 200
    data = r.json()
    holidays = data.get("holidays") if isinstance(data, dict) else data
    names = list(holidays.values()) if isinstance(holidays, dict) else [h.get("name", "") for h in holidays]
    assert any("Tiradentes" in n for n in names), names


def test_regression_pricing_calc():
    today = datetime.now(timezone.utc).date()
    payload = {
        "room_id": _get_room_id(),
        "checkin_date": (today + timedelta(days=10)).isoformat(),
        "checkout_date": (today + timedelta(days=12)).isoformat(),
        "adults": 2,
    }
    r = requests.post(f"{API}/pricing/calc", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "total" in d or "total_amount" in d or "nights" in d


def test_regression_reservation_has_source_and_created_at():
    res = _create_reservation(checkin_offset=20, total=300.0)
    rid = res["id"]
    g = requests.get(f"{API}/reservations", headers=_auth_headers(), timeout=15)
    assert g.status_code == 200
    found = next((x for x in g.json() if x["id"] == rid), None)
    assert found is not None
    assert "source" in found
    assert "created_at" in found and found["created_at"]


# -------- crons.yml --------
def test_crons_yml_parses():
    import yaml
    with open("/app/.emergent/crons.yml") as f:
        data = yaml.safe_load(f)
    crons = data["crons"]
    assert len(crons) == 1
    c = crons[0]
    assert c["name"] == "checkin-reminder"
    assert c["cron"] == "0 12 * * *"
    assert c["timezone"] == "America/Sao_Paulo"
    assert "/api/cron/checkin-reminder" in c["endpoint"]
