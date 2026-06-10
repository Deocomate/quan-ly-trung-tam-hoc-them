from __future__ import annotations

import json
import re
from datetime import date

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import Student
from app.timezone import month_bounds, today_vietnam

DEFAULT_TEMPLATE_BLOCKS: list[dict[str, str]] = [
    {"type": "YEAR", "value": "YYYY"},
    {"type": "TEXT", "value": "HS"},
    {"type": "SEQ", "value": "6", "reset": "yearly"},
]

TEXT_PATTERN = re.compile(r"[^a-zA-Z0-9]")
MAX_STUDENT_CODE_LENGTH = 80


def _sanitize_text(value: str) -> str:
    return TEXT_PATTERN.sub("", value or "").upper()


def _clamp_seq_padding(value: str) -> int:
    try:
        padding = int(value)
    except (TypeError, ValueError):
        padding = 6
    return max(3, min(8, padding))


def parse_template_blocks(template_json_str: str | None) -> list[dict[str, str]]:
    if not template_json_str or not template_json_str.strip():
        return [block.copy() for block in DEFAULT_TEMPLATE_BLOCKS]

    try:
        parsed = json.loads(template_json_str)
    except (TypeError, ValueError, json.JSONDecodeError):
        return [block.copy() for block in DEFAULT_TEMPLATE_BLOCKS]

    if not isinstance(parsed, list) or not parsed:
        return [block.copy() for block in DEFAULT_TEMPLATE_BLOCKS]

    blocks: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        block_type = str(item.get("type", "")).upper()
        if block_type not in {"YEAR", "MONTH", "DAY", "TEXT", "SEQ"}:
            continue

        block: dict[str, str] = {"type": block_type}
        if block_type == "YEAR":
            block["value"] = "YY" if str(item.get("value", "")).upper() == "YY" else "YYYY"
        elif block_type in {"MONTH", "DAY"}:
            block["value"] = str(item.get("value", "MM" if block_type == "MONTH" else "DD"))
        elif block_type == "TEXT":
            block["value"] = _sanitize_text(str(item.get("value", "")))
        elif block_type == "SEQ":
            block["value"] = str(_clamp_seq_padding(str(item.get("value", "6"))))
            reset_mode = str(item.get("reset", "yearly")).lower()
            block["reset"] = reset_mode if reset_mode in {"yearly", "monthly", "never"} else "yearly"

        blocks.append(block)

    if not blocks:
        return [block.copy() for block in DEFAULT_TEMPLATE_BLOCKS]
    return blocks


def _seq_count(db: Session, reset_mode: str, t_now: date) -> int:
    stmt = select(func.count(Student.id))
    if reset_mode == "yearly":
        start = date(t_now.year, 1, 1)
        end = date(t_now.year + 1, 1, 1)
        stmt = stmt.where(and_(Student.created_at >= start, Student.created_at < end))
    elif reset_mode == "monthly":
        start, end = month_bounds(t_now.year, t_now.month)
        stmt = stmt.where(and_(Student.created_at >= start, Student.created_at < end))
    return db.scalar(stmt) or 0


def generate_custom_student_code(db: Session, template_json_str: str | None) -> str:
    blocks = parse_template_blocks(template_json_str)
    t_now = today_vietnam()
    code_parts: list[str] = []

    for block in blocks:
        block_type = block.get("type")
        block_value = block.get("value", "")

        if block_type == "YEAR":
            code_parts.append(str(t_now.year) if block_value == "YYYY" else str(t_now.year)[-2:])
        elif block_type == "MONTH":
            code_parts.append(f"{t_now.month:02d}")
        elif block_type == "DAY":
            code_parts.append(f"{t_now.day:02d}")
        elif block_type == "TEXT":
            code_parts.append(block_value)
        elif block_type == "SEQ":
            reset_mode = block.get("reset", "yearly")
            padding = _clamp_seq_padding(block_value)
            next_num = _seq_count(db, reset_mode, t_now) + 1
            code_parts.append(f"{next_num:0{padding}d}")

    result = "".join(code_parts)
    if not result or len(result) > MAX_STUDENT_CODE_LENGTH:
        return generate_custom_student_code(db, json.dumps(DEFAULT_TEMPLATE_BLOCKS))
    return result
