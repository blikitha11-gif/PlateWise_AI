import os
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.config import BASE_DIR, USE_AWS_AI
from backend.database import engine, Base, get_db
from backend.models import DailyMealRecord, DemandPredictionRecord, PreparationPlanRecord, ModelEvaluationRecord
from backend.schemas import (
    MealRecordCreate, MealRecordUpdate, MealRecordResponse,
    PredictRequest, PredictResponse,
    PlanRequest, PlanResponse,
    DashboardSummaryResponse, ModelEvaluationResponse
)
from backend.ml.train import train_model
from backend.ml.predict import predict_demand_for_item
from backend.ml.evaluate import get_latest_evaluation, get_actual_vs_predicted
from backend.services.planner import compute_preparation_plan
from backend.services.advisor import get_ai_waste_advice
from backend.services.analytics import (
    get_dashboard_kpis, get_waste_trends, get_menu_item_waste_breakdown, get_impact_comparison
)
from backend.services.csv_service import generate_csv_template, import_csv_records, export_records_to_csv

# Initialize SQLite tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="WasteWise AI — Predict Food Waste Before It Happens",
    description="Smart Canteen & Hostel Food Demand Forecasting and Waste Prevention System. WeMakeDevs Environmental Hacks 2026.",
    version="1.0.0"
)

# CORS middleware for open local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "WasteWise AI Backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "aws_ai_active": USE_AWS_AI
    }


# -------------------------------------------------------------
# DASHBOARD & ANALYTICS
# -------------------------------------------------------------
@app.get("/api/dashboard/summary", response_model=DashboardSummaryResponse)
def get_summary(db: Session = Depends(get_db)):
    return get_dashboard_kpis(db)


@app.get("/api/analytics/trends")
def get_trends(db: Session = Depends(get_db)):
    return get_waste_trends(db)


@app.get("/api/analytics/menu-items")
def get_menu_breakdown(db: Session = Depends(get_db)):
    return get_menu_item_waste_breakdown(db)


@app.get("/api/analytics/impact")
def get_impact(db: Session = Depends(get_db)):
    return get_impact_comparison(db)


# -------------------------------------------------------------
# DAILY MEAL RECORDS CRUD
# -------------------------------------------------------------
@app.get("/api/records")
def list_records(
    db: Session = Depends(get_db),
    menu_item: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500)
):
    query = db.query(DailyMealRecord)
    if menu_item and menu_item.strip():
        query = query.filter(DailyMealRecord.menu_item.ilike(f"%{menu_item.strip()}%"))
    if date_from:
        query = query.filter(DailyMealRecord.date >= date_from)
    if date_to:
        query = query.filter(DailyMealRecord.date <= date_to)

    total_count = query.count()
    records = query.order_by(desc(DailyMealRecord.date), DailyMealRecord.menu_item.asc()).offset(skip).limit(limit).all()

    return {
        "total": total_count,
        "skip": skip,
        "limit": limit,
        "records": [MealRecordResponse.model_validate(r) for r in records]
    }


@app.post("/api/records", response_model=MealRecordResponse, status_code=status.HTTP_201_CREATED)
def create_record(record_in: MealRecordCreate, db: Session = Depends(get_db)):
    # Check for existing record for date + menu_item
    existing = (
        db.query(DailyMealRecord)
        .filter(DailyMealRecord.date == record_in.date)
        .filter(DailyMealRecord.menu_item == record_in.menu_item)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A record for '{record_in.menu_item}' on date {record_in.date} already exists. Use edit to update."
        )

    db_rec = DailyMealRecord(**record_in.model_dump())
    db.add(db_rec)
    db.commit()
    db.refresh(db_rec)
    return db_rec


