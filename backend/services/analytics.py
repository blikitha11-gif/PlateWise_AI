import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime

from backend.models import DailyMealRecord, DemandPredictionRecord, PreparationPlanRecord

def get_dashboard_kpis(db: Session) -> dict:
    """
    Computes real summary KPIs from stored database records.
    """
    records = db.query(DailyMealRecord).all()
    if not records:
        return {
            "total_meals_prepared": 0,
            "total_meals_sold": 0,
            "total_unsold_meals": 0,
            "total_discarded_kg": 0.0,
            "total_waste_cost": 0.0,
            "next_day_predicted_demand": 0.0,
            "next_day_recommended_prepared": 0,
            "next_day_target": "N/A",
            "is_demo_data": False,
            "record_count": 0
        }

    total_prep = sum(r.meals_prepared for r in records)
    total_sold = sum(r.meals_sold for r in records)
    total_unsold = max(0, total_prep - total_sold)
    total_discarded_kg = round(sum(r.food_discarded_kg for r in records), 1)
    
    # Financial waste cost calculation:
    # Based on measured discarded kg (approx 0.35kg per meal equivalent) * meal cost,
    # or unsold meals that had to be thrown out
    total_waste_cost = round(sum(r.food_discarded_kg * (r.cost_per_meal / 0.4) for r in records), 2)

    # Next day prediction
    latest_rec = db.query(DailyMealRecord).order_by(desc(DailyMealRecord.date)).first()
    latest_date = latest_rec.date if latest_rec else datetime.utcnow().strftime("%Y-%m-%d")
    
    next_dt = datetime.strptime(latest_date, "%Y-%m-%d").date()
    # next day:
    from datetime import timedelta
    next_day_str = (next_dt + timedelta(days=1)).strftime("%Y-%m-%d")

    latest_plan = (
        db.query(PreparationPlanRecord)
        .order_by(desc(PreparationPlanRecord.target_date))
        .first()
    )

    return {
        "total_meals_prepared": total_prep,
        "total_meals_sold": total_sold,
        "total_unsold_meals": total_unsold,
        "total_discarded_kg": total_discarded_kg,
        "total_waste_cost": total_waste_cost,
        "next_day_predicted_demand": latest_plan.predicted_demand if latest_plan else round(float(total_sold / max(len(records), 1)), 1),
        "next_day_recommended_prepared": latest_plan.recommended_prepared if latest_plan else int(np.ceil((total_sold / max(len(records), 1)) * 1.1)),
        "next_day_target": latest_plan.target_date if latest_plan else next_day_str,
        "is_demo_data": any("sample" in (r.notes or "").lower() for r in records[:5]),
        "record_count": len(records)
    }


def get_waste_trends(db: Session) -> dict:
    """
    Returns aggregated chronological time-series of meals prepared, sold, and discarded kg.
    """
    records = db.query(DailyMealRecord).order_by(DailyMealRecord.date.asc()).all()
    if not records:
        return {"dates": [], "prepared": [], "sold": [], "discarded_kg": [], "unsold": []}

    df = pd.DataFrame([{
        "date": r.date,
        "meals_prepared": r.meals_prepared,
        "meals_sold": r.meals_sold,
        "food_discarded_kg": r.food_discarded_kg
    } for r in records])

    daily_agg = df.groupby("date").agg(
        prepared=("meals_prepared", "sum"),
        sold=("meals_sold", "sum"),
        discarded_kg=("food_discarded_kg", "sum")
    ).reset_index()

    daily_agg["unsold"] = daily_agg["prepared"] - daily_agg["sold"]

    return {
        "dates": daily_agg["date"].tolist(),
        "prepared": daily_agg["prepared"].tolist(),
        "sold": daily_agg["sold"].tolist(),
        "discarded_kg": [round(x, 2) for x in daily_agg["discarded_kg"].tolist()],
        "unsold": daily_agg["unsold"].tolist()
    }


def get_menu_item_waste_breakdown(db: Session) -> list[dict]:
    """
    Returns food waste statistics aggregated by menu item.
    """
    records = db.query(DailyMealRecord).all()
    if not records:
        return []

    df = pd.DataFrame([{
        "menu_item": r.menu_item,
        "meal_category": r.meal_category,
        "meals_prepared": r.meals_prepared,
        "meals_sold": r.meals_sold,
        "leftover_meals": r.leftover_meals,
        "food_discarded_kg": r.food_discarded_kg,
        "cost_per_meal": r.cost_per_meal
    } for r in records])

    df["unsold_meals"] = df["meals_prepared"] - df["meals_sold"]
    df["estimated_waste_cost"] = df["food_discarded_kg"] * (df["cost_per_meal"] / 0.4)

    item_agg = df.groupby(["menu_item", "meal_category"]).agg(
        total_prepared=("meals_prepared", "sum"),
        total_sold=("meals_sold", "sum"),
        total_unsold=("unsold_meals", "sum"),
        total_discarded_kg=("food_discarded_kg", "sum"),
        total_waste_cost=("estimated_waste_cost", "sum"),
        avg_cost_per_meal=("cost_per_meal", "mean"),
        count=("meals_prepared", "count")
    ).reset_index()

    item_agg["waste_rate_pct"] = (item_agg["total_unsold"] / item_agg["total_prepared"].replace(0, 1) * 100).round(1)
    item_agg["total_discarded_kg"] = item_agg["total_discarded_kg"].round(1)
    item_agg["total_waste_cost"] = item_agg["total_waste_cost"].round(2)

    return item_agg.sort_values("total_discarded_kg", ascending=False).to_dict(orient="records")


