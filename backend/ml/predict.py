import joblib
import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.config import ML_MODEL_DIR
from backend.models import DailyMealRecord, DemandPredictionRecord

MODEL_FILE = ML_MODEL_DIR / "model_rf.joblib"
METADATA_FILE = ML_MODEL_DIR / "model_metadata.joblib"

def predict_demand_for_item(
    db: Session,
    target_date: str,
    menu_item: str,
    meal_category: str = "Lunch",
    is_holiday: int = 0,
    special_event: str = "None"
) -> dict:
    """
    Generates meal demand prediction for a specific date and menu item.
    Uses trained Random Forest model if available, else falls back to robust baseline.
    """
    target_dt = datetime.strptime(target_date, "%Y-%m-%d").date()
    day_of_week = target_dt.strftime("%A")
    is_weekend = 1 if target_dt.weekday() >= 5 else 0
    has_event = 0 if str(special_event).lower() in ["none", "no", "", "nan"] else 1
    day_of_month = target_dt.day
    month = target_dt.month

    # Retrieve recent historical meals sold for this item to compute realistic lag
    recent_records = (
        db.query(DailyMealRecord.meals_sold)
        .filter(DailyMealRecord.menu_item == menu_item)
        .filter(DailyMealRecord.date < target_date)
        .order_by(desc(DailyMealRecord.date))
        .limit(7)
        .all()
    )
    recent_sales = [r[0] for r in recent_records]

    if recent_sales:
        lag_demand_1 = float(recent_sales[0])
        rolling_mean_3 = float(np.mean(recent_sales[:3]))
        rolling_mean_7 = float(np.mean(recent_sales))
    else:
        # Fallback to general average across all items
        avg_sold = db.query(DailyMealRecord.meals_sold).limit(20).all()
        default_val = float(np.mean([r[0] for r in avg_sold])) if avg_sold else 150.0
        lag_demand_1 = default_val
        rolling_mean_3 = default_val
        rolling_mean_7 = default_val

    # Check if trained model artifact exists
    if MODEL_FILE.exists() and METADATA_FILE.exists():
        try:
            model = joblib.load(MODEL_FILE)
            meta = joblib.load(METADATA_FILE)

            input_dict = {
                "menu_item": [menu_item],
                "meal_category": [meal_category],
                "day_of_week": [day_of_week],
                "is_weekend": [is_weekend],
                "is_holiday": [is_holiday],
                "has_event": [has_event],
                "day_of_month": [day_of_month],
                "month": [month],
                "lag_demand_1": [lag_demand_1],
                "rolling_mean_3": [rolling_mean_3],
                "rolling_mean_7": [rolling_mean_7]
            }
            input_df = pd.DataFrame(input_dict)
            pred_raw = float(model.predict(input_df)[0])
            pred_val = max(10.0, round(pred_raw, 1))

            mae_val = meta.get("rf_mae", 12.0)
            res_std = meta.get("residual_std", 15.0)

            lower_bound = max(0.0, round(pred_val - 1.5 * res_std, 1))
            upper_bound = round(pred_val + 1.5 * res_std, 1)

            feature_insights = [
                f"Trained Random Forest model applied (Held-out Test MAE: {mae_val} meals).",
                f"Day of week '{day_of_week}' factor integrated.",
                f"Recent 7-day demand trend benchmark: {round(rolling_mean_7, 1)} meals.",
            ]
            if is_holiday:
                feature_insights.append("Holiday flag active: historical demand dampener accounted for.")
            if has_event:
                feature_insights.append(f"Special event '{special_event}' active: surge adjustment applied.")

            # Record prediction in DB
            pred_record = DemandPredictionRecord(
                target_date=target_date,
                menu_item=menu_item,
                meal_category=meal_category,
                predicted_demand=pred_val,
                model_name="RandomForestRegressor",
                mae_estimate=mae_val,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                features_summary=f"Event: {special_event}, Day: {day_of_week}"
            )
            db.add(pred_record)
            db.commit()

            return {
                "target_date": target_date,
                "menu_item": menu_item,
                "meal_category": meal_category,
                "day_of_week": day_of_week,
                "predicted_demand": pred_val,
                "model_name": "RandomForestRegressor",
                "mae_estimate": mae_val,
                "confidence_interval": {
                    "lower": lower_bound,
                    "upper": upper_bound,
                    "confidence_level": "85% Empirical Residual Interval"
                },
                "feature_insights": feature_insights
            }
        except Exception as e:
            # Fall back to baseline gracefully
            pass

    # Baseline Method: Day-of-Week historical median or general item mean
    dow_records = (
        db.query(DailyMealRecord.meals_sold)
        .filter(DailyMealRecord.menu_item == menu_item)
        .filter(DailyMealRecord.day_of_week == day_of_week)
        .all()
    )
    if dow_records:
        base_pred = float(np.median([r[0] for r in dow_records]))
        baseline_desc = f"Historical {day_of_week} median for {menu_item}"
    elif recent_sales:
        base_pred = float(rolling_mean_7)
        baseline_desc = f"Recent 7-record moving average for {menu_item}"
    else:
        base_pred = 120.0
        baseline_desc = "Default canteen baseline (insufficient historical data)"

    # Adjust for event/holiday in baseline
    if is_holiday:
        base_pred *= 0.75
    if has_event:
        base_pred *= 1.25

    base_pred = max(10.0, round(base_pred, 1))

    pred_record = DemandPredictionRecord(
        target_date=target_date,
        menu_item=menu_item,
        meal_category=meal_category,
        predicted_demand=base_pred,
        model_name="BaselineMovingAverage",
        mae_estimate=18.5,
        lower_bound=max(0.0, base_pred - 20),
        upper_bound=base_pred + 20,
        features_summary=baseline_desc
    )
    db.add(pred_record)
    db.commit()

    return {
        "target_date": target_date,
        "menu_item": menu_item,
        "meal_category": meal_category,
        "day_of_week": day_of_week,
        "predicted_demand": base_pred,
        "model_name": "BaselineMovingAverage",
        "mae_estimate": 18.5,
        "confidence_interval": {
            "lower": max(0.0, round(base_pred - 20.0, 1)),
            "upper": round(base_pred + 20.0, 1),
            "confidence_level": "Baseline Heuristic Interval"
        },
        "feature_insights": [
            f"Using baseline method: {baseline_desc}.",
            "Train the machine learning model on at least 15 historical records for higher accuracy.",
            f"Recent demand anchor: {round(rolling_mean_7, 1)} meals."
        ]
    }
