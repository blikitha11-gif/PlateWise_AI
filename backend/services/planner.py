import math
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models import PreparationPlanRecord, DailyMealRecord
from backend.ml.predict import predict_demand_for_item

def compute_preparation_plan(
    db: Session,
    target_date: str,
    menu_item: str,
    meal_category: str = "Lunch",
    buffer_percent: float = 10.0,
    stockout_penalty_weight: float = 1.2,
    waste_penalty_weight: float = 1.0,
    manual_predicted_demand: float = None,
    save_to_db: bool = True
) -> dict:
    """
    Computes transparent, asymmetric-loss food preparation recommendations.
    Distinguishes raw predicted demand from final preparation quantity.
    """
    # 1. Obtain demand prediction
    if manual_predicted_demand is not None and manual_predicted_demand > 0:
        pred_demand = round(float(manual_predicted_demand), 1)
        model_source = "User-Specified Manual Prediction"
        mae_est = 15.0
    else:
        pred_res = predict_demand_for_item(
            db=db,
            target_date=target_date,
            menu_item=menu_item,
            meal_category=meal_category
        )
        pred_demand = round(pred_res["predicted_demand"], 1)
        model_source = pred_res["model_name"]
        mae_est = pred_res["mae_estimate"]

    # 2. Asymmetric loss adjustment:
    # If the cost of running out of meals is weighted higher (e.g. 1.5x) vs wasting food (1.0x),
    # the buffer dynamically expands according to the cost ratio (Newsvendor critical fractile logic).
    cost_ratio = stockout_penalty_weight / max(waste_penalty_weight, 0.1)
    
    # Scale base buffer by the cost ratio
    effective_buffer_pct = buffer_percent * (cost_ratio ** 0.5)
    effective_buffer_pct = max(0.0, min(effective_buffer_pct, 35.0)) # clamp between 0% and 35%

    buffer_meals = int(math.ceil(pred_demand * (effective_buffer_pct / 100.0)))
    
    # Round recommended prepared to practical kitchen batch size (e.g. batches of 5)
    raw_prep = pred_demand + buffer_meals
    recommended_prepared = int(math.ceil(raw_prep / 5.0) * 5)
    actual_buffer = recommended_prepared - int(pred_demand)

    # 3. Transparent Rationale Generation
    rationale_points = [
        f"Base predicted demand: {int(pred_demand)} meals (Model: {model_source}).",
        f"Configured safety buffer: {buffer_percent}%.",
        f"Cost ratio adjustment: stockout penalty {stockout_penalty_weight}x vs waste penalty {waste_penalty_weight}x.",
        f"Effective safety margin: +{actual_buffer} meals ({round((actual_buffer/max(pred_demand,1))*100, 1)}%).",
        f"Kitchen batch rounding: Rounded up to nearest 5-meal portion ({recommended_prepared} portions total)."
    ]
    rationale = " | ".join(rationale_points)

    # 4. Fetch cost per meal to estimate economic impacts
    recent_item_rec = (
        db.query(DailyMealRecord.cost_per_meal)
        .filter(DailyMealRecord.menu_item == menu_item)
        .order_by(DailyMealRecord.date.desc())
        .first()
    )
    cost_per_meal = recent_item_rec[0] if recent_item_rec else 50.0

    cost_estimation = {
        "cost_per_meal": cost_per_meal,
        "raw_cost_to_prepare": round(recommended_prepared * cost_per_meal, 2),
        "maximum_surplus_cost_risk": round(actual_buffer * cost_per_meal, 2),
        "unmet_demand_prevention_value": round(actual_buffer * cost_per_meal * stockout_penalty_weight, 2)
    }

    # 5. Save to database if requested
    if save_to_db:
        # Check existing plan for same date & item
        existing_plan = (
            db.query(PreparationPlanRecord)
            .filter(PreparationPlanRecord.target_date == target_date)
            .filter(PreparationPlanRecord.menu_item == menu_item)
            .first()
        )
        if existing_plan:
            existing_plan.predicted_demand = pred_demand
            existing_plan.buffer_percent = buffer_percent
            existing_plan.buffer_meals = actual_buffer
            existing_plan.recommended_prepared = recommended_prepared
            existing_plan.rationale = rationale
            db.commit()
        else:
            plan_rec = PreparationPlanRecord(
                target_date=target_date,
                menu_item=menu_item,
                predicted_demand=pred_demand,
                buffer_percent=buffer_percent,
                buffer_meals=actual_buffer,
                recommended_prepared=recommended_prepared,
                rationale=rationale,
                status="Planned"
            )
            db.add(plan_rec)
            db.commit()

    return {
        "target_date": target_date,
        "menu_item": menu_item,
        "meal_category": meal_category,
        "predicted_demand": pred_demand,
        "buffer_percent": round(effective_buffer_pct, 1),
        "buffer_meals": actual_buffer,
        "recommended_prepared": recommended_prepared,
        "rationale": rationale,
        "model_source": model_source,
        "cost_estimation": cost_estimation
    }
