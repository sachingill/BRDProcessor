import json
import re
from pathlib import Path

from openai import OpenAI

import os

from src.config import OPENAI_API_KEY, OPENAI_MODEL, SYSTEM_PROMPT
from src.fallback import brd_sections_fallback


SECTION_ORDER = [
    "problem",
    "objectives",
    "functional_requirements",
    "non_functional_requirements",
    "constraints",
    "dependencies",
    "assumptions",
]


HEADING_MAP = {
    "problem": ["problem"],
    "objectives": ["objectives", "goals"],
    "functional_requirements": ["functional requirements", "functional requirements:"],
    "non_functional_requirements": ["non-functional requirements", "non functional requirements"],
    "constraints": ["constraints"],
    "dependencies": ["dependencies"],
    "assumptions": ["assumptions"],
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _split_sections(text: str) -> tuple[dict, dict]:
    sections = {key: "" for key in SECTION_ORDER}
    debug = {"markdown_detected": False, "mapped_headings": []}
    markdown_sections, markdown_debug = _split_markdown_sections(text)
    debug.update(markdown_debug)
    if markdown_sections:
        return markdown_sections, debug

    lower = text.lower()
    indices = []
    for key, headings in HEADING_MAP.items():
        for heading in headings:
            match = re.search(rf"\b{re.escape(heading)}\b", lower)
            if match:
                indices.append((match.start(), key))
                break
    indices.sort()
    if not indices:
        return sections, debug

    for i, (start, key) in enumerate(indices):
        end = indices[i + 1][0] if i + 1 < len(indices) else len(text)
        sections[key] = _normalize(text[start:end])
    return sections, debug


def _split_markdown_sections(text: str) -> tuple[dict, dict]:
    sections = {key: "" for key in SECTION_ORDER}
    matches = list(re.finditer(r"^(#{1,6})\s+(.+)$", text, flags=re.MULTILINE))
    if not matches:
        return {}, {"markdown_detected": False, "mapped_headings": []}

    mapped = []
    for match in matches:
        heading = match.group(2).strip().lower()
        for key, headings in HEADING_MAP.items():
            if any(heading == h for h in headings):
                mapped.append((match.start(), match.end(), key))
                break
    if not mapped:
        return {}, {"markdown_detected": True, "mapped_headings": []}

    mapped.sort()
    for i, (start, end_heading, key) in enumerate(mapped):
        end = mapped[i + 1][0] if i + 1 < len(mapped) else len(text)
        sections[key] = _normalize(text[end_heading:end])
    return sections, {"markdown_detected": True, "mapped_headings": [item[2] for item in mapped]}


def parse_brd_text(text: str) -> dict:
    sections, debug = _split_sections(text)
    payload = {
        "schema": "brd_sections_v1",
        "sections": {
            "problem": sections["problem"],
            "objectives": _to_list(sections["objectives"]),
            "functional_requirements": _to_list(sections["functional_requirements"]),
            "non_functional_requirements": _to_list(sections["non_functional_requirements"]),
            "constraints": _to_list(sections["constraints"]),
            "dependencies": _to_list(sections["dependencies"]),
            "assumptions": _to_list(sections["assumptions"]),
        },
        "_llm_fallback_used": False,
        "_debug": debug,
    }
    if _needs_llm_fallback(payload):
        debug["strategy"] = "llm_fallback"
        llm_payload = _llm_parse(text)
        llm_payload["_llm_fallback_used"] = True
        llm_payload["_debug"] = debug
        return llm_payload
    debug["strategy"] = "rule_based"
    if os.getenv("PARSER_DEBUG") == "1":
        print("PARSER_DEBUG:", json.dumps(payload["_debug"]))
    return payload


def _to_list(text: str) -> list:
    if not text:
        return []
    lines = [line.strip("-• ") for line in re.split(r"[•\n]", text)]
    return [line for line in lines if line]


def _needs_llm_fallback(payload: dict) -> bool:
    sections = payload.get("sections", {})
    non_empty = 0
    for key, value in sections.items():
        if isinstance(value, str) and value.strip():
            non_empty += 1
        if isinstance(value, list) and len(value) > 0:
            non_empty += 1
    return non_empty < 2


def _load_prompt() -> str:
    prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "parser" / "brd_parser.prompt.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return (
        "You are a BRD parser.\n\n"
        "Return JSON only with this structure:\n"
        "{\n"
        '  "schema": "brd_sections_v1",\n'
        '  "sections": {\n'
        '    "problem": "",\n'
        '    "objectives": [],\n'
        '    "functional_requirements": [],\n'
        '    "non_functional_requirements": [],\n'
        '    "constraints": [],\n'
        '    "dependencies": [],\n'
        '    "assumptions": []\n'
        "  }\n"
        "}\n"
        "Rules:\n"
        "- Extract concise bullet strings into arrays.\n"
        "- If a section is missing, return an empty array or empty string.\n"
        "- Do not add extra keys."
    )


def _llm_parse(text: str) -> dict:
    if not OPENAI_API_KEY:
        return brd_sections_fallback()
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = f"{_load_prompt()}\n\nInput BRD text:\n{text}"
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    content = response.choices[0].message.content or "{}"
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return brd_sections_fallback()
