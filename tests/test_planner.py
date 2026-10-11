import pytest
from backend.services.planner import compute_preparation_plan
from backend.database import SessionLocal

def test_planner_recommendation_logic():
    db = SessionLocal()
    
    # Test with manual predicted demand of 100, buffer 10%
    plan = compute_preparation_plan(
        db=db,
        target_date="2026-11-05",
        menu_item="Veg Thali",
        manual_predicted_demand=100.0,
        buffer_percent=10.0,
        stockout_penalty_weight=1.0,
        waste_penalty_weight=1.0,
        save_to_db=False
    )
    db.close()

    assert plan["predicted_demand"] == 100.0
    # 100 + 10% = 110 (which is already a multiple of 5)
    assert plan["recommended_prepared"] >= 110
    assert plan["recommended_prepared"] % 5 == 0
    assert "rationale" in plan
    assert "cost_estimation" in plan

def test_planner_asymmetric_buffer_expansion():
    db = SessionLocal()
    
    # Higher stockout penalty should result in a higher buffer
    plan_balanced = compute_preparation_plan(
        db=db,
        target_date="2026-11-05",
        menu_item="Veg Thali",
        manual_predicted_demand=200.0,
        buffer_percent=10.0,
        stockout_penalty_weight=1.0,
        waste_penalty_weight=1.0,
        save_to_db=False
    )

    plan_high_stockout = compute_preparation_plan(
        db=db,
        target_date="2026-11-05",
        menu_item="Veg Thali",
        manual_predicted_demand=200.0,
        buffer_percent=10.0,
        stockout_penalty_weight=2.0,
        waste_penalty_weight=1.0,
        save_to_db=False
    )
    db.close()

    assert plan_high_stockout["buffer_meals"] >= plan_balanced["buffer_meals"]
