"""Physical safety checks, recommendations and user-facing messaging.

These functions are independent of the ML model and operate on a plain
mapping / pandas row. ``temp_col`` is passed in explicitly because the name of
the temperature column is determined by the trained model metadata.
"""


def physical_safety_check(row, temp_col):
    temperature = row[temp_col]
    humidity = row["Humidity (%)"]
    tds = row["TDS Value (ppm)"]
    ph = row["pH Level"]
    growth_days = row["Growth Days"]
    water_level = row.get("Water Level (%)", None)
    water_temperature = row.get("Water Temperature (°C)", None)
    temperature_outside = row.get("Temperature Outside (°C)", None)
    humidity_outside = row.get("Humidity Outside (%)", None)

    blocking_alerts = []
    warning_alerts = []

    if temperature < -10 or temperature > 60:
        blocking_alerts.append("Temperature interieure invalide : verifier le capteur.")
    elif temperature < 15 or temperature > 35:
        warning_alerts.append("Temperature interieure defavorable pour la laitue.")

    if humidity < 0 or humidity > 100:
        blocking_alerts.append("Humidite interieure invalide : verifier le capteur.")
    elif humidity < 40 or humidity > 90:
        warning_alerts.append("Humidite interieure defavorable pour la culture.")

    if tds < 0 or tds > 2000:
        blocking_alerts.append("Valeur TDS invalide : verifier le capteur.")

    if ph < 0 or ph > 14:
        blocking_alerts.append("Valeur pH invalide : verifier le capteur.")

    # Growth day is now derived from the plantation date instead of being
    # typed in per-reading, so a value < 1 should never happen in practice
    # (compute_growth_days() clamps it) - kept as a defensive check. A crop
    # running long (>60 days) is no longer treated as an invalid *reading*
    # (blocking every prediction just because the plantation date is old is
    # worse than warning about it), just a warning to check the date/harvest.
    if growth_days < 1:
        blocking_alerts.append("Age de croissance invalide.")
    elif growth_days > 60:
        warning_alerts.append(
            "Cycle de culture superieur a 60 jours : verifier la date de "
            "plantation ou envisager la recolte."
        )

    if water_level is not None:
        if water_level < 0 or water_level > 100:
            blocking_alerts.append("Niveau d'eau invalide : verifier le capteur ultrason.")
        elif water_level <= 10:
            blocking_alerts.append("Niveau d'eau critique : reservoir presque vide.")
        elif water_level <= 25:
            warning_alerts.append("Niveau d'eau faible : remplissage recommande.")

    # Water temperature (DS18B20) was previously collected by the ESP32 but
    # dropped before it ever reached this check. It directly affects root
    # health and dissolved-oxygen levels, so it gets the same
    # invalid-vs-unfavourable treatment as air temperature.
    if water_temperature is not None:
        if water_temperature < -5 or water_temperature > 50:
            blocking_alerts.append(
                "Temperature de l'eau invalide : verifier le capteur DS18B20."
            )
        elif water_temperature < 15 or water_temperature > 28:
            warning_alerts.append("Temperature de l'eau defavorable pour les racines.")

    # Outside climate isn't used by the fuzzy/ML decision (it's contextual,
    # not actionable for nutrient/pH dosing), so implausible readings are
    # only ever a non-blocking warning - a broken outdoor sensor shouldn't
    # stop indoor irrigation decisions.
    if temperature_outside is not None and not (-10 <= temperature_outside <= 60):
        warning_alerts.append(
            "Temperature exterieure hors plage plausible : verifier le capteur exterieur."
        )

    if humidity_outside is not None and not (0 <= humidity_outside <= 100):
        warning_alerts.append(
            "Humidite exterieure hors plage plausible : verifier le capteur exterieur."
        )

    return {
        "blocking": len(blocking_alerts) > 0,
        "warnings": warning_alerts,
        "blocking_alerts": blocking_alerts,
        "all_alerts": blocking_alerts + warning_alerts
    }


def collect_recommendations(fuzzy_decision, safety_check):
    recommendations = []

    if fuzzy_decision["tds_error"] < 0:
        recommendations.append({
            "type": "nutrients",
            "level": "warning",
            "title": "Nutriments insuffisants",
            "message": "Ajouter manuellement des nutriments a la solution."
        })

    elif fuzzy_decision["tds_error"] > 0:
        recommendations.append({
            "type": "water",
            "level": "warning",
            "title": "TDS trop eleve",
            "message": "Diluer manuellement avec de l'eau propre."
        })

    if fuzzy_decision["ph_error"] > 0:
        recommendations.append({
            "type": "ph",
            "level": "warning",
            "title": "pH trop eleve",
            "message": "Corriger manuellement avec une solution pH Down."
        })

    elif fuzzy_decision["ph_error"] < 0:
        recommendations.append({
            "type": "ph",
            "level": "warning",
            "title": "pH trop faible",
            "message": "Corriger manuellement avec une solution pH Up."
        })

    if len(recommendations) == 0:
        recommendations.append({
            "type": "normal",
            "level": "success",
            "title": "Etat normal",
            "message": "Aucune action necessaire."
        })

    return recommendations


def anomaly_severity(score):
    if score < -0.03:
        return "Critical"
    if score < -0.01:
        return "High"
    if score < 0:
        return "Medium"
    return "Low"


def build_user_response(final_decision):
    messages = {
        "Healthy": (
            "Etat normal.",
            "Aucune action necessaire."
        ),
        "Add Nutrients": (
            "Nutriments insuffisants.",
            "Ajouter manuellement des nutriments a la solution."
        ),
        "Reduce Nutrients": (
            "Concentration nutritive trop elevee.",
            "Diluer manuellement avec de l’eau propre"
        ),
        "Lower pH": (
            "pH trop eleve.",
            "Corriger manuellement le pH avec une solution pH Down."
        ),
        "Increase pH": (
            "pH trop faible.",
            "Corriger manuellement le pH avec une solution pH Up."
        ),
        "Safety Alert": (
            "Anomalie detectee.",
            "Verifier les mesures capteurs avant toute action automatique."
        ),
        "Sensor Alert": (
            "Alerte capteur.",
            "Verifier les capteurs avant de relancer la regulation automatique."
        )
    }

    return messages.get(
        final_decision,
        ("Etat non reconnu.", "Verifier le systeme.")
    )
