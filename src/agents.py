import json
import re
from pathlib import Path

from openai import OpenAI

from src.config import OPENAI_API_KEY, OPENAI_MODEL, SYSTEM_PROMPT
from src.fallback import (
    eng_plan_fallback,
    schedule_fallback,
    architecture_fallback,
    poc_fallback,
    tech_stack_fallback,
)


def _client():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    if OPENAI_API_KEY in {"YOUR_KEY", "sk-your-key"} or not OPENAI_API_KEY.startswith("sk-"):
        raise RuntimeError("OPENAI_API_KEY looks invalid. Update your .env with a real key.")
    return OpenAI(api_key=OPENAI_API_KEY)


def _load_prompt(path: str) -> str:
    full_path = Path(__file__).resolve().parents[1] / path
    if full_path.exists():
        return full_path.read_text(encoding="utf-8")
    return ""


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _chat(prompt: str, fallback: dict) -> dict:
    try:
        client = _client()
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        content = response.choices[0].message.content or "{}"
        return _extract_json(content)
    except Exception as exc:
        error_payload = {"_error": str(exc)}
        error_payload.update(fallback)
        return error_payload


def eng_plan_generator(brd_sections: dict) -> dict:
    template = _load_prompt("prompts/planning/eng_plan_generator.prompt.md")
    prompt = (
        f"{template}\n\n"
        f"Input BRD sections (JSON): {json.dumps(brd_sections)}"
    )
    return _chat(prompt, eng_plan_fallback())


def schedule_estimator(plan: dict) -> dict:
    template = _load_prompt("prompts/planning/schedule_estimator.prompt.md")
    prompt = (
        f"{template}\n\n"
        f"Input engineering plan JSON: {json.dumps(plan)}"
    )
    return _chat(prompt, schedule_fallback())


def solution_architect(brd_sections: dict) -> dict:
    template = _load_prompt("prompts/design/solution_architect.prompt.md")
    prompt = (
        f"{template}\n\n"
        f"Input BRD sections: {json.dumps(brd_sections)}"
    )
    return _chat(prompt, architecture_fallback())


def poc_planner(architecture: dict) -> dict:
    template = _load_prompt("prompts/design/poc_planner.prompt.md")
    prompt = (
        f"{template}\n\n"
        f"Input architecture JSON: {json.dumps(architecture)}"
    )
    return _chat(prompt, poc_fallback())


def tech_stack_recommender(brd_sections: dict) -> dict:
    template = _load_prompt("prompts/design/tech_stack_recommender.prompt.md")
    prompt = (
        f"{template}\n\n"
        f"Input BRD sections: {json.dumps(brd_sections)}"
    )
    return _chat(prompt, tech_stack_fallback())
