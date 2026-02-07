import json
import os
import time
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from src.agents import (
    eng_plan_generator,
    schedule_estimator,
    solution_architect,
    poc_planner,
    tech_stack_recommender,
)
from src.guardrails import validate_artifact, validate_schema
from src.org_team_profile import load_org_team_profile


ARTIFACT_SCHEMAS = {
    "engineering_plan": "engineering_plan.schema.json",
    "schedule_estimate": "schedule_estimate.schema.json",
    "solution_architecture": "solution_architecture.schema.json",
    "poc_plan": "poc_plan.schema.json",
    "tech_stack_recommendations": "tech_stack.schema.json",
}

STAGE_ORDER = [
    "engineering_plan",
    "schedule_estimate",
    "solution_architecture",
    "poc_plan",
    "tech_stack_recommendations",
]

ROOT_DIR = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT_DIR / ".runtime"
DEFAULT_LOCK_PATH = RUNTIME_DIR / "pipeline.lock"
DEFAULT_CHECKPOINT_DIR = RUNTIME_DIR / "checkpoints"

STAGE_INPUTS = {
    "engineering_plan": lambda state, brd_sections, _org_team_profile: brd_sections,
    "schedule_estimate": lambda state, brd_sections, _org_team_profile: state["engineering_plan"]["payload"],
    "solution_architecture": lambda state, brd_sections, _org_team_profile: brd_sections,
    "poc_plan": lambda state, brd_sections, _org_team_profile: state["solution_architecture"]["payload"],
    "tech_stack_recommendations": lambda state, brd_sections, org_team_profile: {
        "brd_sections": brd_sections,
        "org_team_profile": org_team_profile,
    },
}

STAGE_FUNCTION_NAMES = {
    "engineering_plan": "eng_plan_generator",
    "schedule_estimate": "schedule_estimator",
    "solution_architecture": "solution_architect",
    "poc_plan": "poc_planner",
    "tech_stack_recommendations": "tech_stack_recommender",
}


class PipelineExecutionError(RuntimeError):
    def __init__(self, run_id: str, stage: str, attempts: int, detail: str):
        super().__init__(f"run_id={run_id} stage={stage} attempts={attempts} detail={detail}")
        self.run_id = run_id
        self.stage = stage
        self.attempts = attempts
        self.detail = detail


class LockAcquisitionError(RuntimeError):
    pass


