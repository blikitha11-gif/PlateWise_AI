import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.config import DATA_DIR
from backend.models import DailyMealRecord

SAMPLE_CSV_PATH = DATA_DIR / "sample_meals.csv"

MENU_ITEMS = [
    {"name": "Veg Thali", "category": "Lunch", "base_demand": 180, "cost": 50.0},
    {"name": "Chicken Biryani", "category": "Lunch", "base_demand": 240, "cost": 90.0},
    {"name": "Dal Makhani & Rice", "category": "Dinner", "base_demand": 150, "cost": 45.0},
    {"name": "Paneer Roll & Salad", "category": "Dinner", "base_demand": 120, "cost": 65.0},
    {"name": "Pasta Alfredo & Bread", "category": "Dinner", "base_demand": 100, "cost": 75.0},
]

SPECIAL_EVENTS = [
    {"name": "Tech Symposium", "demand_multiplier": 1.35},
    {"name": "Annual Sports Meet", "demand_multiplier": 1.40},
    {"name": "Midterm Exams", "demand_multiplier": 0.85},
    {"name": "Semester Finals", "demand_multiplier": 0.75},
    {"name": "Cultural Fest", "demand_multiplier": 1.50},
    {"name": "Monsoon Heavy Rain", "demand_multiplier": 0.70},
]

def generate_synthetic_data(num_days: int = 120) -> pd.DataFrame:
    """
    Generates realistic synthetic canteen meal activity over multiple months.
    Labelled explicitly as synthetic demonstration data for hackathon review.
    """
    random.seed(42)
    np.random.seed(42)

    start_date = datetime(2026, 6, 1)
    rows = []

    # Map out calendar events
    event_calendar = {}
    for offset in range(num_days):
        cur_date = start_date + timedelta(days=offset)
        date_str = cur_date.strftime("%Y-%m-%d")
        # Every ~18 days assign a special event
        if offset in [14, 15, 35, 36, 52, 70, 71, 95, 110]:
            event_calendar[date_str] = random.choice(SPECIAL_EVENTS)

    for offset in range(num_days):
        cur_date = start_date + timedelta(days=offset)
        date_str = cur_date.strftime("%Y-%m-%d")
        day_of_week = cur_date.strftime("%A")
        is_weekend = 1 if cur_date.weekday() >= 5 else 0
        
        # Indian college holidays: ~2 per month or Sundays
        is_holiday = 1 if cur_date.weekday() == 6 or offset in [15, 45, 75, 105] else 0

        event_info = event_calendar.get(date_str, {"name": "None", "demand_multiplier": 1.0})
        event_name = event_info["name"]
        event_mult = event_info["demand_multiplier"]

        for item in MENU_ITEMS:
            base = item["base_demand"]
            cost = item["cost"]

            # Weekday factors
            dow_factor = 1.0
            if day_of_week == "Friday" and "Biryani" in item["name"]:
                dow_factor = 1.30  # Biryani Friday surge
            elif day_of_week in ["Saturday", "Sunday"]:
                dow_factor = 0.65  # lower campus presence on weekends
            elif day_of_week in ["Monday", "Tuesday"]:
                dow_factor = 1.10  # high early-week attendance

            if is_holiday:
                dow_factor *= 0.55

            # Random variance
            noise = np.random.normal(1.0, 0.08)
            actual_demand = int(max(20, round(base * dow_factor * event_mult * noise)))
            meals_sold = actual_demand

            # In the first 70 days (baseline phase), the canteen kitchen over-prepared heavily (20-30% buffer)
            # In the later 50 days (optimized phase), kitchen tuned production closer to actual demand (8-12% buffer)
            if offset < 70:
                prep_buffer = np.random.uniform(1.18, 1.30)
                note = "Pre-optimization baseline: Fixed kitchen estimation"
            else:
                prep_buffer = np.random.uniform(1.06, 1.12)
                note = "WasteWise AI guided preparation: Calibrated safety buffer"

            meals_prepared = int(np.ceil(meals_sold * prep_buffer / 5.0) * 5)
            unsold = meals_prepared - meals_sold

            # Leftovers: fraction saved for staff meal or cooling, remainder discarded
            leftover_meals = int(unsold * np.random.uniform(0.3, 0.5))
            discarded_meals = unsold - leftover_meals
            food_discarded_kg = round(max(0.0, discarded_meals * np.random.uniform(0.30, 0.38)), 1)

            rows.append({
                "date": date_str,
                "menu_item": item["name"],
                "meal_category": item["category"],
                "day_of_week": day_of_week,
                "is_weekend": is_weekend,
                "is_holiday": is_holiday,
                "special_event": event_name,
                "meals_prepared": meals_prepared,
                "meals_sold": meals_sold,
                "leftover_meals": leftover_meals,
                "food_discarded_kg": food_discarded_kg,
                "cost_per_meal": cost,
                "notes": f"[Synthetic Sample] {note}"
            })

    df = pd.DataFrame(rows)
    return df


def generate_and_seed_data(db: Session, num_days: int = 120) -> int:
    """
    Generates synthetic dataset, saves to CSV, and seeds SQLite database.
    """
    df = generate_synthetic_data(num_days=num_days)
    df.to_csv(SAMPLE_CSV_PATH, index=False)

    # Insert into database
    count = 0
    for _, row in df.iterrows():
        existing = (
            db.query(DailyMealRecord)
            .filter(DailyMealRecord.date == row["date"])
            .filter(DailyMealRecord.menu_item == row["menu_item"])
            .first()
        )
        if not existing:
            rec = DailyMealRecord(
                date=row["date"],
                menu_item=row["menu_item"],
                meal_category=row["meal_category"],
                day_of_week=row["day_of_week"],
                is_weekend=int(row["is_weekend"]),
                is_holiday=int(row["is_holiday"]),
                special_event=row["special_event"],
                meals_prepared=int(row["meals_prepared"]),
                meals_sold=int(row["meals_sold"]),
                leftover_meals=int(row["leftover_meals"]),
                food_discarded_kg=float(row["food_discarded_kg"]),
                cost_per_meal=float(row["cost_per_meal"]),
                notes=row["notes"]
            )
            db.add(rec)
            count += 1

    db.commit()
    return count

if __name__ == "__main__":
    from backend.database import SessionLocal, Base, engine
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    inserted = generate_and_seed_data(db)
    print(f"Generated sample dataset and seeded {inserted} records into database.")
    db.close()
