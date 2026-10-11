from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime, Index
from backend.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class DailyMealRecord(Base):
    __tablename__ = "daily_meal_records"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    menu_item = Column(String(100), nullable=False, index=True)
    meal_category = Column(String(50), nullable=False, default="Lunch")
    day_of_week = Column(String(20), nullable=False)
    is_weekend = Column(Integer, default=0)
    is_holiday = Column(Integer, default=0)
    special_event = Column(String(100), default="None")
    
    meals_prepared = Column(Integer, nullable=False)
    meals_sold = Column(Integer, nullable=False)
    leftover_meals = Column(Integer, nullable=False, default=0)
    food_discarded_kg = Column(Float, nullable=False, default=0.0)
    cost_per_meal = Column(Float, nullable=False, default=50.0)
    notes = Column(String(255), nullable=True, default="")
    created_at = Column(DateTime, default=utc_now)

    __table_args__ = (
        Index("idx_date_menu", "date", "menu_item", unique=True),
    )


class DemandPredictionRecord(Base):
    __tablename__ = "demand_predictions"

    id = Column(Integer, primary_key=True, index=True)
    target_date = Column(String(10), nullable=False, index=True)
    menu_item = Column(String(100), nullable=False)
    meal_category = Column(String(50), default="Lunch")
    predicted_demand = Column(Float, nullable=False)
    model_name = Column(String(50), default="RandomForestRegressor")
    mae_estimate = Column(Float, nullable=True)
    lower_bound = Column(Float, nullable=True)
    upper_bound = Column(Float, nullable=True)
    features_summary = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now)


class PreparationPlanRecord(Base):
    __tablename__ = "preparation_plans"

    id = Column(Integer, primary_key=True, index=True)
    target_date = Column(String(10), nullable=False, index=True)
    menu_item = Column(String(100), nullable=False)
    predicted_demand = Column(Float, nullable=False)
    buffer_percent = Column(Float, nullable=False, default=10.0)
    buffer_meals = Column(Integer, nullable=False, default=0)
    recommended_prepared = Column(Integer, nullable=False)
    rationale = Column(String(500), nullable=False)
    status = Column(String(50), default="Planned")  # Planned, Completed
    actual_meals_prepared = Column(Integer, nullable=True)
    actual_meals_sold = Column(Integer, nullable=True)
    actual_food_discarded_kg = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class ModelEvaluationRecord(Base):
    __tablename__ = "model_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    trained_at = Column(DateTime, default=utc_now)
    model_name = Column(String(100), nullable=False)
    mae = Column(Float, nullable=False)
    rmse = Column(Float, nullable=False)
    r2 = Column(Float, nullable=False)
    baseline_mae = Column(Float, nullable=False)
    baseline_rmse = Column(Float, nullable=False)
    train_samples = Column(Integer, nullable=False)
    test_samples = Column(Integer, nullable=False)
    notes = Column(String(255), nullable=True)
