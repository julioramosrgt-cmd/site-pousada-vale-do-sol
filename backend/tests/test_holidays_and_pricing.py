"""Iteration 7 tests — Brazilian national holidays in pricing engine + regression on pets breeds."""
import os
import requests
import pytest

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://gestao-acomodacoes.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def any_room_id():
    """Fetch an existing public room to run pricing calc against."""
    r = requests.get(f"{API}/public/rooms", timeout=30)
    assert r.status_code == 200, r.text
    rooms = r.json()
    assert isinstance(rooms, list) and len(rooms) > 0, "No public rooms available"
    return rooms[0]["id"]


# ---------- GET /api/public/holidays ----------
class TestHolidaysEndpoint:
    def test_default_returns_current_and_next(self):
        r = requests.get(f"{API}/public/holidays", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "holidays" in data
        h = data["holidays"]
        # Portuguese names present, and both 2026 + 2027 keys should appear (current year is 2026)
        years = {k[:4] for k in h.keys()}
        assert len(years) >= 2, f"Expected >=2 years, got {years}"

    def test_year_2025_contains_expected_names(self):
        r = requests.get(f"{API}/public/holidays?year=2025", timeout=15)
        assert r.status_code == 200
        h = r.json()["holidays"]
        # Fixed
        assert h.get("2025-04-21") == "Tiradentes"
        assert h.get("2025-12-25") == "Natal"
        assert h.get("2025-11-20") == "Consciência Negra"
        # Movable (Easter 2025 = 2025-04-20)
        assert h.get("2025-06-19") == "Corpus Christi"
        assert h.get("2025-03-03") == "Carnaval (Segunda-feira)"
        assert h.get("2025-03-04") == "Carnaval (Terça-feira)"
        assert h.get("2025-04-18") == "Sexta-feira Santa"


# ---------- Pricing surcharge on holidays ----------
class TestPricingHolidaySurcharge:
    def test_tiradentes_2025_04_21_has_surcharge(self, any_room_id):
        payload = {
            "room_id": any_room_id,
            "checkin_date": "2025-04-20",
            "checkout_date": "2025-04-22",
            "adults": 2,
            "children_0_3": 0,
            "children_4_10": 0,
            "pets_small": 0,
            "pets_medium": 0,
            "pets_large": 0,
        }
        r = requests.post(f"{API}/pricing/calc", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        nights = data.get("nights") or data.get("breakdown") or []
        assert len(nights) == 2
        # First night is Sunday 2025-04-20 (not Fri/Sat, not holiday) -> surcharge 0
        n1 = next(n for n in nights if n["date"] == "2025-04-20")
        assert n1["surcharge"] == 0, n1
        assert n1["is_holiday"] is False
        assert n1["is_national_holiday"] is False
        # Second night 2025-04-21 = Tiradentes
        n2 = next(n for n in nights if n["date"] == "2025-04-21")
        assert n2["is_holiday"] is True
        assert n2["is_national_holiday"] is True
        assert n2["holiday_name"] == "Tiradentes"
        assert n2["surcharge"] == 10.0
        # nightly_rate = base * 1.10  (base = n1.nightly_rate since n1 has 0 surcharge)
        expected = round(n1["nightly_rate"] * 1.10, 2)
        assert abs(n2["nightly_rate"] - expected) < 0.02, (n2["nightly_rate"], expected)

    def test_corpus_christi_2025_06_19(self, any_room_id):
        payload = {
            "room_id": any_room_id,
            "checkin_date": "2025-06-19",
            "checkout_date": "2025-06-20",
            "adults": 2,
            "children_0_3": 0, "children_4_10": 0,
            "pets_small": 0, "pets_medium": 0, "pets_large": 0,
        }
        r = requests.post(f"{API}/pricing/calc", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        nights = r.json().get("nights") or []
        assert len(nights) == 1
        n = nights[0]
        assert n["date"] == "2025-06-19"
        assert n["surcharge"] == 10.0
        assert n["is_national_holiday"] is True
        assert n["holiday_name"] == "Corpus Christi"

    def test_regression_normal_monday(self, any_room_id):
        payload = {
            "room_id": any_room_id,
            "checkin_date": "2025-03-10",
            "checkout_date": "2025-03-11",
            "adults": 2,
            "children_0_3": 0, "children_4_10": 0,
            "pets_small": 0, "pets_medium": 0, "pets_large": 0,
        }
        r = requests.post(f"{API}/pricing/calc", json=payload, timeout=30)
        assert r.status_code == 200
        n = r.json()["nights"][0]
        assert n["date"] == "2025-03-10"
        assert n["surcharge"] == 0
        assert n["is_holiday"] is False
        assert n["is_national_holiday"] is False
        assert n["holiday_name"] in (None, "")


# ---------- Regression pets breeds ----------
class TestPetsBreedRegression:
    def test_breeds_over_100(self):
        r = requests.get(f"{API}/pets/breeds", timeout=15)
        assert r.status_code == 200
        data = r.json()
        breeds = data.get("breeds", data if isinstance(data, list) else [])
        assert len(breeds) > 100, f"Expected >100 breeds, got {len(breeds)}"

    def test_classify_golden_retriever(self):
        r = requests.get(f"{API}/pets/classify", params={"breed": "golden retriever"}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get("size") == "large"
        assert d.get("matched") is True
