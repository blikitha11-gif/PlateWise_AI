import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.config import USE_AWS_AI, AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_BEDROCK_MODEL_ID
from backend.models import DailyMealRecord, PreparationPlanRecord

def get_rule_based_advisory(db: Session) -> dict:
    """
    Expert rule-based advisory engine. Analyzes stored meal records to deliver
    actionable food waste prevention and kitchen optimization guidance.
    """
    records = db.query(DailyMealRecord).all()
    if not records:
        return {
            "advisor_mode": "Local Expert Rule Engine",
            "executive_summary": "No historical meal records stored yet. Add daily records to receive custom operational guidance.",
            "action_items": [],
            "surplus_reduction_targets": [],
            "demand_spikes": [],
            "redistribution_protocol": None,
            "generated_at": datetime.utcnow().isoformat()
        }

    df = pd.DataFrame([{
        "date": r.date,
        "menu_item": r.menu_item,
        "meal_category": r.meal_category,
        "day_of_week": r.day_of_week,
        "meals_prepared": r.meals_prepared,
        "meals_sold": r.meals_sold,
        "leftover_meals": r.leftover_meals,
        "food_discarded_kg": r.food_discarded_kg,
        "cost_per_meal": r.cost_per_meal
    } for r in records])

    df["waste_cost"] = df["food_discarded_kg"] * 50.0  # conservative estimated loss per kg or meal cost
    df["surplus_rate"] = (df["meals_prepared"] - df["meals_sold"]) / df["meals_prepared"].replace(0, 1)

    # 1. Repeated surplus items
    item_stats = df.groupby("menu_item").agg(
        avg_prepared=("meals_prepared", "mean"),
        avg_sold=("meals_sold", "mean"),
        avg_leftover=("leftover_meals", "mean"),
        total_discarded_kg=("food_discarded_kg", "sum"),
        total_waste_cost=("waste_cost", "sum"),
        avg_surplus_rate=("surplus_rate", "mean")
    ).reset_index()

    repeated_surplus = item_stats[item_stats["avg_surplus_rate"] > 0.12].sort_values("avg_surplus_rate", ascending=False)
    surplus_targets = []
    for _, row in repeated_surplus.iterrows():
        trim_meals = int(np.ceil((row["avg_prepared"] - row["avg_sold"]) * 0.7))
        surplus_targets.append({
            "menu_item": row["menu_item"],
            "current_surplus_rate": f"{round(row['avg_surplus_rate'] * 100, 1)}%",
            "recommended_reduction": f"Reduce base prep by ~{trim_meals} portions per batch",
            "estimated_annual_saving_kg": round(trim_meals * 0.35 * 180, 1) # ~180 academic days
        })

    # 2. Demand spikes by weekday
    dow_stats = df.groupby(["menu_item", "day_of_week"])["meals_sold"].mean().reset_index()
    dow_overall = df.groupby("day_of_week")["meals_sold"].mean().to_dict()
    avg_all_days = df["meals_sold"].mean()
    high_days = [d for d, v in dow_overall.items() if v > avg_all_days * 1.1]
    low_days = [d for d, v in dow_overall.items() if v < avg_all_days * 0.88]

    demand_spikes = []
    if high_days:
        demand_spikes.append({
            "observation": f"Consistently elevated demand on {', '.join(high_days)}.",
            "recommendation": "Increase preparation buffer to 12-15% to avoid stockouts and student dissatisfaction."
        })
    if low_days:
        demand_spikes.append({
            "observation": f"Drop in consumption observed on {', '.join(low_days)}.",
            "recommendation": "Lower batch sizing by 15-20% to prevent end-of-day overproduction."
        })

    # 3. High discarded food hotspot
    worst_item = item_stats.sort_values("total_discarded_kg", ascending=False).iloc[0] if len(item_stats) > 0 else None

    # 4. Action items
    action_items = []
    if worst_item is not None and worst_item["total_discarded_kg"] > 5.0:
        action_items.append({
            "priority": "HIGH",
            "title": f"Review Production for '{worst_item['menu_item']}'",
            "detail": f"This item accounts for {round(worst_item['total_discarded_kg'], 1)} kg of discarded food. Consider cooking in staggered phased batches (e.g. 60% before lunch, 40% halfway) rather than a single massive morning cook."
        })

    if len(surplus_targets) > 0:
        action_items.append({
            "priority": "MEDIUM",
            "title": "Calibrate Safety Buffers on Surplus Items",
            "detail": f"Targeting {len(surplus_targets)} items with persistent >12% surplus will prevent roughly {sum([t['estimated_annual_saving_kg'] for t in surplus_targets])} kg of avoidable food waste per semester."
        })

    action_items.append({
        "priority": "BEST PRACTICE",
        "title": "Staggered Batch Cooking Protocol",
        "detail": "Transition from all-at-once cooking to progressive cook-chill or small-batch replenishments after the initial rush."
    })

    # 5. Surplus Food Redistribution Protocol
    redistribution_protocol = {
        "status": "Active Safe Protocol",
        "guidelines": [
            "Hot foods held above 60°C (140°F) or cold foods chilled below 5°C (41°F) may be safely packed within 2 hours of meal service.",
            "Pre-arrange daily dispatch with verified campus charity or local NGO food banks (e.g. Robin Hood Army / Feeding India).",
            "Log batch timestamp and quantity in WasteWise food dispatch register before handover."
        ]
    }

    executive_summary = (
        f"Analyzed {len(df)} meal logs. Total recorded waste stands at {round(df['food_discarded_kg'].sum(), 1)} kg. "
        f"{len(surplus_targets)} items exhibit recurring preparation surplus. Immediate staggered batching "
        f"can eliminate an estimated {round(len(surplus_targets) * 4.5, 1)} kg of waste weekly without risking stockouts."
    )

    return {
        "advisor_mode": "Local Expert Rule Engine",
        "executive_summary": executive_summary,
        "action_items": action_items,
        "surplus_reduction_targets": surplus_targets,
        "demand_spikes": demand_spikes,
        "redistribution_protocol": redistribution_protocol,
        "generated_at": datetime.utcnow().isoformat()
    }


