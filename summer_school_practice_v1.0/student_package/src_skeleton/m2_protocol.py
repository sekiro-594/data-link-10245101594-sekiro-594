from __future__ import annotations

import json
import math
from typing import Any


FRAME_SIZE = 41
MAX22 = (1 << 22) - 1


def quantize(value: float) -> int:
    """按实验手册中的 Q(y)=floor(y+0.5) 进行量化。"""
    return math.floor(value + 0.5)


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def parse_state_vector(vector: list[Any]) -> dict[str, Any] | None:
    """把一条 OpenSky 数组记录整理成发送方使用的字典。"""
    if len(vector) < 17 or vector[0] is None:
        return None

    target_id = str(vector[0]).lower()
    if len(target_id) != 6 or any(
        character not in "0123456789abcdef" for character in target_id
    ):
        return None

    timestamp = vector[3] if vector[3] is not None else vector[4]
    altitude = vector[7] if vector[7] is not None else vector[13]

    if vector[3] is not None:
        timestamp_source = "time_position"
    elif vector[4] is not None:
        timestamp_source = "last_contact"
    else:
        timestamp_source = "none"

    if vector[7] is not None:
        altitude_type = "barometric"
    elif vector[13] is not None:
        altitude_type = "geometric"
    else:
        altitude_type = "unknown"

    callsign = None
    if vector[1] is not None:
        callsign = str(vector[1]).strip() or None

    return {
        "target_id": target_id,
        "callsign": callsign,
        "timestamp": int(timestamp) if timestamp is not None else None,
        "timestamp_source": timestamp_source,
        "longitude": _to_number(vector[5]),
        "latitude": _to_number(vector[6]),
        "altitude": _to_number(altitude),
        "alt_type": altitude_type,
        "velocity": _to_number(vector[9]),
        "heading": _to_number(vector[10]),
        "vertical_rate": _to_number(vector[11]),
        "on_ground": bool(vector[8]),
    }


def load_raw_states(path: str) -> list[list[Any]]:
    with open(path, encoding="utf-8") as file:
        return json.load(file)["states"]


def parse_states(states: list[list[Any]]) -> list[dict[str, Any]]:
    parsed_records = []
    for vector in states:
        record = parse_state_vector(vector)
        if record is not None:
            parsed_records.append(record)
    return parsed_records


def calculate_checksum(data: bytes) -> int:
    return sum(data) % 65536


def _encode_number(value: Any, formula, limit: int) -> int:
    if value is None:
        return 0

    code = quantize(formula(float(value)))
    if not 0 <= code <= limit:
        raise ValueError("OUT_OF_RANGE")
    return code


def encode_position_message(record: dict[str, Any], message_seq: int) -> bytes:
    """将一条内部状态编码为 41 字节 TeachingLink 位置状态帧。"""
    target_id = str(record.get("target_id", "")).lower()
    timestamp = record.get("timestamp")

    if len(target_id) != 6 or any(
        character not in "0123456789abcdef" for character in target_id
    ):
        raise ValueError("REQUIRED_FIELD_MISSING: target_id")
    if timestamp is None or not 0 <= int(timestamp) <= 0xFFFFFFFF:
        raise ValueError("REQUIRED_FIELD_MISSING: timestamp")

    frame = bytearray(FRAME_SIZE)
    frame[0:2] = b"DS"
    frame[2] = 1
    frame[3] = 1
    frame[4:6] = FRAME_SIZE.to_bytes(2, "big")
    frame[6:8] = (message_seq % 65536).to_bytes(2, "big")
    frame[8:12] = int(timestamp).to_bytes(4, "big")
    frame[12:15] = int(target_id, 16).to_bytes(3, "big")

    validity_flags = 0
    callsign = record.get("callsign")
    if callsign is not None:
        callsign_bytes = str(callsign).strip().encode("ascii")
        if not 1 <= len(callsign_bytes) <= 8:
            raise ValueError("ENCODING_ERROR: callsign")
        frame[15:23] = callsign_bytes.ljust(8, b"\0")
        validity_flags |= 1 << 6

    field_specs = [
        ("latitude", 23, 26, lambda x: (x + 90) / 180 * MAX22, MAX22, 0),
        ("longitude", 26, 29, lambda x: (x + 180) / 360 * MAX22, MAX22, 1),
        ("altitude", 29, 31, lambda x: x + 1000, 65535, 2),
        ("velocity", 31, 33, lambda x: x / 0.1, 65535, 3),
        ("heading", 33, 35, lambda x: x / 0.01, 35999, 4),
        ("vertical_rate", 35, 37, lambda x: (x + 327.68) / 0.01, 65535, 5),
    ]

    for name, start, end, formula, limit, bit in field_specs:
        value = record.get(name)
        code = _encode_number(value, formula, limit)
        frame[start:end] = code.to_bytes(end - start, "big")
        if value is not None:
            validity_flags |= 1 << bit

    status_flags = int(bool(record.get("on_ground")))
    if record.get("altitude") is not None and record.get("alt_type") == "geometric":
        status_flags |= 1 << 1
    if record.get("timestamp_source") == "last_contact":
        status_flags |= 1 << 2

    frame[37] = status_flags
    frame[38] = validity_flags
    frame[39:41] = calculate_checksum(frame[:39]).to_bytes(2, "big")
    return bytes(frame)


