"""Fuzzy agronomic logic.

This module implements a clean, growth-stage-free decision support approach.
It computes normalized sensor quality, a plant health score, AI confidence and
structured alert/recommendation outputs for hydroponic lettuce.
"""

import math
from typing import Any, Dict, List, Tuple


def trapezoid(x: float, a: float, b: float, c: float, d: float) -> float:
    if x < a or x > d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if a <= x < b:
        return (x - a) / (b - a) if b != a else 1.0
    return (d - x) / (d - c) if d != c else 1.0


def triangle(x: float, a: float, b: float, c: float) -> float:
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if a < x < b:
        return (x - a) / (b - a)
    return (c - x) / (c - b)


def is_valid_number(value: float | None) -> bool:
    return (
        value is not None
        and isinstance(value, (int, float))
        and not math.isnan(value)
        and not math.isinf(value)
    )


def normalized_distance(value: float | None, optimal_min: float, optimal_max: float, low_cutoff: float, high_cutoff: float) -> float:
    """Return a normalized error score in [0, 1] for a measurement."""
    if not is_valid_number(value) or value < low_cutoff or value > high_cutoff:
        return 1.0
    if optimal_min <= value <= optimal_max:
        return 0.0
    if value < optimal_min:
        return (optimal_min - value) / (optimal_min - low_cutoff)
    return (value - optimal_max) / (high_cutoff - optimal_max)


def sensor_quality(value: float | None, optimal_min: float, optimal_max: float, low_cutoff: float, high_cutoff: float) -> float:
    """Return a quality score in [0, 1] for a sensor reading."""
    if not is_valid_number(value):
        return 0.0
    return 1.0 - normalized_distance(value, optimal_min, optimal_max, low_cutoff, high_cutoff)


def get_temperature_value(row: Dict[str, Any], temp_col: str) -> float | None:
    if temp_col in row:
        return row[temp_col]
    return row.get("Temperature (%)")


def compute_fuzzy_certainty(row: Dict[str, Any], temp_col: str) -> float:
    measures = [
        sensor_quality(row.get("TDS Value (ppm)"), 520, 750, 400, 950),
        sensor_quality(row.get("pH Level"), 5.8, 6.2, 5.3, 6.7),
        sensor_quality(row.get("Humidity (%)"), 55, 70, 40, 90),
        sensor_quality(row.get("Water Temperature (°C)"), 18, 22, 14, 28),
        sensor_quality(get_temperature_value(row, temp_col), 20, 24, 15, 30),
        sensor_quality(row.get("Water Level (%)"), 35, 100, 10, 100),
    ]
    return sum(measures) / len(measures)


def sensor_status_level(value: float | None, optimal_min: float, optimal_max: float, warning_min: float, warning_max: float) -> str:
    if not is_valid_number(value):
        return "Faulty"
    if optimal_min <= value <= optimal_max:
        return "Healthy"
    if warning_min <= value <= warning_max:
        return "Warning"
    return "Faulty"


def compute_sensor_status(row: Dict[str, Any], temp_col: str) -> Dict[str, str]:
    return {
        "temperature": sensor_status_level(get_temperature_value(row, temp_col), 20, 24, 15, 30),
        "humidity": sensor_status_level(row.get("Humidity (%)"), 55, 70, 40, 90),
        "ph": sensor_status_level(row.get("pH Level"), 5.8, 6.2, 5.3, 6.7),
        "tds": sensor_status_level(row.get("TDS Value (ppm)"), 520, 750, 400, 950),
        "water_temperature": sensor_status_level(row.get("Water Temperature (°C)"), 18, 22, 14, 28),
        "water_level": sensor_status_level(row.get("Water Level (%)"), 35, 100, 10, 100),
    }