def get_ai_waste_advice(db: Session) -> dict:
    """
    Main advisory entrypoint. Uses AWS Strands / Bedrock if AWS credentials are configured;
    otherwise seamlessly falls back to the local expert rule engine.
    """
    # 1. Run local analytics engine first for solid deterministic facts
    base_advice = get_rule_based_advisory(db)

    # 2. Check if AWS credentials exist
    if not USE_AWS_AI:
        return base_advice

    try:
        # Attempt AWS Strands Agent or boto3 Bedrock agent invocation
        import boto3
        bedrock_runtime = boto3.client(
            service_name="bedrock-runtime",
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )

        prompt_payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "system": "You are WasteWise AI, an expert food waste auditor and canteen sustainability consultant. Respond with concise, professional recommendations based ONLY on provided data.",
            "messages": [
                {
                    "role": "user",
                    "content": f"Review this canteen waste audit summary and provide 3 high-impact executive operational recommendations:\n{json.dumps(base_advice, indent=2)}"
                }
            ]
        }

        response = bedrock_runtime.invoke_model(
            modelId=AWS_BEDROCK_MODEL_ID,
            body=json.dumps(prompt_payload),
            contentType="application/json"
        )
        response_body = json.loads(response["body"].read())
        ai_text = response_body.get("content", [{}])[0].get("text", "")

        if ai_text:
            base_advice["advisor_mode"] = "AWS Strands Agents / Bedrock AI"
            base_advice["executive_summary"] = ai_text.strip()
            return base_advice
    except Exception as e:
        # Graceful fallback: append note that local fallback was used due to AWS API condition
        base_advice["aws_notice"] = f"AWS Agent unavailable ({str(e)[:60]}...). Active fallback to Local Expert Engine."
        return base_advice

    return base_advice
