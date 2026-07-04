"""Application service layer.

Bridges inbound payloads, the decision engine and the database. Heavy imports
(pandas / decision engine) are deferred to call time so the package can be
imported by lightweight tooling.
"""
import json
import threading
from datetime import date, datetime
from pathlib import Path

from flask import current_app

from .db_models import InvalidPayload, Reading
from .extensions import db
from .schemas import normalize_payload


def process_payload(data):
    """Normalise a payload, run the hybrid decision and attach sensor data."""
    import pandas as pd  # local import: keeps pandas out of the import path

    from .decision import final_hybrid_decision
    from .led import automation_payload
    from .plantation import compute_growth_days, get_plantation_date

    payload = normalize_payload(data)

    plantation_date = get_plantation_date()
    growth_days = compute_growth_days(plantation_date)

    row = pd.Series({
        # The temperature column name is model-dependent; the decision engine
        # reads it from the ML bundle, so we set both the generic key and the
        # model's expected key via the bundle's temp_col.
        "Humidity (%)": payload["humidity"],
        "TDS Value (ppm)": payload["tds"],
        "pH Level": payload["ph"],
        "Growth Days": growth_days,
        "Water Level (%)": payload["water_level"],
        "Water Temperature (°C)": payload["water_temperature"],
        "Temperature Outside (°C)": payload["temperature_outside"],
        "Humidity Outside (%)": payload["humidity_outside"],
    })

    from .ml import get_bundle

    row[get_bundle().temp_col] = payload["temperature"]

    result = final_hybrid_decision(row)

    payload["growth_days"] = growth_days
    payload["plantation_date"] = plantation_date.isoformat()
    result["sensor_data"] = payload

    # These two are for the ESP32: parseAutomation() reads "automation" to
    # sync the LED relay with what was set on the dashboard, and the
    # firmware's TFT "DAP" readout is populated from "dap". Neither key
    # existed in the response before, so both features were dead on the
    # firmware side despite the firmware already expecting them.
    result["dap"] = growth_days
    result["automation"] = automation_payload()

    return result


def save_reading(result):
    """Persist a decision ``result`` dict as a :class:`Reading` row."""
    payload = result["sensor_data"]

    reading = Reading(
        temperature=payload["temperature"],
        humidity=payload["humidity"],
        temperature_outside=payload.get("temperature_outside"),
        humidity_outside=payload.get("humidity_outside"),
        water_temperature=payload.get("water_temperature"),
        tds=payload["tds"],
        ph=payload["ph"],
        growth_days=payload["growth_days"],
        water_level=payload["water_level"],
        led_on=payload.get("led_on"),
        led_mode=payload.get("led_mode"),
        pump_on=payload.get("pump_on"),
        fan_on=payload.get("fan_on"),
        final_decision=result["final_decision"],
        actuator_command=result["actuator_command"],
        anomaly=result.get("anomaly"),
        anomaly_score=result.get("anomaly_score"),
        severity=result.get("severity"),
        result_json=json.dumps(result),
    )

    db.session.add(reading)
    db.session.commit()

    return reading


def log_invalid_payload(raw_data, error):
    """Persist a rejected /predict payload for later diagnosis.

    Previously an invalid payload just returned 400 and vanished - there was
    no way to tell, after the fact, whether the ESP32 sent bad data, dropped
    a field, or the request never really reached the sensors' logic at all.
    """
    entry = InvalidPayload(
        raw_payload=json.dumps(raw_data) if raw_data is not None else None,
        error_message=str(error),
    )
    db.session.add(entry)
    db.session.commit()
    return entry


_export_thread = None
_export_stop_event = threading.Event()


def _export_worker(app, interval_minutes, export_dir):
    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    with app.app_context():
        while not _export_stop_event.wait(interval_minutes * 60):
            try:
                buffer = export_readings_excel()
                filename = export_dir / f"hydromon_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                with open(filename, "wb") as handle:
                    handle.write(buffer.getvalue())
                app.logger.info("Generated scheduled export: %s", filename)
            except Exception as exc:
                app.logger.exception("Scheduled export failed")