class StageExecutionError(RuntimeError):
    def __init__(self, stage: str, attempts: int, detail: str):
        super().__init__(detail)
        self.stage = stage
        self.attempts = attempts
        self.detail = detail


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _brd_fingerprint(brd_sections: dict) -> str:
    serialized = json.dumps(brd_sections, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def _checkpoint_file(checkpoint_dir: Path, run_id: str) -> Path:
    return checkpoint_dir / f"{run_id}.json"


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


def _load_checkpoint(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@contextmanager
def _run_lock(lock_path: Path, run_id: str, timeout_seconds: float, poll_seconds: float):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    fd = None
    lock_payload = {"run_id": run_id, "pid": os.getpid(), "started_at_utc": _utc_timestamp()}
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, json.dumps(lock_payload).encode("utf-8"))
            break
        except FileExistsError:
            if time.monotonic() - start >= timeout_seconds:
                raise LockAcquisitionError(
                    f"Timeout acquiring pipeline lock at {lock_path} after {timeout_seconds:.1f}s."
                )
            time.sleep(poll_seconds)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(lock_path)
        except FileNotFoundError:
            pass


def _run_stage(stage: str, fn, payload: dict, schema_name: str, max_attempts: int, retry_delay_seconds: float):
    attempt = 0
    errors = []
    raw = None
    total_seconds = 0.0
    while attempt < max_attempts:
        attempt += 1
        start = time.perf_counter()
        raw = fn(payload)
        total_seconds += time.perf_counter() - start
        try:
            validate_artifact(raw, schema_name, stage)
            return raw, raw, round(total_seconds, 3), attempt
        except Exception as exc:
            errors.append(str(exc))
            if attempt < max_attempts and retry_delay_seconds > 0:
                time.sleep(retry_delay_seconds)
    raise StageExecutionError(stage, attempt, " | ".join(errors))


def _stage_fn(stage: str):
    if stage == "tech_stack_recommendations":
        return lambda payload: tech_stack_recommender(payload["brd_sections"], payload["org_team_profile"])
    return globals()[STAGE_FUNCTION_NAMES[stage]]


def _resolve_stage_from_checkpoint(stage: str, checkpoint: dict) -> dict | None:
    stage_entry = checkpoint.get("stages", {}).get(stage)
    if not isinstance(stage_entry, dict):
        return None
    payload = stage_entry.get("payload")
    raw = stage_entry.get("raw", payload)
    if not isinstance(payload, dict):
        raise ValueError(f"Checkpoint stage '{stage}' payload is invalid.")
    validate_artifact(payload, ARTIFACT_SCHEMAS[stage], stage)
    return {
        "payload": payload,
        "raw": raw if isinstance(raw, dict) else payload,
        "timing_seconds": float(stage_entry.get("timing_seconds", 0.0)),
        "attempts": int(stage_entry.get("attempts", 1)),
    }


def _build_result(
    brd_sections: dict,
    org_team_profile: dict,
    state: dict,
    run_id: str,
    started_at_utc: str,
    max_attempts: int,
    retry_delay_seconds: float,
) -> dict:
    completed_at_utc = _utc_timestamp()
    timings = {
        "engineering_plan_seconds": round(float(state["engineering_plan"]["timing_seconds"]), 3),
        "schedule_estimate_seconds": round(float(state["schedule_estimate"]["timing_seconds"]), 3),
        "solution_architecture_seconds": round(float(state["solution_architecture"]["timing_seconds"]), 3),
        "poc_plan_seconds": round(float(state["poc_plan"]["timing_seconds"]), 3),
        "tech_stack_seconds": round(float(state["tech_stack_recommendations"]["timing_seconds"]), 3),
    }
    attempts = {stage: int(state[stage]["attempts"]) for stage in STAGE_ORDER}
    return {
        "brd_sections": brd_sections,
        "engineering_plan": state["engineering_plan"]["payload"],
        "schedule_estimate": state["schedule_estimate"]["payload"],
        "solution_architecture": state["solution_architecture"]["payload"],
        "poc_plan": state["poc_plan"]["payload"],
        "tech_stack_recommendations": state["tech_stack_recommendations"]["payload"],
        "_debug": {
            "engineering_plan_raw": state["engineering_plan"]["raw"],
            "schedule_estimate_raw": state["schedule_estimate"]["raw"],
            "solution_architecture_raw": state["solution_architecture"]["raw"],
            "poc_plan_raw": state["poc_plan"]["raw"],
            "tech_stack_recommendations_raw": state["tech_stack_recommendations"]["raw"],
            "timings": timings,
            "attempts": attempts,
            "org_team_profile": org_team_profile,
            "run": {
                "run_id": run_id,
                "status": "success",
                "started_at_utc": started_at_utc,
                "completed_at_utc": completed_at_utc,
                "max_attempts": max_attempts,
                "retry_delay_seconds": retry_delay_seconds,
            },
        },
    }


def run_pipeline(
    brd_sections: dict,
    run_id: str | None = None,
    max_attempts: int = 2,
    retry_delay_seconds: float = 0.0,
    lock_path: str | None = None,
    checkpoint_dir: str | None = None,
    lock_timeout_seconds: float = 30.0,
    lock_poll_seconds: float = 0.1,
    enable_lock: bool = True,
    resume_from_checkpoint: bool = True,
    org_team_profile_path: str | None = None,
) -> dict:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1.")
    validate_schema(brd_sections, "brd_sections.schema.json")

    resolved_run_id = run_id or str(uuid4())
    org_team_profile = load_org_team_profile(org_team_profile_path)
    lock_path_obj = Path(lock_path) if lock_path else DEFAULT_LOCK_PATH
    checkpoint_dir_obj = Path(checkpoint_dir) if checkpoint_dir else DEFAULT_CHECKPOINT_DIR
    checkpoint_path = _checkpoint_file(checkpoint_dir_obj, resolved_run_id)

    context = (
        _run_lock(lock_path_obj, resolved_run_id, lock_timeout_seconds, lock_poll_seconds)
        if enable_lock
        else nullcontext()
    )

    try:
        with context:
            checkpoint = _load_checkpoint(checkpoint_path) if resume_from_checkpoint else None
            brd_hash = _brd_fingerprint(brd_sections)
            org_profile_hash = _brd_fingerprint(org_team_profile)
            started_at_utc = _utc_timestamp()
            state = {}

            if checkpoint:
                if checkpoint.get("run_id") != resolved_run_id:
                    raise PipelineExecutionError(resolved_run_id, "checkpoint", 1, "Checkpoint run_id mismatch.")
                if checkpoint.get("brd_fingerprint") != brd_hash:
                    raise PipelineExecutionError(
                        resolved_run_id,
                        "checkpoint",
                        1,
                        "Checkpoint BRD fingerprint mismatch for run_id.",
                    )
                if checkpoint.get("org_profile_fingerprint") != org_profile_hash:
                    raise PipelineExecutionError(
                        resolved_run_id,
                        "checkpoint",
                        1,
                        "Checkpoint org/team profile fingerprint mismatch for run_id.",
                    )
                started_at_utc = checkpoint.get("started_at_utc", started_at_utc)
                for stage in STAGE_ORDER:
                    cached = _resolve_stage_from_checkpoint(stage, checkpoint)
                    if cached:
                        state[stage] = cached

            checkpoint_payload = {
                "run_id": resolved_run_id,
                "status": "running",
                "started_at_utc": started_at_utc,
                "updated_at_utc": _utc_timestamp(),
                "brd_fingerprint": brd_hash,
                "org_profile_fingerprint": org_profile_hash,
                "max_attempts": max_attempts,
                "retry_delay_seconds": retry_delay_seconds,
                "stages": {
                    stage: {
                        "attempts": int(stage_data["attempts"]),
                        "timing_seconds": round(float(stage_data["timing_seconds"]), 3),
                        "payload": stage_data["payload"],
                        "raw": stage_data["raw"],
                    }
                    for stage, stage_data in state.items()
                },
            }
            _write_json_atomic(checkpoint_path, checkpoint_payload)

            try:
                for stage in STAGE_ORDER:
                    if stage in state:
                        continue
                    payload = STAGE_INPUTS[stage](state, brd_sections, org_team_profile)
                    output, raw, seconds, attempts = _run_stage(
                        stage,
                        _stage_fn(stage),
                        payload,
                        ARTIFACT_SCHEMAS[stage],
                        max_attempts,
                        retry_delay_seconds,
                    )
                    state[stage] = {
                        "payload": output,
                        "raw": raw,
                        "timing_seconds": seconds,
                        "attempts": attempts,
                    }
                    checkpoint_payload["updated_at_utc"] = _utc_timestamp()
                    checkpoint_payload["stages"][stage] = {
                        "attempts": attempts,
                        "timing_seconds": seconds,
                        "payload": output,
                        "raw": raw,
                    }
                    _write_json_atomic(checkpoint_path, checkpoint_payload)
            except StageExecutionError as exc:
                checkpoint_payload["status"] = "failed"
                checkpoint_payload["failed_stage"] = exc.stage
                checkpoint_payload["failed_attempts"] = exc.attempts
                checkpoint_payload["failure_detail"] = exc.detail
                checkpoint_payload["updated_at_utc"] = _utc_timestamp()
                _write_json_atomic(checkpoint_path, checkpoint_payload)
                raise PipelineExecutionError(resolved_run_id, exc.stage, exc.attempts, exc.detail) from exc
            except Exception as exc:
                checkpoint_payload["status"] = "failed"
                checkpoint_payload["failed_stage"] = "checkpoint"
                checkpoint_payload["failed_attempts"] = 1
                checkpoint_payload["failure_detail"] = str(exc)
                checkpoint_payload["updated_at_utc"] = _utc_timestamp()
                _write_json_atomic(checkpoint_path, checkpoint_payload)
                raise PipelineExecutionError(resolved_run_id, "checkpoint", 1, str(exc)) from exc

            result = _build_result(
                brd_sections,
                org_team_profile,
                state,
                resolved_run_id,
                started_at_utc,
                max_attempts,
                retry_delay_seconds,
            )
            checkpoint_payload["status"] = "success"
            checkpoint_payload["completed_at_utc"] = result["_debug"]["run"]["completed_at_utc"]
            checkpoint_payload["updated_at_utc"] = _utc_timestamp()
            _write_json_atomic(checkpoint_path, checkpoint_payload)
            return result
    except LockAcquisitionError as exc:
        raise PipelineExecutionError(resolved_run_id, "lock", 1, str(exc)) from exc
