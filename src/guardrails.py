import json
from pathlib import Path

from jsonschema import ValidationError, validate


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def apply_guardrails(payload: dict, required_keys: list) -> dict:
    for key in required_keys:
        if key not in payload:
            payload[key] = [] if key.endswith("s") else ""
    return payload


def load_schema(name: str) -> dict:
    schema_path = SCHEMA_DIR / name
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_schema(payload: dict, schema_name: str) -> None:
    validate(instance=payload, schema=load_schema(schema_name))


def validate_artifact(payload: dict, schema_name: str, stage: str) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"{stage} returned non-dict payload.")
    if payload.get("_error"):
        raise ValueError(f"{stage} returned error payload: {payload['_error']}")
    try:
        validate_schema(payload, schema_name)
    except ValidationError as exc:
        message = str(exc).splitlines()[0]
        raise ValueError(f"{stage} schema validation failed: {message}") from exc
