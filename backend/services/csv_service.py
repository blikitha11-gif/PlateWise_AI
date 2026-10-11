import io
import csv
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models import DailyMealRecord
from backend.schemas import MealRecordBase

EXPECTED_HEADERS = [
    "date", "menu_item", "meal_category", "meals_prepared", "meals_sold",
    "leftover_meals", "food_discarded_kg", "cost_per_meal", "is_holiday", "special_event", "notes"
]

def generate_csv_template() -> str:
    """
    Generates a sample CSV template with instructions and reference rows.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(EXPECTED_HEADERS)
    writer.writerow([
        "2026-10-10", "Veg Thali", "Lunch", "200", "185", "10", "4.5", "50.0", "0", "None", "Regular Saturday lunch"
    ])
    writer.writerow([
        "2026-10-10", "Chicken Biryani", "Lunch", "250", "240", "5", "3.0", "90.0", "0", "None", "High demand weekend special"
    ])
    writer.writerow([
        "2026-10-11", "Paneer Rice Combo", "Lunch", "180", "150", "20", "8.2", "60.0", "1", "Diwali Holiday", "Lower attendance expected"
    ])
    return output.getvalue()


def import_csv_records(db: Session, file_content: str) -> dict:
    """
    Parses and validates CSV records, prevents duplicates, reports row-level errors.
    """
    reader = csv.DictReader(io.StringIO(file_content))
    if not reader.fieldnames:
        return {"success": False, "error": "Uploaded CSV file is empty or corrupted.", "imported_count": 0, "skipped_count": 0}

    # Normalize header names
    fieldnames = [f.strip().lower() for f in reader.fieldnames]
    required = ["date", "menu_item", "meals_prepared", "meals_sold"]
    missing = [req for req in required if req not in fieldnames]
    if missing:
        return {
            "success": False,
            "error": f"Missing required columns in CSV header: {', '.join(missing)}. Download sample template for expected format.",
            "imported_count": 0,
            "skipped_count": 0
        }

    imported_count = 0
    skipped_count = 0
    errors = []

    for row_idx, row in enumerate(reader, start=2):
        row_clean = {k.strip().lower(): v.strip() for k, v in row.items() if k}
        try:
            # 1. Date check
            date_str = row_clean.get("date", "")
            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                day_name = parsed_date.strftime("%A")
                is_weekend = 1 if parsed_date.weekday() >= 5 else 0
            except ValueError:
                errors.append(f"Row {row_idx}: Invalid date format '{date_str}'. Expected YYYY-MM-DD.")
                skipped_count += 1
                continue

            menu_item = row_clean.get("menu_item", "")
            if not menu_item:
                errors.append(f"Row {row_idx}: Menu item cannot be blank.")
                skipped_count += 1
                continue

            # 2. Number parsing
            try:
                prepared = int(row_clean.get("meals_prepared", 0))
                sold = int(row_clean.get("meals_sold", 0))
                leftover = int(row_clean.get("leftover_meals", 0)) if row_clean.get("leftover_meals") else 0
                discarded_kg = float(row_clean.get("food_discarded_kg", 0.0)) if row_clean.get("food_discarded_kg") else 0.0
                cost = float(row_clean.get("cost_per_meal", 50.0)) if row_clean.get("cost_per_meal") else 50.0
                is_holiday = int(row_clean.get("is_holiday", 0)) if row_clean.get("is_holiday") else 0
            except ValueError as ve:
                errors.append(f"Row {row_idx}: Number conversion error: {str(ve)}")
                skipped_count += 1
                continue

            if prepared < 0 or sold < 0 or leftover < 0 or discarded_kg < 0 or cost <= 0:
                errors.append(f"Row {row_idx}: Negative quantities or invalid cost are not permitted.")
                skipped_count += 1
                continue

            if sold > prepared:
                errors.append(f"Row {row_idx}: Meals sold ({sold}) exceeds meals prepared ({prepared}).")
                skipped_count += 1
                continue

            # 3. Duplicate check
            existing = (
                db.query(DailyMealRecord)
                .filter(DailyMealRecord.date == date_str)
                .filter(DailyMealRecord.menu_item == menu_item)
                .first()
            )
            if existing:
                errors.append(f"Row {row_idx}: Record for '{menu_item}' on {date_str} already exists. Skipped to prevent duplicates.")
                skipped_count += 1
                continue

            # 4. Insert
            category = row_clean.get("meal_category", "Lunch") or "Lunch"
            event = row_clean.get("special_event", "None") or "None"
            notes = row_clean.get("notes", "") or ""

            record = DailyMealRecord(
                date=date_str,
                menu_item=menu_item,
                meal_category=category,
                day_of_week=day_name,
                is_weekend=is_weekend,
                is_holiday=is_holiday,
                special_event=event,
                meals_prepared=prepared,
                meals_sold=sold,
                leftover_meals=leftover,
                food_discarded_kg=discarded_kg,
                cost_per_meal=cost,
                notes=notes
            )
            db.add(record)
            imported_count += 1

        except Exception as e:
            errors.append(f"Row {row_idx}: Unexpected error: {str(e)}")
            skipped_count += 1

    if imported_count > 0:
        db.commit()

    return {
        "success": imported_count > 0 or len(errors) == 0,
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "errors": errors[:25] # return first 25 error messages
    }


def export_records_to_csv(db: Session) -> str:
    """
    Exports all daily meal records to a clean CSV formatted string.
    """
    records = db.query(DailyMealRecord).order_by(DailyMealRecord.date.asc(), DailyMealRecord.menu_item.asc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "date", "menu_item", "meal_category", "day_of_week", "is_weekend",
        "is_holiday", "special_event", "meals_prepared", "meals_sold",
        "leftover_meals", "food_discarded_kg", "cost_per_meal", "notes", "created_at"
    ])
    for r in records:
        writer.writerow([
            r.id, r.date, r.menu_item, r.meal_category, r.day_of_week, r.is_weekend,
            r.is_holiday, r.special_event, r.meals_prepared, r.meals_sold,
            r.leftover_meals, r.food_discarded_kg, r.cost_per_meal, r.notes,
            r.created_at.isoformat() if r.created_at else ""
        ])
    return output.getvalue()
