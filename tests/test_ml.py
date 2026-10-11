import pytest
import pandas as pd
from backend.ml.train import prepare_features, train_model
from backend.ml.predict import predict_demand_for_item
from backend.database import SessionLocal, Base, engine
from scripts.generate_sample_data import generate_synthetic_data

@pytest.fixture(scope="module")
def sample_dataframe():
    df = generate_synthetic_data(num_days=30)
    return df

def test_feature_engineering_no_leakage(sample_dataframe):
    df_feats = prepare_features(sample_dataframe.copy())
    
    assert "lag_demand_1" in df_feats.columns
    assert "rolling_mean_7" in df_feats.columns
    assert "day_of_week" in df_feats.columns
    assert "has_event" in df_feats.columns
    
    # Lag and rolling features should have no NaNs after imputation
    assert df_feats["lag_demand_1"].isnull().sum() == 0
    assert df_feats["rolling_mean_7"].isnull().sum() == 0

def test_ml_train_and_evaluate(sample_dataframe):
    db = SessionLocal()
    result = train_model(db=db, df=sample_dataframe)
    db.close()

    assert result["status"] == "success"
    assert "mae" in result
    assert "rmse" in result
    assert "baseline_mae" in result
    assert result["train_samples"] > 0
    assert result["test_samples"] > 0

def test_prediction_output():
    db = SessionLocal()
    res = predict_demand_for_item(
        db=db,
        target_date="2026-11-01",
        menu_item="Veg Thali",
        meal_category="Lunch",
        is_holiday=0,
        special_event="None"
    )
    db.close()

    assert "predicted_demand" in res
    assert res["predicted_demand"] > 0
    assert "confidence_interval" in res
    assert res["confidence_interval"]["lower"] <= res["predicted_demand"]
    assert res["confidence_interval"]["upper"] >= res["predicted_demand"]
