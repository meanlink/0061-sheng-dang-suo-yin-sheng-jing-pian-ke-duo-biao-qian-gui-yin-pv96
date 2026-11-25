"""补正请求体的宽容解析：兼容批量信封、裸数组、单段对象与编号映射。"""
from fastapi import HTTPException

ITEM_LIST_KEYS = (
    "clips", "updates", "items", "corrections", "features", "segments",
    "records", "data", "changes", "batch", "list", "rows",
)
NUMBER_KEYS = ("number", "no", "clip_number", "clip", "segment", "segment_number", "index", "id")
NOTE_KEYS = ("note", "reason", "comment", "summary", "description", "archive_note")
KEY_KEYS = ("request_key", "idempotency_key", "key", "client_token", "request_id")
DIRECT_FIELDS = ("start_s", "end_s", "voices", "movement", "engines", "surf")
FIELD_ALIASES = {
    "start": "start_s", "startSec": "start_s", "start_seconds": "start_s",
    "end": "end_s", "endSec": "end_s", "end_seconds": "end_s",
    "voice": "voices",
    "movement_level": "movement",
    "engine": "engines", "engine_level": "engines",
    "surf_level": "surf", "water": "surf",
}


def _coerce_number(value):
    if isinstance(value, bool):
        raise HTTPException(422, "片刻号必须是整数")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, "片刻号必须是整数") from exc


def _coerce_float(value, field):
    if isinstance(value, bool):
        raise HTTPException(422, f"{field} 必须是 0 到 1 之间的数")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, f"{field} 必须是 0 到 1 之间的数") from exc
    if not 0 <= result <= 1:
        raise HTTPException(422, f"{field} 必须落在 0 到 1")
    return result


def _coerce_int(value, field):
    if isinstance(value, bool):
        raise HTTPException(422, f"{field} 必须是整数秒")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, f"{field} 必须是整数秒") from exc


def _merge_item(raw):
    if not isinstance(raw, dict):
        raise HTTPException(422, "每段补正必须是对象")
    merged = dict(raw)
    for nested_key in ("features", "values", "correction", "fields", "detail"):
        nested = raw.get(nested_key)
        if isinstance(nested, dict):
            for key, value in nested.items():
                merged.setdefault(key, value)
    return merged


def normalize_item(raw, number_override=None):
    raw = _merge_item(raw)
    item = {}

    number = number_override
    if number is None:
        for key in NUMBER_KEYS:
            if raw.get(key) is not None:
                number = _coerce_number(raw[key])
                break
    else:
        number = _coerce_number(number)
    if number is not None:
        if not 1 <= number <= 100:
            raise HTTPException(422, "片刻号范围为 1 到 100")
        item["number"] = number

    for raw_key, value in raw.items():
        target = FIELD_ALIASES.get(raw_key, raw_key)
        if target in DIRECT_FIELDS and value is not None:
            if target in ("start_s",):
                item[target] = _coerce_int(value, target)
                if not 0 <= item[target] <= 3600:
                    raise HTTPException(422, "start_s 范围为 0 到 3600")
            elif target == "end_s":
                item[target] = _coerce_int(value, target)
                if not 1 <= item[target] <= 3600:
                    raise HTTPException(422, "end_s 范围为 1 到 3600")
            else:
                item[target] = _coerce_float(value, target)
    return item


def parse_corrections(payload, number_override=None):
    """返回 (items, request_key, note)。"""
    if payload is None:
        payload = {}

    envelope_note = None
    request_key = None
    if isinstance(payload, dict):
        for key in KEY_KEYS:
            if payload.get(key):
                request_key = str(payload[key])
                break
        for key in NOTE_KEYS:
            if payload.get(key):
                envelope_note = str(payload[key])
                break

    if number_override is not None:
        raw_items = [payload] if isinstance(payload, dict) else list(payload or [])
    elif isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict):
        raw_items = None
        for key in ITEM_LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                raw_items = value
                break
            if isinstance(value, dict):
                # 支持 features/updates 为 {"1": {...}} 的编号映射。
                numeric_keys = [sub for sub in value if str(sub).isdigit()]
                if numeric_keys and all(isinstance(value[sub], dict) for sub in numeric_keys):
                    raw_items = [{"number": int(sub), **value[sub]} for sub in numeric_keys]
                    break
        if raw_items is None:
            # {"1": {...}, "2": {...}} 形式的编号映射
            mapped = []
            numeric_keys = [key for key in payload if str(key).isdigit()]
            if numeric_keys and all(isinstance(payload[key], dict) for key in numeric_keys):
                for key in numeric_keys:
                    mapped.append({"number": int(key), **payload[key]})
                raw_items = mapped
            elif any(key in payload for key in NUMBER_KEYS + DIRECT_FIELDS) or \
                    any(key in payload for key in FIELD_ALIASES):
                raw_items = [payload]
            else:
                raise HTTPException(422, "请提供至少一段补正特征（clips/updates/items）")
    else:
        raise HTTPException(422, "补正请求必须是对象或数组")

    items = [normalize_item(raw, number_override) for raw in raw_items]
    if not items:
        raise HTTPException(422, "补正列表不能为空")
    return items, request_key, envelope_note
