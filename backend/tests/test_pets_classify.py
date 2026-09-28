"""Backend tests for pets classification, pricing calc with pets[], and pre-reservation with pets[]."""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback: read from frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@pousada.com"
ADMIN_PASSWORD = "pousada2024"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def test_room(auth_headers):
    """Create a room with daily_rate=145 for pricing tests. Cleanup at teardown."""
    payload = {
        "name": f"TEST_pets_{uuid.uuid4().hex[:6]}",
        "category": "Quarto",
        "max_adults": 4,
        "max_children": 4,
        "amenities": [],
        "daily_rate": 145.0,
        "min_stay": 1,
        "status": "available",
        "description": "",
    }
    r = requests.post(f"{API}/rooms", json=payload, headers=auth_headers)
    assert r.status_code == 200, r.text
    room = r.json()
    yield room
    requests.delete(f"{API}/rooms/{room['id']}", headers=auth_headers)


# --- /api/pets/classify ---
class TestClassify:
    def test_golden_retriever_large(self):
        r = requests.get(f"{API}/pets/classify", params={"breed": "Golden Retriever", "pet_type": "cão"})
        assert r.status_code == 200
        d = r.json()
        assert d["size"] == "large"
        assert d["matched"] is True

    def test_yorkshire_small(self):
        r = requests.get(f"{API}/pets/classify", params={"breed": "Yorkshire", "pet_type": "cão"})
        assert r.status_code == 200
        d = r.json()
        assert d["size"] == "small"
        assert d["matched"] is True

    def test_shih_tzu_small(self):
        r = requests.get(f"{API}/pets/classify", params={"breed": "Shih Tzu", "pet_type": "cão"})
        assert r.status_code == 200
        d = r.json()
        assert d["size"] == "small"
        assert d["matched"] is True

    def test_siames_cat_small(self):
        r = requests.get(f"{API}/pets/classify", params={"breed": "Siamês", "pet_type": "gato"})
        assert r.status_code == 200
        d = r.json()
        assert d["size"] == "small"
        assert d["matched"] is True

    def test_unknown_medium_fallback(self):
        r = requests.get(f"{API}/pets/classify", params={"breed": "Raça Inexistente XYZ"})
        assert r.status_code == 200
        d = r.json()
        assert d["size"] == "medium"
        assert d["matched"] is False
        assert d["message"] and "não reconhecida" in d["message"].lower()


# --- /api/pets/breeds ---
class TestBreedList:
    def test_breeds_returns_100_plus(self):
        r = requests.get(f"{API}/pets/breeds")
        assert r.status_code == 200
        d = r.json()
        assert "breeds" in d
        assert isinstance(d["breeds"], list)
        assert len(d["breeds"]) >= 100, f"only {len(d['breeds'])} breeds"


# --- /api/pricing/calc with pets[] ---
class TestPricingCalcPets:
    def test_pets_array_aggregation(self, test_room):
        # 2 nights, daily_rate=145
        # pets: 1 large (Golden Retriever 34.5%) + 1 small (Yorkshire 20.7%)
        # But nightly rate may have weekend surcharge — pick a Mon/Tue to be safe: 2026-03-02 (Mon), 2026-03-03 (Tue), checkout 2026-03-04
        payload = {
            "room_id": test_room["id"],
            "checkin_date": "2026-03-02",
            "checkout_date": "2026-03-04",
            "adults": 1,
            "children_0_3": 0,
            "children_4_10": 0,
            "pets": [
                {"type": "cão", "breed": "Golden Retriever"},
                {"type": "cão", "breed": "Yorkshire"},
            ],
        }
        r = requests.post(f"{API}/pricing/calc", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["n_nights"] == 2
        # nightly base with no weekend surcharge = 145
        # pets_value per night = (0.345 + 0.207) * 145 = 80.04
        for n in d["nights"]:
            assert n["surcharge"] == 0
            assert n["nightly_rate"] == 145.0
            assert abs(n["pets_value"] - 80.04) < 0.01, n
        # confirm the aggregated small/large counts appear in top-level
        assert d["pets"]["small"] == 1
        assert d["pets"]["large"] == 1
        assert d["pets"]["medium"] == 0


# --- /api/public/pre-reservation with pets[] ---
class TestPublicPreReservation:
    def test_creates_reservation_with_pets(self, auth_headers, test_room):
        payload = {
            "room_id": test_room["id"],
            "guest_name": "TEST_pets_flow",
            "guest_document": "12345678901",
            "guest_email": "test-pets@example.com",
            "guest_phone": "+5511999999999",
            "guest_birthdate": "1990-01-01",
            "checkin_date": "2026-03-02",
            "checkout_date": "2026-03-04",
            "adults": 1,
            "children_0_3": 0,
            "children_4_10": 0,
            "pets": [
                {"type": "cão", "breed": "Golden Retriever"},
                {"type": "cão", "breed": "Yorkshire"},
                {"type": "cão", "breed": "Raça Inexistente XYZ"},
            ],
            "accepted_terms": True,
        }
        r = requests.post(f"{API}/public/pre-reservation", json=payload)
        assert r.status_code == 200, r.text
        res_id = r.json()["reservation_id"]

        # Fetch back via admin
        g = requests.get(f"{API}/reservations", headers=auth_headers, params={"room_id": test_room["id"]})
        assert g.status_code == 200
        found = next((x for x in g.json() if x["id"] == res_id), None)
        assert found is not None
        assert found["pets_small"] == 1
        assert found["pets_medium"] == 1  # the unknown breed
        assert found["pets_large"] == 1
        assert len(found["pets"]) == 3
        for p in found["pets"]:
            assert p["size"] in ("small", "medium", "large")
        # total: 2 nights, 1 adult, plus pets fees
        # per night = 145 + (0.345 + 0.207 + 0.276)*145 = 145 + 0.828*145 = 145 + 120.06 = 265.06
        # 2 nights => 530.12
        assert abs(found["total_amount"] - 530.12) < 0.1, found["total_amount"]

        # cleanup
        requests.delete(f"{API}/reservations/{res_id}", headers=auth_headers)

    def test_legacy_counts_still_accepted(self, test_room):
        payload = {
            "room_id": test_room["id"],
            "checkin_date": "2026-03-02",
            "checkout_date": "2026-03-04",
            "adults": 1,
            "pets_small": 1,
            "pets_large": 1,
        }
        r = requests.post(f"{API}/pricing/calc", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["pets"]["small"] == 1
        assert d["pets"]["large"] == 1