def decode_position_message(data: bytes) -> dict[str, Any]:
    """检查并解码一帧 TeachingLink 消息。"""
    if len(data) != FRAME_SIZE:
        raise ValueError("LENGTH_ERROR")

    errors = []
    if data[0:2] != b"DS":
        errors.append("MAGIC_ERROR")
    if data[2] != 1:
        errors.append("VERSION_ERROR")
    if data[3] != 1:
        errors.append("MESSAGE_TYPE_ERROR")
    if int.from_bytes(data[4:6], "big") != FRAME_SIZE:
        errors.append("LENGTH_ERROR")
    if data[37] & 0xF8 or data[38] & 0x80:
        errors.append("RESERVED_BITS_ERROR")

    checksum = int.from_bytes(data[39:41], "big")
    expected_checksum = calculate_checksum(data[:39])
    if checksum != expected_checksum:
        errors.append("CHECKSUM_ERROR")

    status_flags = data[37]
    validity_flags = data[38]

    def decode_optional(bit: int, start: int, end: int, formula):
        raw_code = int.from_bytes(data[start:end], "big")
        if not validity_flags & (1 << bit):
            if raw_code != 0:
                errors.append("FLAG_VALUE_INCONSISTENCY")
            return None, raw_code
        return formula(raw_code), raw_code

    latitude, latitude_code = decode_optional(
        0, 23, 26, lambda x: x / MAX22 * 180 - 90
    )
    longitude, longitude_code = decode_optional(
        1, 26, 29, lambda x: x / MAX22 * 360 - 180
    )
    altitude, altitude_code = decode_optional(2, 29, 31, lambda x: x - 1000.0)
    speed, speed_code = decode_optional(3, 31, 33, lambda x: x * 0.1)
    heading, heading_code = decode_optional(4, 33, 35, lambda x: x * 0.01)
    vertical_rate, vertical_rate_code = decode_optional(
        5, 35, 37, lambda x: x * 0.01 - 327.68
    )

    callsign_bytes = data[15:23]
    if validity_flags & (1 << 6):
        callsign = callsign_bytes.rstrip(b"\0").decode("ascii", errors="replace")
    else:
        callsign = None
        if any(callsign_bytes):
            errors.append("FLAG_VALUE_INCONSISTENCY")

    timestamp = int.from_bytes(data[8:12], "big")
    target_id = data[12:15].hex()
    if timestamp == 0 or target_id == "000000":
        errors.append("REQUIRED_FIELD_MISSING")

    altitude_type = "unknown"
    if altitude is not None:
        altitude_type = "geometric" if status_flags & (1 << 1) else "barometric"

    return {
        "version": data[2],
        "message_type": data[3],
        "length": int.from_bytes(data[4:6], "big"),
        "sequence": int.from_bytes(data[6:8], "big"),
        "target_id": target_id,
        "callsign": callsign,
        "timestamp": timestamp,
        "timestamp_source": (
            "last_contact" if status_flags & (1 << 2) else "time_position"
        ),
        "time_source": (
            "last_contact_fallback" if status_flags & (1 << 2) else "position_time"
        ),
        "message_seq": int.from_bytes(data[6:8], "big"),
        "lat": latitude,
        "latitude": latitude,
        "lon": longitude,
        "longitude": longitude,
        "altitude": altitude,
        "velocity": speed,
        "speed": speed,
        "heading": heading,
        "vertical_rate": vertical_rate,
        "on_ground": bool(status_flags & 1),
        "alt_type": altitude_type,
        "status_flags": status_flags,
        "validity_flags": validity_flags,
        "latitude_code": latitude_code,
        "longitude_code": longitude_code,
        "altitude_code": altitude_code,
        "speed_code": speed_code,
        "heading_code": heading_code,
        "vertical_rate_code": vertical_rate_code,
        "lat_valid": bool(validity_flags & 1),
        "lon_valid": bool(validity_flags & 2),
        "altitude_valid": bool(validity_flags & 4),
        "speed_valid": bool(validity_flags & 8),
        "heading_valid": bool(validity_flags & 16),
        "vertical_rate_valid": bool(validity_flags & 32),
        "callsign_valid": bool(validity_flags & 64),
        "checksum": checksum,
        "expected_checksum": expected_checksum,
        "message_valid": not errors,
        "validation_errors": ";".join(dict.fromkeys(errors)),
        "source": "TeachingLink",
    }
