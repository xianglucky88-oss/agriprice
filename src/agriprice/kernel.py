"""Quote normalisation rules.

A wholesale quote may be published per kilogram first and later corrected
to per ton, and historical batches may be delivered more than once.  This
module turns every raw quote expression into one canonical, comparable
result and records how that result was produced, so re-processing the same
quote never creates a new amount.

``process(record)`` returns a dict with:

* ``value_raw`` / ``unit_raw`` - the original expression, untouched, so the
  source of every result stays traceable.
* ``value_norm``               - the price per canonical unit (``unit_norm``);
  ``None`` when the input cannot be used.
* ``unit_norm``                - the canonical unit, or ``None`` when no
  usable value was produced.
* ``scale_factor``             - the multiplier that turns a raw value into
  the canonical one (``1.0`` when the unit is missing or unknown).
* ``quality``                  - one of ``ok``, ``zero``, ``negative``,
  ``extreme``, ``missing``, ``invalid``; this keeps unusable input distinct
  from genuine zero/negative/extreme quotes.
* ``flags``                    - extra hints such as ``scientific_notation``
  and ``unit_assumed``.
* ``rule``                     - ``RULE_VERSION``, the processing basis.

The function is pure and deterministic: the same input always yields the
same output regardless of arrival order, so a stored result is only ever
rewritten when a changed rule (a new ``RULE_VERSION``) would produce a
different outcome.
"""

import math
import re

RULE_VERSION = "quote-norm-v2"

CANONICAL_UNIT = "ton"

# Multiplier converting a price expressed in a unit into a price per
# canonical unit.  1 ton = 1000 kg = 1e6 g, so a per-kg price is multiplied
# by 1000 to become a per-ton price.
_UNIT_FACTORS = {
    "t": 1.0, "ton": 1.0, "tons": 1.0, "tonne": 1.0, "tonnes": 1.0,
    "吨": 1.0,
    "kg": 1000.0, "kilogram": 1000.0, "kilograms": 1000.0,
    "公斤": 1000.0, "千克": 1000.0,
    "g": 1000000.0, "gram": 1000000.0, "grams": 1000000.0,
    "克": 1000000.0,
}

# |value_norm| at or above this is flagged "extreme"; the value is valid and
# is kept as-is (never silently rescaled).
EXTREME_THRESHOLD = 1e9

_SCI_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)[eE][+-]?\d+$")


def _parse_value(raw):
    """Return (number|None, status, flags) for a raw quote value."""
    if raw is None:
        return None, "missing", []
    if isinstance(raw, bool):
        return None, "invalid", []
    if isinstance(raw, (int, float)):
        number = float(raw)
        if not math.isfinite(number):
            return None, "invalid", []
        return number, "ok", []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None, "missing", []
        try:
            number = float(text)
        except ValueError:
            return None, "invalid", []
        if not math.isfinite(number):
            return None, "invalid", []
        flags = ["scientific_notation"] if _SCI_RE.match(text) else []
        return number, "ok", flags
    return None, "invalid", []


def _unit_factor(raw):
    """Return (factor|None, label|None) for a raw unit unit expression."""
    if raw is None:
        return None, None
    text = str(raw).strip().lower()
    if not text:
        return None, None
    text = text.replace("每", "").replace(" ", "")
    for prefix in ("元/", "¥", "￥", "cny/", "rmb/"):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return _UNIT_FACTORS.get(text), text or None


def process(record):
    if not isinstance(record, dict):
        record = {}
    raw = record.get("value")
    unit_raw = record.get("unit")
    number, status, flags = _parse_value(raw)
    factor, _label = _unit_factor(unit_raw)
    if factor is None:
        factor = 1.0
        flags = flags + ["unit_assumed"]
    result = {
        "value_raw": raw,
        "unit_raw": unit_raw,
        "value_norm": None,
        "unit_norm": None,
        "scale_factor": factor,
        "quality": status,
        "flags": flags,
        "rule": RULE_VERSION,
    }
    if status != "ok":
        return result
    value = round(number * factor, 4)
    if value == 0:
        value = 0.0  # collapse -0.0 so equal quotes hash identically
    result["value_norm"] = value
    result["unit_norm"] = CANONICAL_UNIT
    if value == 0:
        result["quality"] = "zero"
    elif value < 0:
        result["quality"] = "negative"
    elif abs(value) >= EXTREME_THRESHOLD:
        result["quality"] = "extreme"
    return result
