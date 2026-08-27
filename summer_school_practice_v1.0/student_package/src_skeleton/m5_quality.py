from __future__ import annotations


BATCH_TIME = 1710000120
EMPTY_VALUES = (None, "", "None", "null")


def _create_alert(
    record,
    alert_type,
    severity,
    field,
    description,
    alert_time=BATCH_TIME,
):
    return {
        "alert_time": alert_time,
        "target_id": record.get("target_id"),
        "timestamp": record.get("timestamp", record.get("latest_time")),
        "alert_type": alert_type,
        "severity": severity,
        "field": field,
        "description": description,
    }


def check_record(record, batch_time=BATCH_TIME):
    """检查单条记录中的缺失、延迟、越界和帧验证问题。"""
    alerts = []

    if record.get("lat") in EMPTY_VALUES or record.get("lon") in EMPTY_VALUES:
        alerts.append(
            _create_alert(
                record,
                "POSITION_MISSING",
                "HIGH",
                "lat/lon",
                "纬度或经度缺失",
                batch_time,
            )
        )

    timestamp = record.get("latest_time", record.get("timestamp"))
    if timestamp not in EMPTY_VALUES and batch_time - int(float(timestamp)) > 60:
        alerts.append(
            _create_alert(
                record,
                "DATA_DELAYED",
                "MEDIUM",
                "timestamp",
                "记录时间相对批次时间延迟超过60秒",
                batch_time,
            )
        )

    heading = record.get("heading")
    if heading not in EMPTY_VALUES and not 0 <= float(heading) < 360:
        alerts.append(
            _create_alert(
                record,
                "HEADING_OUT_OF_RANGE",
                "MEDIUM",
                "heading",
                "航向不在[0,360)范围",
                batch_time,
            )
        )

    if record.get("message_valid") in (False, "False", "false", 0, "0"):
        alerts.append(
            _create_alert(
                record,
                "FRAME_VALIDATION_ERROR",
                "HIGH",
                "message_valid",
                "上游帧未通过接收检查",
                batch_time,
            )
        )

    return alerts


def check_duplicates(records):
    key_counts = {}
    for record in records:
        key = (
            record.get("target_id"),
            record.get("timestamp", record.get("latest_time")),
        )
        key_counts[key] = key_counts.get(key, 0) + 1

    alerts = []
    for record in records:
        key = (
            record.get("target_id"),
            record.get("timestamp", record.get("latest_time")),
        )
        if key_counts[key] > 1:
            alerts.append(
                _create_alert(
                    record,
                    "DUPLICATE_RECORD",
                    "MEDIUM",
                    "target_id+timestamp",
                    "目标与时间联合键重复",
                )
            )
    return alerts


def build_quality_situation(records, alerts):
    quality_rows = []

    for record in records:
        timestamp = record.get("timestamp", record.get("latest_time"))
        related_alerts = [
            alert
            for alert in alerts
            if alert["target_id"] == record.get("target_id")
            and alert["timestamp"] == timestamp
        ]
        alert_types = {alert["alert_type"] for alert in related_alerts}
        severity_levels = {alert["severity"] for alert in related_alerts}

        if "HIGH" in severity_levels:
            anomaly_level = "HIGH"
            display_status = "ERROR"
        elif "MEDIUM" in severity_levels:
            anomaly_level = "MEDIUM"
            display_status = "WARNING"
        else:
            anomaly_level = "NONE"
            display_status = "NORMAL"

        quality_rows.append(
            {
                "target_id": record.get("target_id"),
                "timestamp": timestamp,
                "position_valid": "POSITION_MISSING" not in alert_types,
                "delayed": "DATA_DELAYED" in alert_types,
                "duplicate_detected": "DUPLICATE_RECORD" in alert_types,
                "heading_valid": "HEADING_OUT_OF_RANGE" not in alert_types,
                "message_valid": record.get("message_valid", True),
                "anomaly_level": anomaly_level,
                "display_status": display_status,
            }
        )

    return quality_rows
