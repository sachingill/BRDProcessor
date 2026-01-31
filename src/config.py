import os
from pathlib import Path

from dotenv import load_dotenv


env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "Return JSON only. No extra text.")
