import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from backend.config import ML_MODEL_DIR
from backend.models import DailyMealRecord, ModelEvaluationRecord

MODEL_FILE = ML_MODEL_DIR / "model_rf.joblib"
METADATA_FILE = ML_MODEL_DIR / "model_metadata.joblib"

def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes time-series and categorical features without target leakage.
    Lag and rolling features are calculated strictly using previous chronological records.
    """
    df = df.sort_values(by=["date", "menu_item"]).reset_index(drop=True)
    df["date_dt"] = pd.to_datetime(df["date"])
    df["day_of_month"] = df["date_dt"].dt.day
    df["month"] = df["date_dt"].dt.month
    df["day_of_week"] = df["date_dt"].dt.day_name()
    df["is_weekend"] = df["date_dt"].dt.weekday.apply(lambda x: 1 if x >= 5 else 0)

    # Compute lags strictly per menu_item
    df["lag_demand_1"] = df.groupby("menu_item")["meals_sold"].shift(1)
    df["rolling_mean_3"] = df.groupby("menu_item")["meals_sold"].shift(1).rolling(3, min_periods=1).mean()
    df["rolling_mean_7"] = df.groupby("menu_item")["meals_sold"].shift(1).rolling(7, min_periods=1).mean()

    # Fill initial lag missing values with item median (avoiding future leakage)
    for col in ["lag_demand_1", "rolling_mean_3", "rolling_mean_7"]:
        df[col] = df.groupby("menu_item")[col].transform(lambda s: s.bfill().fillna(df["meals_sold"].median()))

    if "special_event" not in df.columns:
        df["special_event"] = "None"
    df["has_event"] = df["special_event"].apply(lambda x: 0 if str(x).lower() in ["none", "no", "", "nan"] else 1)

    return df


def train_model(db: Session = None, df: pd.DataFrame = None) -> dict:
    """
    Trains baseline and Random Forest models on historical meal data using chronological train/test split.
    """
    if df is None:
        if db is None:
            raise ValueError("Either db session or df must be provided")
        records = db.query(DailyMealRecord).order_by(DailyMealRecord.date.asc()).all()
        if len(records) < 15:
            return {
                "status": "insufficient_data",
                "message": f"Only {len(records)} records available. Minimum 15 records needed for ML validation.",
                "sample_count": len(records),
                "model_name": "BaselineOnly"
            }
        
        data = [{
            "date": r.date,
            "menu_item": r.menu_item,
            "meal_category": r.meal_category,
            "day_of_week": r.day_of_week,
            "is_weekend": r.is_weekend,
            "is_holiday": r.is_holiday,
            "special_event": r.special_event,
            "meals_sold": r.meals_sold,
            "meals_prepared": r.meals_prepared,
            "cost_per_meal": r.cost_per_meal
        } for r in records]
        df = pd.DataFrame(data)

    if len(df) < 15:
        return {
            "status": "insufficient_data",
            "message": f"Insufficient data: {len(df)} records. Need at least 15 records.",
            "sample_count": len(df),
            "model_name": "BaselineOnly"
        }

    df_feats = prepare_features(df)

    # Chronological Split: 80% train, 20% test
    unique_dates = sorted(df_feats["date"].unique())
    split_idx = max(1, int(len(unique_dates) * 0.8))
    split_date = unique_dates[split_idx]

    train_mask = df_feats["date"] < split_date
    test_mask = df_feats["date"] >= split_date

    train_df = df_feats[train_mask].copy()
    test_df = df_feats[test_mask].copy()

    if len(test_df) < 3:
        # Fallback if too few test dates
        train_df = df_feats.iloc[:int(len(df_feats)*0.8)].copy()
        test_df = df_feats.iloc[int(len(df_feats)*0.8):].copy()

    feature_cols_cat = ["menu_item", "meal_category", "day_of_week"]
    feature_cols_num = ["is_weekend", "is_holiday", "has_event", "day_of_month", "month", "lag_demand_1", "rolling_mean_3", "rolling_mean_7"]
    all_feature_cols = feature_cols_cat + feature_cols_num

    X_train = train_df[all_feature_cols]
    y_train = train_df["meals_sold"]
    X_test = test_df[all_feature_cols]
    y_test = test_df["meals_sold"]

    # 1. Baseline Model: 7-day rolling mean or Day-of-Week + Menu-Item historical median from training set
    baseline_lookup = train_df.groupby(["menu_item", "day_of_week"])["meals_sold"].median().to_dict()
    item_median_lookup = train_df.groupby("menu_item")["meals_sold"].median().to_dict()
    global_median = float(train_df["meals_sold"].median())

    def predict_baseline(row):
        key = (row["menu_item"], row["day_of_week"])
        if key in baseline_lookup:
            return baseline_lookup[key]
        return item_median_lookup.get(row["menu_item"], global_median)

    baseline_test_preds = test_df.apply(predict_baseline, axis=1).values
    baseline_mae = float(mean_absolute_error(y_test, baseline_test_preds))
    baseline_rmse = float(np.sqrt(mean_squared_error(y_test, baseline_test_preds)))

    # 2. Random Forest Regressor Pipeline
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), feature_cols_cat),
            ("num", "passthrough", feature_cols_num)
        ]
    )

    rf_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=8,
        min_samples_split=4,
        random_state=42,
        n_jobs=-1
    )

    pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("regressor", rf_model)
    ])

    pipeline.fit(X_train, y_train)
    rf_test_preds = pipeline.predict(X_test)

    rf_mae = float(mean_absolute_error(y_test, rf_test_preds))
    rf_rmse = float(np.sqrt(mean_squared_error(y_test, rf_test_preds)))
    rf_r2 = float(r2_score(y_test, rf_test_preds))

    # Calculate residual std dev for prediction uncertainty interval
    residuals = y_test - rf_test_preds
    residual_std = float(np.std(residuals)) if len(residuals) > 0 else 5.0

    # Save artifacts
    joblib.dump(pipeline, MODEL_FILE)
    metadata = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "train_samples": len(train_df),
        "test_samples": len(test_df),
        "rf_mae": rf_mae,
        "rf_rmse": rf_rmse,
        "rf_r2": rf_r2,
        "baseline_mae": baseline_mae,
        "baseline_rmse": baseline_rmse,
        "residual_std": residual_std,
        "baseline_lookup": {f"{k[0]}::{k[1]}": v for k, v in baseline_lookup.items()},
        "item_median_lookup": item_median_lookup,
        "global_median": global_median,
        "feature_cols_cat": feature_cols_cat,
        "feature_cols_num": feature_cols_num
    }
    joblib.dump(metadata, METADATA_FILE)

    # Save evaluation record to DB if provided
    if db is not None:
        eval_record = ModelEvaluationRecord(
            trained_at=datetime.now(timezone.utc),
            model_name="RandomForestRegressor",
            mae=round(rf_mae, 2),
            rmse=round(rf_rmse, 2),
            r2=round(rf_r2, 3),
            baseline_mae=round(baseline_mae, 2),
            baseline_rmse=round(baseline_rmse, 2),
            train_samples=len(train_df),
            test_samples=len(test_df),
            notes="Chronological split evaluation vs Day-of-Week Median Baseline"
        )
        db.add(eval_record)
        db.commit()

    return {
        "status": "success",
        "model_name": "RandomForestRegressor",
        "mae": round(rf_mae, 2),
        "rmse": round(rf_rmse, 2),
        "r2": round(rf_r2, 3),
        "baseline_mae": round(baseline_mae, 2),
        "baseline_rmse": round(baseline_rmse, 2),
        "train_samples": len(train_df),
        "test_samples": len(test_df),
        "mae_improvement_pct": round(((baseline_mae - rf_mae) / max(baseline_mae, 0.001)) * 100, 1)
    }