def get_impact_comparison(db: Session) -> dict:
    """
    Calculates before vs after adoption impact.
    Splits chronological records into:
    - Phase 1: Historical baseline (standard over-preparation habits)
    - Phase 2: WasteWise AI Optimization period (after implementing recommendations)
    Provides honest, separately labelled metrics (observed vs estimated avoided waste).
    """
    records = db.query(DailyMealRecord).order_by(DailyMealRecord.date.asc()).all()
    if len(records) < 10:
        return {
            "has_data": False,
            "message": "Minimum 10 records required for longitudinal before/after comparison."
        }

    df = pd.DataFrame([{
        "date": r.date,
        "menu_item": r.menu_item,
        "meals_prepared": r.meals_prepared,
        "meals_sold": r.meals_sold,
        "food_discarded_kg": r.food_discarded_kg,
        "cost_per_meal": r.cost_per_meal
    } for r in records])

    df["unsold"] = df["meals_prepared"] - df["meals_sold"]
    df["surplus_rate"] = df["unsold"] / df["meals_prepared"].replace(0, 1)

    unique_dates = sorted(df["date"].unique())
    half_point = len(unique_dates) // 2
    cutoff_date = unique_dates[half_point]

    baseline_period = df[df["date"] < cutoff_date]
    optimized_period = df[df["date"] >= cutoff_date]

    b_prep = int(baseline_period["meals_prepared"].sum())
    b_sold = int(baseline_period["meals_sold"].sum())
    b_unsold = int(baseline_period["unsold"].sum())
    b_discarded_kg = round(float(baseline_period["food_discarded_kg"].sum()), 1)
    b_surplus_rate = round(float(baseline_period["surplus_rate"].mean()) * 100, 1)

    o_prep = int(optimized_period["meals_prepared"].sum())
    o_sold = int(optimized_period["meals_sold"].sum())
    o_unsold = int(optimized_period["unsold"].sum())
    o_discarded_kg = round(float(optimized_period["food_discarded_kg"].sum()), 1)
    o_surplus_rate = round(float(optimized_period["surplus_rate"].mean()) * 100, 1)

    # Normalized comparison per 1,000 meals served
    b_waste_per_1000 = round((b_discarded_kg / max(b_sold, 1)) * 1000, 1)
    o_waste_per_1000 = round((o_discarded_kg / max(o_sold, 1)) * 1000, 1)
    reduction_pct = round(((b_waste_per_1000 - o_waste_per_1000) / max(b_waste_per_1000, 0.01)) * 100, 1)

    # Counterfactual Avoided Waste Estimate:
    # If the second period had operated at baseline period's waste rate per meal:
    counterfactual_waste_kg = round((b_discarded_kg / max(b_sold, 1)) * o_sold, 1)
    avoided_waste_kg = max(0.0, round(counterfactual_waste_kg - o_discarded_kg, 1))
    avg_cost = float(df["cost_per_meal"].mean())
    estimated_money_saved = round((avoided_waste_kg / 0.4) * avg_cost, 2)

    return {
        "has_data": True,
        "cutoff_date": cutoff_date,
        "baseline_period": {
            "name": f"Initial Baseline Phase (Prior to {cutoff_date})",
            "days_recorded": len(baseline_period["date"].unique()),
            "meals_prepared": b_prep,
            "meals_sold": b_sold,
            "unsold_meals": b_unsold,
            "discarded_kg_measured": b_discarded_kg,
            "avg_surplus_rate_pct": b_surplus_rate,
            "waste_per_1000_meals_kg": b_waste_per_1000
        },
        "optimized_period": {
            "name": f"WasteWise AI Phase (From {cutoff_date} onward)",
            "days_recorded": len(optimized_period["date"].unique()),
            "meals_prepared": o_prep,
            "meals_sold": o_sold,
            "unsold_meals": o_unsold,
            "discarded_kg_measured": o_discarded_kg,
            "avg_surplus_rate_pct": o_surplus_rate,
            "waste_per_1000_meals_kg": o_waste_per_1000
        },
        "impact_metrics": {
            "relative_reduction_pct": reduction_pct,
            "estimated_avoided_waste_kg": avoided_waste_kg,
            "estimated_cost_saved": estimated_money_saved,
            "disclaimer": "Avoided waste is an estimate calculated by comparing the baseline waste-per-meal rate against actual measured outcomes during the optimization period."
        }
    }