def start_export_scheduler(app):
    global _export_thread, _export_stop_event

    if _export_thread is not None and _export_thread.is_alive():
        return

    _export_stop_event.clear()
    interval = app.config.get("EXPORT_INTERVAL_MINUTES", 5)
    export_dir = app.config.get("EXPORT_DIR", Path("exports"))

    _export_thread = threading.Thread(
        target=_export_worker,
        args=(app, interval, export_dir),
        daemon=True,
        name="HydromonExportScheduler",
    )
    _export_thread.start()


def get_history():
    """Return the most recent decision results in chronological order.

    Mirrors the previous in-memory deque (max length ``MAX_HISTORY``, oldest
    first).
    """
    limit = current_app.config["MAX_HISTORY"]

    rows = (
        Reading.query
        .order_by(Reading.id.desc())
        .limit(limit)
        .all()
    )

    return [json.loads(row.result_json) for row in reversed(rows)]


def get_latest():
    """Return the most recent decision result, or ``None`` if there are none."""
    row = Reading.query.order_by(Reading.id.desc()).first()

    if row is None:
        return None

    return json.loads(row.result_json)


# --- Plantation date -------------------------------------------------------

def get_plantation_info():
    from .plantation import compute_growth_days, get_plantation_date

    plantation_date = get_plantation_date()
    return {
        "plantation_date": plantation_date.isoformat(),
        "growth_days": compute_growth_days(plantation_date),
    }


def update_plantation_date(date_str):
    from .plantation import compute_growth_days, set_plantation_date

    if not date_str:
        raise ValueError("Le champ plantation_date est requis (format AAAA-MM-JJ).")

    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Date invalide, format attendu AAAA-MM-JJ.") from exc

    if parsed > date.today():
        raise ValueError("La date de plantation ne peut pas etre dans le futur.")

    config = set_plantation_date(parsed)

    return {
        "plantation_date": config.plantation_date.isoformat(),
        "growth_days": compute_growth_days(config.plantation_date),
    }


# --- LED automation ----------------------------------------------------

def get_led_info():
    from .led import get_led_settings

    settings = get_led_settings()
    return {
        "mode": settings.mode,
        "manual_state": settings.manual_state,
        "on_hour": settings.on_hour,
        "off_hour": settings.off_hour,
    }


def update_led_settings(mode=None, manual_state=None, on_hour=None, off_hour=None):
    from .led import set_led_settings

    settings = set_led_settings(
        mode=mode, manual_state=manual_state, on_hour=on_hour, off_hour=off_hour
    )

    return {
        "mode": settings.mode,
        "manual_state": settings.manual_state,
        "on_hour": settings.on_hour,
        "off_hour": settings.off_hour,
    }


# --- Excel export ------------------------------------------------------

def export_readings_excel():
    """Build an in-memory .xlsx workbook of every stored reading."""
    import pandas as pd
    from io import BytesIO

    rows = Reading.query.order_by(Reading.id.asc()).all()

    records = [{
        "ID": r.id,
        "Horodatage (UTC)": r.created_at.isoformat(sep=" ", timespec="seconds"),
        "Temp. interieure (C)": r.temperature,
        "Humidite interieure (%)": r.humidity,
        "Temp. exterieure (C)": r.temperature_outside,
        "Humidite exterieure (%)": r.humidity_outside,
        "Temp. eau (C)": r.water_temperature,
        "TDS (ppm)": r.tds,
        "pH": r.ph,
        "Niveau d'eau (%)": r.water_level,
        "Jours apres plantation": r.growth_days,
        "LED": (
            "ON" if r.led_on is True else "OFF" if r.led_on is False else "N/A"
        ),
        "Mode LED": r.led_mode or "N/A",
        "Pompe": (
            "ON" if r.pump_on is True else "OFF" if r.pump_on is False else "N/A"
        ),
        "Ventilateur": (
            "ON" if r.fan_on is True else "OFF" if r.fan_on is False else "N/A"
        ),
        "Decision": r.final_decision,
        "Commande actionneur": r.actuator_command,
        "Anomalie": r.anomaly,
        "Score anomalie": r.anomaly_score,
        "Severite": r.severity,
    } for r in rows]

    df = pd.DataFrame(records)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Mesures")
        workbook = writer.book
        workbook.security.workbookPassword = current_app.config.get("EXPORT_PASSWORD", "manalpfe2026")
        workbook.security.lockStructure = True
    buffer.seek(0)

    return buffer