@app.get("/api/records/{record_id}", response_model=MealRecordResponse)
def get_record(record_id: int, db: Session = Depends(get_db)):
    rec = db.query(DailyMealRecord).filter(DailyMealRecord.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    return rec


@app.put("/api/records/{record_id}", response_model=MealRecordResponse)
def update_record(record_id: int, update_data: MealRecordUpdate, db: Session = Depends(get_db)):
    rec = db.query(DailyMealRecord).filter(DailyMealRecord.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")

    payload = update_data.model_dump(exclude_unset=True)
    for field, val in payload.items():
        setattr(rec, field, val)

    # Re-validate relationship between prep and sold if updated
    if rec.meals_sold > rec.meals_prepared:
        raise HTTPException(status_code=400, detail="Meals sold cannot exceed meals prepared.")

    db.commit()
    db.refresh(rec)
    return rec


@app.delete("/api/records/{record_id}")
def delete_record(record_id: int, db: Session = Depends(get_db)):
    rec = db.query(DailyMealRecord).filter(DailyMealRecord.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    db.delete(rec)
    db.commit()
    return {"message": "Record successfully deleted", "id": record_id}


# -------------------------------------------------------------
# MACHINE LEARNING
# -------------------------------------------------------------
@app.post("/api/ml/train")
def trigger_training(db: Session = Depends(get_db)):
    result = train_model(db=db)
    return result


@app.get("/api/ml/evaluation")
def get_evaluation(db: Session = Depends(get_db)):
    return get_latest_evaluation(db)


@app.post("/api/ml/predict", response_model=PredictResponse)
def predict_demand(req: PredictRequest, db: Session = Depends(get_db)):
    try:
        return predict_demand_for_item(
            db=db,
            target_date=req.target_date,
            menu_item=req.menu_item,
            meal_category=req.meal_category,
            is_holiday=req.is_holiday,
            special_event=req.special_event
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.get("/api/ml/actual-vs-predicted")
def list_actual_vs_predicted(db: Session = Depends(get_db), limit: int = 30):
    return get_actual_vs_predicted(db, limit=limit)


# -------------------------------------------------------------
# SMART PREPARATION PLANNER
# -------------------------------------------------------------
@app.post("/api/planner/recommend", response_model=PlanResponse)
def get_recommendation(plan_req: PlanRequest, db: Session = Depends(get_db)):
    return compute_preparation_plan(
        db=db,
        target_date=plan_req.target_date,
        menu_item=plan_req.menu_item,
        meal_category=plan_req.meal_category,
        buffer_percent=plan_req.buffer_percent,
        stockout_penalty_weight=plan_req.stockout_penalty_weight,
        waste_penalty_weight=plan_req.waste_penalty_weight,
        manual_predicted_demand=plan_req.predicted_demand,
        save_to_db=True
    )


@app.get("/api/planner/history")
def get_recent_plans(db: Session = Depends(get_db), limit: int = 20):
    plans = db.query(PreparationPlanRecord).order_by(desc(PreparationPlanRecord.target_date)).limit(limit).all()
    return [{
        "id": p.id,
        "target_date": p.target_date,
        "menu_item": p.menu_item,
        "predicted_demand": p.predicted_demand,
        "buffer_percent": p.buffer_percent,
        "buffer_meals": p.buffer_meals,
        "recommended_prepared": p.recommended_prepared,
        "rationale": p.rationale,
        "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else ""
    } for p in plans]


# -------------------------------------------------------------
# AI FOOD-WASTE ADVISOR
# -------------------------------------------------------------
@app.get("/api/advisor/insights")
def get_advisory_insights(db: Session = Depends(get_db)):
    return get_ai_waste_advice(db)


# -------------------------------------------------------------
# CSV IMPORT / EXPORT & TEMPLATE
# -------------------------------------------------------------
@app.get("/api/csv/template")
def download_csv_template():
    content = generate_csv_template()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=wastewise_meal_template.csv"}
    )


@app.post("/api/csv/upload")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files (.csv) are supported.")
    
    # 5MB size limit check
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds maximum 5MB limit.")

    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        text = contents.decode("latin-1")

    res = import_csv_records(db=db, file_content=text)
    return res


@app.get("/api/csv/export")
def export_csv(db: Session = Depends(get_db)):
    csv_data = export_records_to_csv(db)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=wastewise_export_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"}
    )


# -------------------------------------------------------------
# SAMPLE DATA SEEDING (FOR HACKATHON DEMO)
# -------------------------------------------------------------
@app.post("/api/seed-sample-data")
def seed_sample_data(db: Session = Depends(get_db)):
    from scripts.generate_sample_data import generate_and_seed_data
    count = generate_and_seed_data(db)
    # also trigger ML training on the new seed data
    ml_res = train_model(db)
    return {
        "status": "success",
        "records_inserted": count,
        "ml_training": ml_res,
        "message": f"Successfully loaded {count} realistic synthetic meal records and trained initial model."
    }


@app.post("/api/clear-data")
def clear_all_data(db: Session = Depends(get_db)):
    db.query(DailyMealRecord).delete()
    db.query(DemandPredictionRecord).delete()
    db.query(PreparationPlanRecord).delete()
    db.query(ModelEvaluationRecord).delete()
    db.commit()
    return {"status": "success", "message": "All data cleared. Database is reset to empty state."}


# -------------------------------------------------------------
# STATIC FRONTEND SERVING
# -------------------------------------------------------------
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(frontend_dir / "index.html")
