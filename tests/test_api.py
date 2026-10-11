import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, engine, SessionLocal
from backend.models import DailyMealRecord

client = TestClient(app)

@pytest.fixture(autouse=True)
def run_around_tests():
    # Setup
    Base.metadata.create_all(bind=engine)
    yield
    # Teardown if needed

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data

def test_create_and_read_meal_record():
    payload = {
        "date": "2026-10-15",
        "menu_item": "Test Veg Thali",
        "meal_category": "Lunch",
        "meals_prepared": 150,
        "meals_sold": 140,
        "leftover_meals": 10,
        "food_discarded_kg": 2.5,
        "cost_per_meal": 50.0,
        "special_event": "None",
        "is_holiday": 0,
        "notes": "Automated unit test record"
    }

    # Delete if exists
    db = SessionLocal()
    existing = db.query(DailyMealRecord).filter(
        DailyMealRecord.date == "2026-10-15",
        DailyMealRecord.menu_item == "Test Veg Thali"
    ).first()
    if existing:
        db.delete(existing)
        db.commit()
    db.close()

    res = client.post("/api/records", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["menu_item"] == "Test Veg Thali"
    assert created["day_of_week"] == "Thursday"  # 2026-10-15 is Thursday

    rec_id = created["id"]

    # Read back
    res_get = client.get(f"/api/records/{rec_id}")
    assert res_get.status_code == 200
    assert res_get.json()["meals_prepared"] == 150

    # Clean up
    client.delete(f"/api/records/{rec_id}")

def test_validation_rejects_impossible_sales():
    # Meals sold (200) > Meals prepared (100) must be rejected
    payload = {
        "date": "2026-10-16",
        "menu_item": "Impossible Biryani",
        "meals_prepared": 100,
        "meals_sold": 200,
        "cost_per_meal": 60.0
    }
    res = client.post("/api/records", json=payload)
    assert res.status_code == 422 or res.status_code == 400

def test_csv_template_endpoint():
    res = client.get("/api/csv/template")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "date,menu_item" in res.text

def test_dashboard_summary():
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert "total_meals_prepared" in data
    assert "total_meals_sold" in data
    assert "total_discarded_kg" in data
