"""Small, dependency-free helpers for messy catalog values."""
import json
import math
import re
from typing import Any

import pandas as pd

_NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    try:
        return bool(pd.isna(value)) if not isinstance(value, (list, dict, tuple)) else False
    except (TypeError, ValueError):
        return False


def parse_numeric(value: Any) -> float | None:
    """First number in a value like 16, "16GB", "1TB" (-> 1000), "₹45,999".
    None when nothing numeric is present (never raises)."""
    if is_missing(value) or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    try:
        number = float(match.group(0).replace(",", ""))
    except ValueError:
        return None
    if re.search(r"\d\s*tb\b", text.lower()):
        number *= 1000
    return number


def json_safe(value: Any) -> Any:
    """NaN/NaT -> None, numpy/pandas scalars -> plain Python."""
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if is_missing(value):
        return None if not isinstance(value, str) else value.strip() or None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return value.item()
        except (AttributeError, ValueError):
            return value
    return value


def clean_record(record: dict) -> dict:
    return {key: json_safe(value) for key, value in record.items()}


def parse_attributes(value: Any) -> dict:
    """The JSON `attributes` column as a dict (never raises)."""
    if isinstance(value, dict):
        return value
    if is_missing(value) or not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def humanize(key: str) -> str:
    """'battery_life' -> 'Battery life', 'ram' -> 'RAM' (short keys are
    usually acronyms)."""
    text = str(key).replace("_", " ").strip()
    if len(text) <= 3 and text.isalpha():
        return text.upper()
    return text[:1].upper() + text[1:]


def format_price(value: Any, currency: str = "INR") -> str:
    number = parse_numeric(value)
    if number is None:
        return "price unavailable"
    if currency.upper() == "INR":
        return f"₹{_indian_grouping(int(round(number)))}"
    return f"{currency} {number:,.0f}"


def _indian_grouping(n: int) -> str:
    sign, digits = ("-", str(-n)) if n < 0 else ("", str(n))
    if len(digits) <= 3:
        return sign + digits
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return sign + ",".join(groups + [tail])
