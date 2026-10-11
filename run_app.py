"""
Single-command launcher for WasteWise AI.
Initializes SQLite, seeds demo data if empty, trains ML model, and starts FastAPI.
"""
import uvicorn
from backend.database import Base, engine, SessionLocal
from backend.models import DailyMealRecord
from scripts.generate_sample_data import generate_and_seed_data
from backend.ml.train import train_model

def setup_and_run():
    print("=" * 65)
    print(" WasteWise AI — Predict Food Waste Before It Happens")
    print(" Hackathon Track: Waste & Energy | WeMakeDevs 2026")
    print("=" * 65)

    # 1. Initialize SQLite Database Tables
    print("\n[1/3] Initializing SQLite database schema...")
    Base.metadata.create_all(bind=engine)

    # 2. Seed data if database is empty
    db = SessionLocal()
    count = db.query(DailyMealRecord).count()
    if count == 0:
        print("[2/3] Empty database detected. Seeding 120 days of realistic synthetic records...")
        inserted = generate_and_seed_data(db, num_days=120)
        print(f"      Seeded {inserted} records. Training initial Random Forest model...")
        ml_res = train_model(db)
        print(f"      Model trained successfully (MAE: {ml_res.get('mae')} meals, Baseline MAE: {ml_res.get('baseline_mae')} meals).")
    else:
        print(f"[2/3] Database contains {count} meal records.")
        # Train model if not yet trained
        from backend.ml.evaluate import get_latest_evaluation
        eval_info = get_latest_evaluation(db)
        if not eval_info.get("has_trained_model"):
            print("      Training Random Forest model on existing records...")
            train_model(db)
    db.close()

    # 3. Start Uvicorn Server
    print("\n[3/3] Starting WasteWise AI Web Application...")
    print("      ➜ Web Dashboard:       http://127.0.0.1:8000")
    print("      ➜ API Documentation:   http://127.0.0.1:8000/docs")
    print("=" * 65)
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    setup_and_run()
