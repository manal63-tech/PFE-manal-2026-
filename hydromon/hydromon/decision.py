"""Hybrid decision engine.

Combines the fuzzy agronomic diagnosis, the physical safety checks and the
isolation-forest anomaly detector into a single decision dict.
"""
from datetime import datetime

import pandas as pd

from .fuzzy import (
    fuzzy_agronomic_decision,
    compute_plant_health_score,
    estimate_harvest_remaining,
    compute_ai_confidence,
    build_sensor_alerts,
    health_label,
    compute_sensor_status,
    compute_water_quality_score,
    compute_climate_stability_score,
    compute_nutrient_balance_score,
    compute_risk_level,
    compute_ai_confidence_explanation,
)
from .ml import get_bundle
from .safety import (
    anomaly_severity,
    build_user_response,
    collect_recommendations,
    physical_safety_check,
)


def final_hybrid_decision(row):
    bundle = get_bundle()
    temp_col = bundle.temp_col
    features = bundle.features
    scaler = bundle.scaler
    iso_model = bundle.iso_model

    fuzzy_decision = fuzzy_agronomic_decision(row, temp_col)
    safety_check = physical_safety_check(row, temp_col)
    recommendations = collect_recommendations(fuzzy_decision, safety_check)
    sensor_status = compute_sensor_status(row, temp_col)
    water_quality_score, water_quality_label = compute_water_quality_score(row)
    climate_stability_score, climate_stability_label = compute_climate_stability_score(row, temp_col)
    nutrient_balance_score, nutrient_balance_label = compute_nutrient_balance_score(row)

    if safety_check["blocking"]:
        health_score = compute_plant_health_score(row, anomaly_score=0.0, safety_blocking=True, temp_col=temp_col)
        harvest_days, harvest_confidence = estimate_harvest_remaining(row["Growth Days"], health_score)
        risk_level, risk_color = compute_risk_level(health_score, anomaly_score=0.0, safety_blocking=True)
        ai_explanation = compute_ai_confidence_explanation(row, fuzzy_decision, 0.0, sensor_status)
        recommendation_priority = "HIGH" if any(rec["level"] == "warning" for rec in recommendations) else "NORMAL"

        user_message, user_action = build_user_response("Sensor Alert")

        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "final_decision": "Sensor Alert",
            "actuator_command": "NO_ACTION",
            "user_message": user_message,
            "user_action": user_action,
            "recommendations": recommendations,
            "sensor_alerts": build_sensor_alerts(row, safety_check, anomaly_score=0.0),
            "climate_warnings": safety_check["warnings"],
            "blocking_alerts": safety_check["blocking_alerts"],
            "all_alerts": safety_check["all_alerts"],
            "anomaly": "Physical Safety Alert",
            "anomaly_score": None,
            "severity": "Critical",
            "plant_health_score": health_score,
            "plant_health_label": health_label(health_score),
            "estimated_harvest_remaining": harvest_days,
            "estimated_harvest_confidence": harvest_confidence,
            "ai_confidence": 0,
            "fuzzy_diagnosis": fuzzy_decision["diagnosis"],
            "sensor_status": sensor_status,
            "water_quality_score": water_quality_score,
            "water_quality_label": water_quality_label,
            "climate_stability_score": climate_stability_score,
            "climate_stability_label": climate_stability_label,
            "nutrient_balance_score": nutrient_balance_score,
            "nutrient_balance_label": nutrient_balance_label,
            "risk_level": risk_level,
            "risk_color": risk_color,
            "recommendation_priority": recommendation_priority,
            "ai_confidence_reasons": ai_explanation,
            **fuzzy_decision
        }

    input_data = pd.DataFrame([{
        temp_col: row[temp_col],
        "Humidity (%)": row["Humidity (%)"],
        "TDS Value (ppm)": row["TDS Value (ppm)"],
        "pH Level": row["pH Level"],
        "Growth Days": row["Growth Days"]
    }])

    input_data = input_data[features]
    input_scaled = scaler.transform(input_data)

    anomaly_prediction = iso_model.predict(input_scaled)[0]
    anomaly_score = iso_model.decision_function(input_scaled)[0]
    severity = anomaly_severity(anomaly_score)

    if anomaly_prediction == -1:
        final_decision = "Safety Alert"
        actuator_command = "NO_ACTION"
    else:
        final_decision = fuzzy_decision["diagnosis"]

        if final_decision == "Healthy":
            actuator_command = "NO_ACTION"
        elif final_decision == "Add Nutrients":
            actuator_command = "MANUAL_ADD_NUTRIENTS"
        elif final_decision == "Reduce Nutrients":
            actuator_command = "MANUAL_DILUTION_REQUIRED"
        elif final_decision == "Lower pH":
            actuator_command = "MANUAL_LOWER_PH"
        elif final_decision == "Increase pH":
            actuator_command = "MANUAL_INCREASE_PH"
        else:
            actuator_command = "NO_ACTION"

    health_score = compute_plant_health_score(row, anomaly_score, safety_check["blocking"], temp_col=temp_col)
    harvest_days, harvest_confidence = estimate_harvest_remaining(row["Growth Days"], health_score)
    ai_confidence = compute_ai_confidence(anomaly_score, fuzzy_decision.get("fuzzy_certainty", 0.0))
    risk_level, risk_color = compute_risk_level(health_score, anomaly_score, safety_check["blocking"])
    ai_explanation = compute_ai_confidence_explanation(row, fuzzy_decision, anomaly_score, sensor_status)
    recommendation_priority = "HIGH" if any(rec["level"] == "warning" for rec in recommendations) else "NORMAL"

    user_message, user_action = build_user_response(final_decision)

    if safety_check["warnings"]:
        user_message = user_message + " Alerte climatique."

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "final_decision": final_decision,
        "actuator_command": actuator_command,
        "user_message": user_message,
        "user_action": user_action,
        "recommendations": recommendations,
        "sensor_alerts": build_sensor_alerts(row, safety_check, anomaly_score),
        "climate_warnings": safety_check["warnings"],
        "blocking_alerts": safety_check["blocking_alerts"],
        "all_alerts": safety_check["all_alerts"],
        "anomaly": "Anomaly" if anomaly_prediction == -1 else "Normal",
        "anomaly_score": round(float(anomaly_score), 4),
        "severity": severity,
        "plant_health_score": health_score,
        "plant_health_label": health_label(health_score),
        "estimated_harvest_remaining": harvest_days,
        "estimated_harvest_confidence": harvest_confidence,
        "ai_confidence": ai_confidence,
        "fuzzy_diagnosis": fuzzy_decision["diagnosis"],
        "sensor_status": sensor_status,
        "water_quality_score": water_quality_score,
        "water_quality_label": water_quality_label,
        "climate_stability_score": climate_stability_score,
        "climate_stability_label": climate_stability_label,
        "nutrient_balance_score": nutrient_balance_score,
        "nutrient_balance_label": nutrient_balance_label,
        "risk_level": risk_level,
        "risk_color": risk_color,
        "recommendation_priority": recommendation_priority,
        "ai_confidence_reasons": ai_explanation,
        **fuzzy_decision
    }
