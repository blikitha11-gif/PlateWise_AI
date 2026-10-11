from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator

class MealRecordBase(BaseModel):
    date: str = Field(..., description="Date formatted as YYYY-MM-DD")
    menu_item: str = Field(..., min_length=2, max_length=100)
    meal_category: str = Field(default="Lunch", max_length=50)
    day_of_week: Optional[str] = Field(default=None)
    is_weekend: Optional[int] = Field(default=0, ge=0, le=1)
    is_holiday: int = Field(default=0, ge=0, le=1)
    special_event: Optional[str] = Field(default="None")
    meals_prepared: int = Field(..., ge=0, description="Total meals cooked")
    meals_sold: int = Field(..., ge=0, description="Total meals actually sold/served")
    leftover_meals: int = Field(default=0, ge=0, description="Edible surplus meals remaining")
    food_discarded_kg: float = Field(default=0.0, ge=0.0, description="Actual physical waste in kilograms")
    cost_per_meal: float = Field(default=50.0, gt=0.0, description="Unit cost in rupees/currency")
    notes: Optional[str] = Field(default="", max_length=255)

    @model_validator(mode="before")
    @classmethod
    def validate_and_derive_fields(cls, values: dict):
        if not isinstance(values, dict):
            return values
        
        # Validate date and derive day of week
        date_str = values.get("date")
        if date_str:
            try:
                parsed_date = datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
                if "day_of_week" not in values or not values["day_of_week"]:
                    values["day_of_week"] = parsed_date.strftime("%A")
                if "is_weekend" not in values or values["is_weekend"] is None:
                    values["is_weekend"] = 1 if parsed_date.weekday() >= 5 else 0
            except ValueError:
                raise ValueError("Date must be formatted as YYYY-MM-DD")

        # Business logic validation:
        prep = values.get("meals_prepared", 0)
        sold = values.get("meals_sold", 0)
        leftover = values.get("leftover_meals", 0)

        # Basic consistency check: meals sold cannot exceed meals prepared
        if prep is not None and sold is not None:
            if sold > prep:
                raise ValueError(f"Meals sold ({sold}) cannot exceed meals prepared ({prep}) without extra preparation.")
            
            # Leftovers cannot exceed unsold portions
            unsold = prep - sold
            if leftover is not None and leftover > unsold:
                # auto-adjust or flag:
                values["leftover_meals"] = unsold

        return values


class MealRecordCreate(MealRecordBase):
    pass


class MealRecordUpdate(BaseModel):
    menu_item: Optional[str] = None
    meal_category: Optional[str] = None
    meals_prepared: Optional[int] = Field(None, ge=0)
    meals_sold: Optional[int] = Field(None, ge=0)
    leftover_meals: Optional[int] = Field(None, ge=0)
    food_discarded_kg: Optional[float] = Field(None, ge=0.0)
    cost_per_meal: Optional[float] = Field(None, gt=0.0)
    is_holiday: Optional[int] = Field(None, ge=0, le=1)
    special_event: Optional[str] = None
    notes: Optional[str] = None


class MealRecordResponse(MealRecordBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PredictRequest(BaseModel):
    target_date: str = Field(..., description="Target date YYYY-MM-DD")
    menu_item: str = Field(..., description="Menu item to predict demand for")
    meal_category: str = Field(default="Lunch")
    is_holiday: int = Field(default=0, ge=0, le=1)
    special_event: str = Field(default="None")


class PredictResponse(BaseModel):
    target_date: str
    menu_item: str
    meal_category: str
    day_of_week: str
    predicted_demand: float
    model_name: str
    mae_estimate: float
    confidence_interval: dict
    feature_insights: list[str]


class PlanRequest(BaseModel):
    target_date: str
    menu_item: str
    meal_category: str = "Lunch"
    predicted_demand: Optional[float] = None
    buffer_percent: float = Field(default=10.0, ge=0.0, le=50.0)
    stockout_penalty_weight: float = Field(default=1.2, ge=0.5, le=3.0)
    waste_penalty_weight: float = Field(default=1.0, ge=0.5, le=3.0)


class PlanResponse(BaseModel):
    target_date: str
    menu_item: str
    meal_category: str
    predicted_demand: float
    buffer_percent: float
    buffer_meals: int
    recommended_prepared: int
    rationale: str
    model_source: str
    cost_estimation: dict


class ModelEvaluationResponse(BaseModel):
    trained_at: datetime
    model_name: str
    mae: float
    rmse: float
    r2: float
    baseline_mae: float
    baseline_rmse: float
    train_samples: int
    test_samples: int
    notes: Optional[str]

    model_config = {"from_attributes": True}


class DashboardSummaryResponse(BaseModel):
    total_meals_prepared: int
    total_meals_sold: int
    total_unsold_meals: int
    total_discarded_kg: float
    total_waste_cost: float
    next_day_predicted_demand: float
    next_day_recommended_prepared: int
    next_day_target: str
    is_demo_data: bool
    record_count: int
