def apply_guardrails(payload: dict, required_keys: list) -> dict:
    for key in required_keys:
        if key not in payload:
            payload[key] = [] if key.endswith("s") else ""
    return payload
