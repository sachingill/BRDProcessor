import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_PATH = ROOT_DIR / "data" / "org_team_profile.json"


def load_org_team_profile(path: str | None = None) -> dict:
    profile_path = Path(path) if path else DEFAULT_PROFILE_PATH
    if not profile_path.exists():
        raise FileNotFoundError(f"Org/team profile not found: {profile_path}")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict):
        raise ValueError("Org/team profile must be a JSON object.")
    strengths = profile.get("team_strengths")
    if not isinstance(strengths, dict):
        raise ValueError("Org/team profile requires 'team_strengths' object.")
    return profile
