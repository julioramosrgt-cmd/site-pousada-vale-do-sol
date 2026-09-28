"""Iteration 5 backend tests: pricing engine, public pre-reservation with new fields,
   block period, voucher PDF, settings pricing config.
"""
import os
import uuid
import requests
import pytest

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
ADMIN = {"email": "admin@pousada.com", "password": "pousada2024"}


def _login():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def headers():
    return {"Authorization": f"Bearer {_login()}"}


@pytest.fixture(scope="module")
def test_room(headers):
    r = requests.post(f"{API}/rooms", headers=headers, json={
        "name": f"TEST_pricing_{uuid.uuid4().hex[:5]}",
        "daily_rate": 100.0,
        "max_adults": 4,
        "max_children": 4,
    })
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    yield r.json()
    requests.delete(f"{API}/rooms/{rid}", headers=headers)


@pytest.fixture(scope="module", autouse=True)
def set_pricing_defaults(headers):
    """Ensure pricing config defaults set (10/65/10/20.7/27.6/34.5) and holidays include 2026-04-10."""
    s = requests.get(f"{API}/settings", headers=headers).json()
    s.update({
        "weekend_surcharge_pct": 10.0,
        "child_rate_pct": 65.0,
        "extra_adult_discount_pct": 10.0,
        "pet_small_pct": 20.7,
        "pet_medium_pct": 27.6,
        "pet_large_pct": 34.5,
        "holidays": "2026-04-10",
    })
    r = requests.put(f"{API}/settings", headers=headers, json=s)
    assert r.status_code == 200, r.text
    return s


# ---------- Pricing calc ----------
class TestPricingCalc:
    def test_basic_weekday_single_adult(self, test_room):
        # Mon->Tue 2026-04-06 to 2026-04-07 = 1 weekday night, 1 adult, rate=100
        r = requests.post(f"{API}/pricing/calc", json={
            "room_id": test_room["id"],
            "checkin_date": "2026-04-06",
            "checkout_date": "2026-04-07",
            "adults": 1,
        })
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["n_nights"] == 1
        assert len(j["nights"]) == 1
        n = j["nights"][0]
        assert n["surcharge"] == 0.0
        assert n["nightly_rate"] == 100.0
        assert n["adults_value"] == 100.0
        assert j["total"] == 100.0

    def test_weekend_surcharge(self, test_room):
        # 2026-04-10 is Friday (weekend surcharge) AND holiday (still +10%)
        # 2026-04-11 Saturday (weekend +10%)
        # 2026-04-12 Sunday (weekday)
        r = requests.post(f"{API}/pricing/calc", json={
            "room_id": test_room["id"],
            "checkin_date": "2026-04-10",
            "checkout_date": "2026-04-13",
            "adults": 1,
        }).json()
        assert r["n_nights"] == 3
        # Fri
        assert r["nights"][0]["surcharge"] == 10.0
        assert r["nights"][0]["nightly_rate"] == 110.0
        # Sat
        assert r["nights"][1]["surcharge"] == 10.0
        # Sun (weekday, non-holiday)
        assert r["nights"][2]["surcharge"] == 0.0
        assert r["nights"][2]["nightly_rate"] == 100.0

    def test_extra_adult_discount_flat(self, test_room):
        # 2 adults, 1 weekday night, rate 100
        # first adult 100, second 100*0.9=90 => 190
        r = requests.post(f"{API}/pricing/calc", json={
            "room_id": test_room["id"],
            "checkin_date": "2026-04-06",
            "checkout_date": "2026-04-07",
            "adults": 2,
        }).json()
        assert r["nights"][0]["adults_value"] == 190.0
        assert r["total"] == 190.0

    def test_first_child_0_3_free(self, test_room):
        # 1 adult, 1 child 0-3 (free) → total 100
        r = requests.post(f"{API}/pricing/calc", json={
            "room_id": test_room["id"],
            "checkin_date": "2026-04-06",
            "checkout_date": "2026-04-07",
            "adults": 1,
            "children_0_3": 1,
        }).json()
        assert r["free_children"] == 1
        assert r["paying_children"] == 0
        assert r["total"] == 100.0

    def test_second_child_0_3_pays_65(self, test_room):
        # 1 adult, 2 children 0-3 (1 free + 1 paying at 65%) → 100 + 65 = 165
        r = requests.post(f"{API}/pricing/calc", json={
            "room_id": test_room["id"],
            "checkin_date": "2026-04-06",
            "checkout_date": "2026-04-07",
            "adults": 1,
            "children_0_3": 2,
        }).json()
        assert r["paying_children"] == 1
        assert r["total"] == 165.0

    def test_children_4_10_pay_65(self, test_room):
        r = requests.post(f"{API}/pricing/calc", json={
            "room_id": test_room["id"],
            "checkin_date": "2026-04-06",
            "checkout_date": "2026-04-07",
            "adults": 1,
            "children_4_10": 2,
        }).json()
        assert r["paying_children"] == 2
        assert r["total"] == 100.0 + 2 * 65.0  # 230

    def test_pets_percentages(self, test_room):
        # 1 small pet + 1 medium + 1 large: 20.7% + 27.6% + 34.5% = 82.8% of nightly 100 = 82.8
        r = requests.post(f"{API}/pricing/calc", json={
            "room_id": test_room["id"],
            "checkin_date": "2026-04-06",
            "checkout_date": "2026-04-07",
            "adults": 1,
            "pets_small": 1, "pets_medium": 1, "pets_large": 1,
        }).json()
        # 100 (adult) + 82.8 (pets) = 182.8
        assert round(r["nights"][0]["pets_value"], 2) == 82.8
        assert round(r["total"], 2) == 182.8


