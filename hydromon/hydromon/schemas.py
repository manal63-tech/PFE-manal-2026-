"""Inbound payload normalisation.

Accepts the various field aliases the sensor clients may send and produces a
canonical, validated payload dict.

``growth_days`` is intentionally NOT accepted here anymore: it is now
derived from the plantation date (see ``plantation.py``) at prediction time,
instead of being sent by the client. Previously the ESP32 never sent it at
all, so every single reading silently used the same fixed default (14) -
that bug is fixed by removing the field entirely.
"""

import math


def normalize_payload(data):
    required_any = {
        "temperature": ["temperature", "temp", "airTemp"],
        "humidity": ["humidity", "hum", "airHumidity"],
        "tds": ["tds", "TDS"],
        "ph": ["ph", "pH"]
    }

    def _to_float(value, field_name):
        try:
            result = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Valeur numerique invalide pour {field_name}: {value!r}")

        if math.isnan(result) or math.isinf(result):
            raise ValueError(f"Valeur numerique invalide pour {field_name}: {value!r}")

        return result

    normalized = {}
    missing = []

    for canonical, aliases in required_any.items():
        found = next((alias for alias in aliases if alias in data), None)

        if found is None:
            missing.append(canonical)
        else:
            normalized[canonical] = _to_float(data[found], canonical)

    if missing:
        raise ValueError(f"Champs manquants: {', '.join(missing)}")

    def optional_float(aliases):
        found = next(
            (alias for alias in aliases if alias in data and data.get(alias) is not None), None
        )
        return None if found is None else _to_float(data[found], found)

    water_level = optional_float(["water_level", "waterLevel"])

    # These three were already being sent by the ESP32
    # (Synaps_hydro_pfe.ino -> taskSendFlask) but silently dropped here,
    # so they were never stored, validated, or shown on the dashboard.
    water_temperature = optional_float(
        ["water_temperature", "waterTemperature", "waterTemp"]
    )
    temperature_outside = optional_float(
        ["temperature_outside", "tempOutside", "airTempOutside"]
    )
    humidity_outside = optional_float(
        ["humidity_outside", "humOutside", "airHumidityOutside"]
    )

    # The ESP32 reports the actual relay/pump/fan state in a nested
    # "actuator_status" object; also silently dropped before.
    actuator_status = data.get("actuator_status") or {}

    return {
        "temperature": float(normalized["temperature"]),
        "humidity": float(normalized["humidity"]),
        "tds": float(normalized["tds"]),
        "ph": float(normalized["ph"]),
        "water_level": water_level,
        "water_temperature": water_temperature,
        "temperature_outside": temperature_outside,
        "humidity_outside": humidity_outside,
        "led_on": bool(actuator_status["led"]) if "led" in actuator_status else None,
        "led_mode": actuator_status.get("led_mode"),
        "pump_on": bool(actuator_status["pump"]) if "pump" in actuator_status else None,
        "fan_on": bool(actuator_status["fan"]) if "fan" in actuator_status else None,
    }
