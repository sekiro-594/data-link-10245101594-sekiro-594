from __future__ import annotations

import csv
import json
from pathlib import Path

from m2_protocol import (
    MAX22,
    encode_position_message,
    load_raw_states,
    parse_states,
)
from m3_tracks import (
    build_current_situation,
    build_tracks,
    decode_message_stream,
    save_records_to_sqlite,
)
from m4_mapping import map_to_unified, verify_candidate_mapping
from m5_quality import build_quality_situation, check_duplicates, check_record


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
DATA_DIR = ROOT / "data"

STATE = {}


def write_csv(path: Path, rows, fields=None) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fields or (list(rows[0]) if rows else [])

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def prepare_output_directory() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def parse() -> None:
    raw_states = load_raw_states(str(DATA_DIR / "raw_states.json"))
    STATE["parsed"] = parse_states(raw_states)


def encode() -> None:
    frames = []
    accepted_records = []
    validation_errors = []

    for record_no, record in enumerate(STATE["parsed"]):
        try:
            frame = encode_position_message(record, record_no)
            frames.append(frame)
            accepted_records.append(record)
        except Exception as error:
            validation_errors.append(
                {
                    "record_no": record_no,
                    "target_id": record.get("target_id"),
                    "stage": "encode",
                    "field": "",
                    "problem_type": str(error).split(":")[0],
                    "value": "",
                    "description": str(error),
                }
            )

    (OUTPUT_DIR / "encoded_messages.bin").write_bytes(b"".join(frames))
    STATE["accepted"] = accepted_records
    STATE["validation"] = validation_errors


def decode_validate() -> None:
    binary_data = (OUTPUT_DIR / "encoded_messages.bin").read_bytes()
    decoded_records = decode_message_stream(binary_data)
    STATE["decoded"] = decoded_records

    write_csv(OUTPUT_DIR / "decoded_partner_states.csv", decoded_records)
    write_csv(
        OUTPUT_DIR / "validation_log.csv",
        STATE["validation"],
        [
            "record_no",
            "target_id",
            "stage",
            "field",
            "problem_type",
            "value",
            "description",
        ],
    )

    roundtrip_fields = [
        ("latitude", "lat", 180 / MAX22, 0, "latitude_code"),
        ("longitude", "lon", 360 / MAX22, 1, "longitude_code"),
        ("altitude", "altitude", 1.0, 2, "altitude_code"),
        ("velocity", "speed", 0.1, 3, "speed_code"),
        ("heading", "heading", 0.01, 4, "heading_code"),
        ("vertical_rate", "vertical_rate", 0.01, 5, "vertical_rate_code"),
    ]

    report = []
    for source, decoded in zip(STATE["accepted"], decoded_records):
        for source_field, decoded_field, tolerance, flag_bit, code_field in roundtrip_fields:
            source_value = source.get(source_field)
            decoded_value = decoded.get(decoded_field)
            if source_value is not None and decoded_value is not None:
                absolute_error = abs(source_value - decoded_value)
            else:
                absolute_error = None

            passed = (source_value is None and decoded_value is None) or (
                absolute_error is not None
                and absolute_error <= tolerance + 1e-9
            )
            report.append(
                {
                    "field": source_field,
                    "source_value": source_value,
                    "source_valid": source_value is not None,
                    "protocol_code": decoded.get(code_field),
                    "flag_bit": flag_bit,
                    "decoded_value": decoded_value,
                    "decoded_valid": decoded_value is not None,
                    "absolute_error/tolerance": f"{absolute_error}/{tolerance}",
                    "passed": passed,
                }
            )

    write_csv(OUTPUT_DIR / "roundtrip_report.csv", report)


def build_tracks_stage() -> None:
    binary_data = (DATA_DIR / "partner_messages_multitime.bin").read_bytes()
    multitime_records = decode_message_stream(binary_data)
    STATE["multi"] = multitime_records

    write_csv(OUTPUT_DIR / "decoded_multitime.csv", multitime_records)
    write_csv(OUTPUT_DIR / "track_table.csv", build_tracks(multitime_records))

    current_situation = build_current_situation(multitime_records)
    STATE["current"] = current_situation
    write_csv(OUTPUT_DIR / "current_situation.csv", current_situation)
    save_records_to_sqlite(multitime_records, str(OUTPUT_DIR / "states.db"))


def map_unified() -> None:
    candidate_path = ROOT / "reference" / "pre_generated_mapping_candidate.csv"
    candidate_rows = read_csv(candidate_path)
    write_csv(OUTPUT_DIR / "llm_mapping_candidate.csv", candidate_rows)

    verified_rows = verify_candidate_mapping(candidate_rows)
    write_csv(OUTPUT_DIR / "verified_mapping_table.csv", verified_rows)

    unified_rows = [
        map_to_unified(record, "OpenSky") for record in STATE["current"]
    ]
    partner_rows = read_csv(DATA_DIR / "m4" / "partner_current_situation.csv")
    unified_rows.extend(
        map_to_unified(record, "TeachingLink") for record in partner_rows
    )

    ndjson_path = OUTPUT_DIR / "unified_situation.ndjson"
    with ndjson_path.open("w", encoding="utf-8") as file:
        for row in unified_rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")

    STATE["unified"] = unified_rows


def check_quality() -> None:
    records = read_csv(DATA_DIR / "m5" / "anomaly_cases.csv")
    alerts = []
    for record in records:
        alerts.extend(check_record(record))
    alerts.extend(check_duplicates(records))

    write_csv(
        OUTPUT_DIR / "alert_log.csv",
        alerts,
        [
            "alert_time",
            "target_id",
            "alert_type",
            "severity",
            "field",
            "description",
        ],
    )

    quality_rows = build_quality_situation(records, alerts)
    write_csv(OUTPUT_DIR / "quality_situation.csv", quality_rows)
    STATE["alerts"] = alerts
    STATE["quality"] = quality_rows


def export_results() -> None:
    summary = {
        "parsed_records": len(STATE["parsed"]),
        "encoded_frames": len(STATE["accepted"]),
        "decoded_frames": len(STATE["decoded"]),
        "multitime_frames": len(STATE["multi"]),
        "targets": len(STATE["current"]),
        "unified_messages": len(STATE["unified"]),
        "alerts": len(STATE["alerts"]),
    }
    (OUTPUT_DIR / "experiment_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_pipeline() -> None:
    prepare_output_directory()
    parse()
    encode()
    decode_validate()
    build_tracks_stage()
    map_unified()
    check_quality()
    export_results()


def main() -> int:
    run_pipeline()
    summary_path = OUTPUT_DIR / "experiment_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