# ---------- Public pre-reservation with new fields ----------
def test_public_pre_reservation_with_new_fields(headers, test_room):
    r = requests.post(f"{API}/public/pre-reservation", json={
        "room_id": test_room["id"],
        "guest_name": "TEST_new_fields",
        "guest_document": "999",
        "guest_email": "test_new@example.com",
        "guest_phone": "+55 11 90000-0000",
        "guest_birthdate": "1990-01-01",
        "checkin_date": "2026-04-06",
        "checkout_date": "2026-04-08",
        "adults": 2,
        "children_0_3": 1,
        "children_4_10": 1,
        "pets_small": 1,
        "accepted_terms": True,
    })
    assert r.status_code == 200, r.text
    rid = r.json()["reservation_id"]
    # Verify persistence and pricing_breakdown / total_amount
    reservations = requests.get(f"{API}/reservations", headers=headers).json()
    row = next((x for x in reservations if x["id"] == rid), None)
    assert row is not None
    assert row["adults"] == 2
    assert row["children_0_3"] == 1
    assert row["children_4_10"] == 1
    assert row["pets_small"] == 1
    # legacy children auto-computed
    assert row["children"] == 2
    assert row.get("pricing_breakdown") is not None
    assert row["pricing_breakdown"]["n_nights"] == 2
    assert row["total_amount"] > 0
    # cleanup
    requests.delete(f"{API}/reservations/{rid}", headers=headers)


# ---------- Block period ----------
def test_reservation_block(headers, test_room):
    r = requests.post(f"{API}/reservations/block", headers=headers, json={
        "room_id": test_room["id"],
        "from_date": "2026-07-01",
        "to_date": "2026-07-05",
        "reason": "Manutenção",
    })
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "blocked"
    assert j["room_id"] == test_room["id"]
    rid = j["id"]
    # ensure appears on list
    lst = requests.get(f"{API}/reservations?status=blocked", headers=headers).json()
    assert any(x["id"] == rid for x in lst)
    requests.delete(f"{API}/reservations/{rid}", headers=headers)


def test_block_invalid_dates(headers, test_room):
    r = requests.post(f"{API}/reservations/block", headers=headers, json={
        "room_id": test_room["id"],
        "from_date": "2026-07-05",
        "to_date": "2026-07-01",
    })
    assert r.status_code == 400


# ---------- Voucher PDF ----------
def test_voucher_pdf(headers, test_room):
    # create reservation with pets
    rc = requests.post(f"{API}/reservations", headers=headers, json={
        "room_id": test_room["id"],
        "guest_name": "TEST_voucher Cliente",
        "guest_document": "111",
        "guest_email": "v@example.com",
        "guest_phone": "+55",
        "checkin_date": "2026-04-06",
        "checkout_date": "2026-04-08",
        "adults": 2, "children_0_3": 1, "pets_small": 1,
        "total_amount": 250.0,
    })
    assert rc.status_code == 200, rc.text
    rid = rc.json()["id"]
    try:
        r = requests.get(f"{API}/reservations/{rid}/voucher.pdf", headers=headers)
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert len(r.content) > 1024
        assert r.content[:4] == b"%PDF"
    finally:
        requests.delete(f"{API}/reservations/{rid}", headers=headers)


def test_voucher_pdf_requires_auth(test_room):
    # any reservation id → without headers should be 401
    r = requests.get(f"{API}/reservations/xxx/voucher.pdf")
    assert r.status_code == 401


# ---------- Settings pricing fields ----------
def test_settings_pricing_fields_persist(headers):
    s = requests.get(f"{API}/settings", headers=headers).json()
    original = {k: s.get(k) for k in ("weekend_surcharge_pct", "child_rate_pct", "extra_adult_discount_pct",
                                      "pet_small_pct", "pet_medium_pct", "pet_large_pct", "holidays")}
    s.update({
        "weekend_surcharge_pct": 15.0,
        "child_rate_pct": 70.0,
        "extra_adult_discount_pct": 12.0,
        "pet_small_pct": 22.0,
        "pet_medium_pct": 30.0,
        "pet_large_pct": 40.0,
        "holidays": "2026-12-25\n2026-01-01",
    })
    r = requests.put(f"{API}/settings", headers=headers, json=s)
    assert r.status_code == 200, r.text
    got = requests.get(f"{API}/settings", headers=headers).json()
    assert got["weekend_surcharge_pct"] == 15.0
    assert got["child_rate_pct"] == 70.0
    assert got["extra_adult_discount_pct"] == 12.0
    assert got["pet_small_pct"] == 22.0
    assert got["holidays"].strip().startswith("2026-12-25")
    # restore defaults
    got.update(original)
    requests.put(f"{API}/settings", headers=headers, json=got)