def compute_water_quality_score(row: Dict[str, Any]) -> tuple[int, str]:
    ph_quality = sensor_quality(row.get("pH Level"), 5.8, 6.2, 5.3, 6.7)
    tds_quality = sensor_quality(row.get("TDS Value (ppm)"), 520, 750, 400, 950)
    water_temp_quality = sensor_quality(row.get("Water Temperature (°C)"), 18, 22, 14, 28)
    score = round((ph_quality * 0.4 + tds_quality * 0.4 + water_temp_quality * 0.2) * 100)
    if score >= 90:
        label = "Excellent"
    elif score >= 75:
        label = "Good"
    elif score >= 55:
        label = "Average"
    else:
        label = "Poor"
    return score, label


def compute_climate_stability_score(row: Dict[str, Any], temp_col: str) -> tuple[int, str]:
    temp_quality = sensor_quality(get_temperature_value(row, temp_col), 20, 24, 15, 30)
    humidity_quality = sensor_quality(row.get("Humidity (%)"), 55, 70, 40, 90)
    score = round((temp_quality * 0.55 + humidity_quality * 0.45) * 100)
    if score >= 80:
        label = "Stable"
    elif score >= 60:
        label = "Moderately Stable"
    else:
        label = "Unstable"
    return score, label


def compute_nutrient_balance_score(row: Dict[str, Any]) -> tuple[int, str]:
    ph_quality = sensor_quality(row.get("pH Level"), 5.8, 6.2, 5.3, 6.7)
    tds_quality = sensor_quality(row.get("TDS Value (ppm)"), 520, 750, 400, 950)
    score = round((tds_quality * 0.6 + ph_quality * 0.4) * 100)
    if score >= 85:
        label = "Excellent"
    elif score >= 70:
        label = "Good"
    elif score >= 55:
        label = "Average"
    else:
        label = "Poor"
    return score, label


def compute_risk_level(health_score: int, anomaly_score: float, safety_blocking: bool) -> tuple[str, str]:
    if safety_blocking or anomaly_score < -0.03 or health_score < 35:
        return "CRITICAL", "red"
    if anomaly_score < -0.015 or health_score < 50:
        return "HIGH", "orange"
    if anomaly_score < -0.005 or health_score < 70:
        return "MEDIUM", "yellow"
    return "LOW", "green"


def compute_ai_confidence_explanation(row: Dict[str, Any], fuzzy_decision: Dict[str, Any], anomaly_score: float, sensor_status: Dict[str, str]) -> list[str]:
    reasons: list[str] = []
    if anomaly_score < -0.01:
        reasons.append("Anomaly model detected unexpected sensor behavior.")
    if abs(fuzzy_decision.get("tds_error", 0)) > 15:
        reasons.append("TDS is outside the optimal nutrient range.")
    if abs(fuzzy_decision.get("ph_error", 0)) > 0.12:
        reasons.append("pH is outside the optimal range.")
    if sensor_status.get("humidity") != "Healthy":
        reasons.append("Humidity is not within the preferred band.")
    if sensor_status.get("water_temperature") != "Healthy":
        reasons.append("Water temperature is outside the best root zone.")
    if sensor_status.get("water_level") != "Healthy":
        reasons.append("Water level is low or inconsistent.")
    if len(reasons) == 0:
        reasons.append("Sensor readings are stable and the model is consistent.")
    return reasons


def compute_plant_health_score(row: Dict[str, Any], anomaly_score: float, safety_blocking: bool, temp_col: str) -> int:
    """Compute a 0-100 plant health score for lettuce."""
    if safety_blocking:
        return 10

    opt_tds = sensor_quality(row.get("TDS Value (ppm)"), 520, 750, 400, 950)
    opt_ph = sensor_quality(row.get("pH Level"), 5.8, 6.2, 5.3, 6.7)
    opt_humidity = sensor_quality(row.get("Humidity (%)"), 55, 70, 40, 90)
    opt_water_temp = sensor_quality(row.get("Water Temperature (°C)"), 18, 22, 14, 28)
    opt_air_temp = sensor_quality(get_temperature_value(row, temp_col), 20, 24, 15, 30)
    opt_water_level = sensor_quality(row.get("Water Level (%)"), 35, 100, 10, 100)

    weighted_average = (
        opt_tds * 0.25 +
        opt_ph * 0.25 +
        opt_humidity * 0.15 +
        opt_water_temp * 0.15 +
        opt_air_temp * 0.1 +
        opt_water_level * 0.1
    )
    anomaly_penalty = min(0.35, max(0.0, -anomaly_score * 0.2))
    score = weighted_average * 100 * (1.0 - anomaly_penalty)
    return max(0, min(100, round(score)))


