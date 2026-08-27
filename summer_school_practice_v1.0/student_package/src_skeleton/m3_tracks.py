from __future__ import annotations

import sqlite3
from typing import Any

from m2_protocol import FRAME_SIZE, decode_position_message


TAIL_ERRORS: list[dict[str, Any]] = []


def decode_message_stream(
    data: bytes, frame_size: int = FRAME_SIZE
) -> list[dict[str, Any]]:
    """按固定帧长读取二进制流，并记录不完整的尾帧。"""
    decoded_records = []
    TAIL_ERRORS.clear()

    for offset in range(0, len(data), frame_size):
        frame = data[offset : offset + frame_size]
        if len(frame) != frame_size:
            TAIL_ERRORS.append(
                {
                    "offset": offset,
                    "problem_type": "LENGTH_ERROR",
                    "length": len(frame),
                }
            )
            continue

        try:
            decoded_records.append(decode_position_message(frame))
        except ValueError as error:
            decoded_records.append(
                {
                    "message_valid": False,
                    "validation_errors": str(error),
                    "source": "TeachingLink",
                }
            )

    return decoded_records


def save_records_to_sqlite(records, db_path) -> None:
    columns = [
        "target_id",
        "callsign",
        "timestamp",
        "timestamp_source",
        "message_seq",
        "lat",
        "lon",
        "altitude",
        "alt_type",
        "speed",
        "heading",
        "vertical_rate",
        "on_ground",
        "status_flags",
        "validity_flags",
        "message_valid",
        "source",
    ]

    create_table_sql = """
        CREATE TABLE state_record(
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id TEXT,
            callsign TEXT,
            timestamp INTEGER,
            timestamp_source TEXT,
            message_seq INTEGER,
            lat REAL,
            lon REAL,
            altitude REAL,
            alt_type TEXT,
            speed REAL,
            heading REAL,
            vertical_rate REAL,
            on_ground INTEGER,
            status_flags INTEGER,
            validity_flags INTEGER,
            message_valid INTEGER,
            source TEXT
        )
    """

    valid_records = [record for record in records if record.get("message_valid")]
    rows = []
    for record in valid_records:
        row = []
        for column in columns:
            value = record.get(column)
            if column in ("on_ground", "message_valid"):
                value = int(value)
            row.append(value)
        rows.append(row)

    placeholders = ",".join("?" for _ in columns)
    insert_sql = (
        f"INSERT INTO state_record({','.join(columns)}) VALUES({placeholders})"
    )

    with sqlite3.connect(db_path) as connection:
        connection.execute("DROP TABLE IF EXISTS state_record")
        connection.execute(create_table_sql)
        connection.executemany(insert_sql, rows)


def _can_build_track(record: dict[str, Any]) -> bool:
    return (
        bool(record.get("message_valid"))
        and bool(record.get("target_id"))
        and record.get("timestamp") is not None
    )


def build_tracks(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if _can_build_track(record):
            groups.setdefault(record["target_id"], []).append(record)

    track_rows = []
    for target_id, target_records in sorted(groups.items()):
        ordered_records = sorted(
            target_records,
            key=lambda item: (int(item["timestamp"]), int(item.get("message_seq", 0))),
        )
        for sequence_no, record in enumerate(ordered_records, start=1):
            track_rows.append(
                {
                    "target_id": target_id,
                    "timestamp": record["timestamp"],
                    "message_seq": record.get("message_seq"),
                    "track_sequence_no": sequence_no,
                    "lat": record.get("lat"),
                    "lon": record.get("lon"),
                    "altitude": record.get("altitude"),
                    "speed": record.get("speed"),
                    "heading": record.get("heading"),
                }
            )
    return track_rows


def build_current_situation(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest_record: dict[str, dict[str, Any]] = {}
    track_lengths: dict[str, int] = {}

    for record in records:
        if not _can_build_track(record):
            continue

        target_id = record["target_id"]
        track_lengths[target_id] = track_lengths.get(target_id, 0) + 1

        current_key = (record["timestamp"], record.get("message_seq", 0))
        previous = latest_record.get(target_id)
        if previous is None:
            latest_record[target_id] = record
            continue

        previous_key = (previous["timestamp"], previous.get("message_seq", 0))
        if current_key > previous_key:
            latest_record[target_id] = record

    current_situation = []
    protocol_fields = [
        "status_flags",
        "validity_flags",
        "latitude_code",
        "longitude_code",
        "altitude_code",
        "speed_code",
        "heading_code",
        "vertical_rate_code",
    ]

    for target_id, record in sorted(latest_record.items()):
        row = {
            "target_id": target_id,
            "callsign": record.get("callsign"),
            "latest_time": record["timestamp"],
            "lat": record.get("lat"),
            "lon": record.get("lon"),
            "altitude": record.get("altitude"),
            "speed": record.get("speed"),
            "heading": record.get("heading"),
            "vertical_rate": record.get("vertical_rate"),
            "on_ground": record.get("on_ground"),
            "track_length": track_lengths[target_id],
            "alt_type": record.get("alt_type"),
            "time_source": record.get("time_source"),
            "message_valid": True,
        }
        for field in protocol_fields:
            row[field] = record.get(field)
        current_situation.append(row)

    return current_situation
