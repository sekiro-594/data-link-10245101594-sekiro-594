from __future__ import annotations

from typing import Any


MAX22 = (1 << 22) - 1


def _number_or_none(value: Any) -> float | None:
    if value in (None, "", "None", "null"):
        return None
    return float(value)


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("1", "true", "yes")


def verify_candidate_mapping(
    candidate_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """返回对照字段定义和协议说明后确认的映射规则。"""
    # 候选表用于列出需要检查的字段，最终规则以人工核验结果为准。
    _ = candidate_rows
    rules = [
        (
            "OpenSky",
            "target_id",
            "track_id",
            "lowercase, preserve six hex digits",
            "none",
            "reject null",
            "source_field_definitions.md: track_id",
            "true",
        ),
        (
            "OpenSky",
            "latest_time",
            "timestamp",
            "positive Unix seconds",
            "none",
            "reject null",
            "source_field_definitions.md: timestamp",
            "true",
        ),
        (
            "OpenSky",
            "callsign",
            "identity.callsign",
            "direct trimmed text",
            "none",
            "blank -> null",
            "source_field_definitions.md: callsign",
            "true",
        ),
        (
            "OpenSky",
            "lat",
            "position.lat",
            "direct numeric value",
            "degrees",
            "blank -> null",
            "source_field_definitions.md: position.lat",
            "true",
        ),
        (
            "OpenSky",
            "lon",
            "position.lon",
            "direct numeric value",
            "degrees",
            "blank -> null",
            "source_field_definitions.md: position.lon",
            "true",
        ),
        (
            "OpenSky",
            "altitude+alt_type",
            "position.alt/position.alt_type",
            "direct altitude and source label",
            "metres",
            "blank altitude -> null/unknown",
            "source_field_definitions.md: altitude",
            "true",
        ),
        (
            "OpenSky",
            "speed/heading/vertical_rate",
            "motion.*",
            "direct numeric values",
            "m/s, degrees, m/s",
            "blank -> null",
            "source_field_definitions.md: motion",
            "true",
        ),
        (
            "OpenSky",
            "on_ground",
            "status.on_ground",
            "convert to boolean",
            "none",
            "missing -> false",
            "source_field_definitions.md: status",
            "true",
        ),
        (
            "OpenSky",
            "time_source",
            "quality.time_source",
            "direct controlled value",
            "none",
            "missing -> position_time",
            "source_field_definitions.md: time_source",
            "true",
        ),
        (
            "OpenSky",
            "lat+lon",
            "quality.position_valid",
            "both non-null and within range",
            "none",
            "missing coordinate -> false",
            "source_field_definitions.md: position_valid",
            "true",
        ),
        (
            "OpenSky",
            "message_valid",
            "quality.message_valid",
            "direct boolean",
            "none",
            "missing -> false",
            "source record validation",
            "true",
        ),
        (
            "TeachingLink",
            "target_id",
            "track_id",
            "lowercase, preserve leading zeros",
            "none",
            "reject null",
            "teaching_message_spec.md offsets 12-14",
            "true",
        ),
        (
            "TeachingLink",
            "timestamp",
            "timestamp",
            "positive uint32 Unix seconds",
            "seconds",
            "zero -> invalid",
            "teaching_message_spec.md offsets 8-11",
            "true",
        ),
        (
            "TeachingLink",
            "callsign+validity_flags.bit6",
            "identity.callsign",
            "strip NUL padding",
            "ASCII",
            "bit6=0 -> null",
            "teaching_message_spec.md offsets 15-22",
            "true",
        ),
        (
            "TeachingLink",
            "latitude_code+validity_flags.bit0",
            "position.lat",
            "code/(2^22-1)*180-90",
            "code to degrees",
            "bit0=0 -> null",
            "teaching_message_spec.md offsets 23-25",
            "true",
        ),
        (
            "TeachingLink",
            "longitude_code+validity_flags.bit1",
            "position.lon",
            "code/(2^22-1)*360-180",
            "code to degrees",
            "bit1=0 -> null",
            "teaching_message_spec.md offsets 26-28",
            "true",
        ),
        (
            "TeachingLink",
            "altitude_code+validity_flags.bit2",
            "position.alt",
            "code-1000",
            "code to metres",
            "bit2=0 -> null",
            "teaching_message_spec.md offsets 29-30",
            "true",
        ),
        (
            "TeachingLink",
            "status_flags.bit1",
            "position.alt_type",
            "0=barometric;1=geometric",
            "none",
            "altitude invalid -> unknown",
            "teaching_message_spec.md status bit1",
            "true",
        ),
        (
            "TeachingLink",
            "speed_code+validity_flags.bit3",
            "motion.speed",
            "code*0.1",
            "code to m/s",
            "bit3=0 -> null",
            "teaching_message_spec.md offsets 31-32",
            "true",
        ),
        (
            "TeachingLink",
            "heading_code+validity_flags.bit4",
            "motion.heading",
            "code*0.01 and <360",
            "code to degrees",
            "bit4=0 -> null",
            "teaching_message_spec.md offsets 33-34",
            "true",
        ),
        (
            "TeachingLink",
            "vertical_rate_code+validity_flags.bit5",
            "motion.vertical_rate",
            "code*0.01-327.68",
            "code to m/s",
            "bit5=0 -> null",
            "teaching_message_spec.md offsets 35-36",
            "true",
        ),
        (
            "TeachingLink",
            "status_flags.bit0",
            "status.on_ground",
            "convert bit to boolean",
            "none",
            "always available",
            "teaching_message_spec.md status bit0",
            "true",
        ),
        (
            "TeachingLink",
            "status_flags.bit2",
            "quality.time_source",
            "1=last_contact_fallback;0=position_time",
            "none",
            "timestamp invalid -> time_valid false",
            "source_field_definitions.md time_source",
            "true",
        ),
        (
            "TeachingLink",
            "lat/lon valid bits+range",
            "quality.position_valid",
            "both valid and within geographic range",
            "none",
            "missing coordinate -> false",
            "source_field_definitions.md: position_valid",
            "true",
        ),
        (
            "TeachingLink",
            "message_valid",
            "quality.message_valid",
            "direct boolean",
            "none",
            "missing -> false",
            "complete receiver validation criteria",
            "true",
        ),
    ]

    verified_rows = []
    for (
        source_format,
        input_field,
        unified_field,
        mapping_rule,
        unit_conversion,
        null_strategy,
        evidence,
        verified,
    ) in rules:
        verified_rows.append(
            {
                "source_format": source_format,
                "input_field": input_field,
                "unified_field": unified_field,
                "mapping_rule": mapping_rule,
                "unit_conversion": unit_conversion,
                "null_strategy": null_strategy,
                "evidence": evidence,
                "verified": verified,
            }
        )
    return verified_rows


def map_to_unified(
    record: dict[str, Any], source_format: str
) -> dict[str, Any]:
    teaching_link = source_format.lower().startswith("teaching")
    target_id = str(record.get("target_id", "")).lower().zfill(6)

    if teaching_link:
        timestamp = record.get("timestamp", record.get("latest_time"))
    else:
        timestamp = record.get("latest_time")

    latitude = _number_or_none(record.get("lat"))
    longitude = _number_or_none(record.get("lon"))
    altitude = _number_or_none(record.get("altitude"))
    speed = _number_or_none(record.get("speed"))
    heading = _number_or_none(record.get("heading"))
    vertical_rate = _number_or_none(record.get("vertical_rate"))

    validity_flags = int(record.get("validity_flags") or 0)
    status_flags = int(record.get("status_flags") or 0)

    if teaching_link:
        latitude = (
            float(record["latitude_code"]) / MAX22 * 180 - 90
            if validity_flags & 1
            else None
        )
        longitude = (
            float(record["longitude_code"]) / MAX22 * 360 - 180
            if validity_flags & 2
            else None
        )
        altitude = (
            float(record["altitude_code"]) - 1000
            if validity_flags & 4
            else None
        )
        speed = (
            float(record["speed_code"]) * 0.1 if validity_flags & 8 else None
        )
        heading = (
            float(record["heading_code"]) * 0.01
            if validity_flags & 16
            else None
        )
        vertical_rate = (
            float(record["vertical_rate_code"]) * 0.01 - 327.68
            if validity_flags & 32
            else None
        )
        callsign = (record.get("callsign") or None) if validity_flags & 64 else None
        altitude_type = (
            ("geometric" if status_flags & 2 else "barometric")
            if altitude is not None
            else "unknown"
        )
        time_source = (
            "last_contact_fallback" if status_flags & 4 else "position_time"
        )
    else:
        callsign = record.get("callsign") or None
        altitude_type = record.get("alt_type", "unknown")
        time_source = record.get(
            "time_source", record.get("timestamp_source", "position_time")
        )

    message_valid = _to_bool(record.get("message_valid", True))
    time_valid = timestamp not in (None, "") and int(float(timestamp)) > 0

    return {
        "track_id": target_id,
        "source": "TeachingLink" if teaching_link else "OpenSky",
        "timestamp": int(float(timestamp)) if time_valid else 0,
        "identity": {"callsign": callsign},
        "position": {
            "lat": latitude,
            "lon": longitude,
            "alt": altitude,
            "alt_type": altitude_type,
        },
        "motion": {
            "speed": speed,
            "heading": heading,
            "vertical_rate": vertical_rate,
        },
        "status": {"on_ground": _to_bool(record.get("on_ground", False))},
        "quality": {
            "position_valid": (
                latitude is not None
                and longitude is not None
                and -90 <= latitude <= 90
                and -180 <= longitude <= 180
            ),
            "time_valid": time_valid,
            "message_valid": message_valid,
            "time_source": time_source,
            "anomaly_flags": [],
        },
    }