def health_label(score: int) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 55:
        return "Moderate"
    if score >= 35:
        return "Poor"
    return "Critical"


def estimate_harvest_remaining(dap: int | None, health_score: int) -> Tuple[int, int]:
    if dap is None or dap < 0:
        return 0, 0

    assumed_cycle = 45
    remaining = max(0, assumed_cycle - dap)
    adjustment = 0.5 + 0.5 * (health_score / 100)
    estimated_days = max(0, round(remaining * adjustment))
    confidence = min(100, max(50, round(health_score * 0.9 + 10)))
    return estimated_days, confidence


def compute_ai_confidence(anomaly_score: float, fuzzy_certainty: float) -> int:
    anomaly_confidence = max(0.0, min(1.0, 1.0 + anomaly_score))
    confidence = 0.55 * anomaly_confidence + 0.45 * fuzzy_certainty
    return int(round(max(0.0, min(1.0, confidence)) * 100))


def build_sensor_alerts(row: Dict[str, Any], safety_check: Dict[str, Any], anomaly_score: float) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []

    for item in safety_check.get("blocking_alerts", []):
        alerts.append({
            "title": "Sensor Blocking Alert",
            "message": item,
            "severity": "Critical"
        })

    for item in safety_check.get("warnings", []):
        alerts.append({
            "title": "Sensor Warning",
            "message": item,
            "severity": "Medium"
        })

    if anomaly_score < -0.03:
        alerts.append({
            "title": "Anomalie détectée",
            "message": "Le modèle statistique détecte une condition imprévue.",
            "severity": "High"
        })
    elif anomaly_score < -0.01:
        alerts.append({
            "title": "Alerte anomalie",
            "message": "Conditions légèrement inhabituelles détectées.",
            "severity": "Medium"
        })

    if not alerts:
        alerts.append({
            "title": "Conditions normales",
            "message": "Aucune alerte détectée pour les capteurs et le modèle.",
            "severity": "Low"
        })

    return alerts


def fuzzy_agronomic_decision(row: Dict[str, Any], temp_col: str) -> Dict[str, Any]:
    tds = row["TDS Value (ppm)"]
    ph = row["pH Level"]

    tds_error = 0.0
    if tds < 520:
        tds_error = tds - 520
    elif tds > 950:
        tds_error = tds - 950

    ph_error = 0.0
    if ph < 5.8:
        ph_error = ph - 5.8
    elif ph > 6.7:
        ph_error = ph - 6.7

    nutrient_action = 0.0
    if tds_error < -0.1:
        nutrient_action = 60.0
    elif tds_error < 0:
        nutrient_action = 30.0
    elif tds_error > 0.1:
        nutrient_action = -40.0

    ph_action = 0.0
    if ph_error < -0.05:
        ph_action = 40.0
    elif ph_error < 0:
        ph_action = 20.0
    elif ph_error > 0.05:
        ph_action = -40.0

    if abs(tds_error) < 15 and abs(ph_error) < 0.12:
        diagnosis = "Healthy"
    elif abs(ph_error) > abs(tds_error):
        diagnosis = "Lower pH" if ph_error > 0 else "Increase pH"
    else:
        diagnosis = "Add Nutrients" if nutrient_action > 0 else "Reduce Nutrients"

    fuzzy_certainty = compute_fuzzy_certainty(row, temp_col)

    return {
        "diagnosis": diagnosis,
        "fuzzy_certainty": round(fuzzy_certainty, 3),
        "tds_error": round(float(tds_error), 2),
        "ph_error": round(float(ph_error), 2),
        "nutrient_action": round(float(nutrient_action), 2),
        "ph_action": round(float(ph_action), 2)
    }
