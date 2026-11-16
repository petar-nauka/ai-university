"""Module statuses, checkpoints, next action and finalize.

Statuses only move up through validation gates; the next action is derived from the
files, never from a stored "current phase"."""
import hashlib
from datetime import datetime
from pathlib import Path

from .render import render_course
from .store import (StoreError, empty_module, find_module, load_benchmarks, load_course,
                    load_module, module_dir, save_course, save_module)
from .validate import (REVIEWS, Problem, build_mode, has_errors, syllabus_fingerprint,
                       validate_final, validate_module, validate_syllabus)

MODULE_STATUSES = ["planned", "sourced", "drafted", "verified"]
CHECKPOINTS = ("syllabus", "pilot")
CHECKPOINT_AUTHORS = ("user", "auto")


class StateError(Exception):
    pass


class GateError(Exception):
    def __init__(self, problems: list[Problem], message: str = "Validation failed"):
        super().__init__(message)
        self.problems = problems


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _load_or_empty(course_dir: Path, module_id: str) -> dict:
    """Only a missing module.json counts as planned; an unreadable one raises StoreError."""
    course = load_course(course_dir)
    if not (module_dir(course_dir, course, module_id) / "module.json").exists():
        return empty_module(module_id)
    return load_module(course_dir, module_id)


def _status_of(course_dir: Path, module_id: str) -> str:
    return _load_or_empty(course_dir, module_id).get("status", "planned")


def set_module_status(course_dir: Path, module_id: str, status: str,
                      review: str | None = None) -> tuple[dict, list[Problem]]:
    """Move a module to status; returns (module, warnings of the gate that ran). Going up
    runs that status's gate (GateError on errors); going down runs nothing."""
    if status not in MODULE_STATUSES:
        raise StateError(f"Unknown status {status!r}; use one of {MODULE_STATUSES}")
    course = load_course(course_dir)
    find_module(course, module_id)
    module = _load_or_empty(course_dir, module_id)
    current = module.get("status", "planned")
    if current not in MODULE_STATUSES:
        current = "planned"
    rank, current_rank = MODULE_STATUSES.index(status), MODULE_STATUSES.index(current)
    problems: list[Problem] = []
    if rank < current_rank:
        module["status"], module["review"] = status, None
    elif rank == current_rank and status != "verified":
        return module, []
    else:
        if status == "verified" and review not in REVIEWS:
            raise StateError(f"Status verified needs --review {' or '.join(REVIEWS)}")
        problems = validate_module(course_dir, course, module_id, gate=status)
        if has_errors(problems):
            raise GateError(problems, f"Module {module_id} does not pass the {status} gate")
        module["status"] = status
        module["review"] = review if status == "verified" else None
    save_module(course_dir, module_id, module)
    return module, problems


def record_checkpoint(course_dir: Path, name: str, by: str, note: str = "",
                      now: str | None = None) -> dict:
    if name not in CHECKPOINTS:
        raise StateError(f"Unknown checkpoint {name!r}; use one of {list(CHECKPOINTS)}")
    if by not in CHECKPOINT_AUTHORS:
        raise StateError(f"Unknown approver {by!r}; use one of {list(CHECKPOINT_AUTHORS)}")
    course = load_course(course_dir)
    if name == "syllabus":
        problems = validate_syllabus(course, load_benchmarks(course_dir))
        if has_errors(problems):
            raise GateError(problems, "Syllabus does not pass validation")
        fingerprint = syllabus_fingerprint(course)
    else:
        modules = course.get("modules", [])
        if not modules or _status_of(course_dir, modules[0]["id"]) != "verified":
            raise StateError("The first module must be verified before the pilot checkpoint")
        fingerprint = None
    record = {"name": name, "by": by, "at": now or _now(), "note": note,
              "fingerprint": fingerprint}
    build = course.setdefault("build", {})
    kept = [c for c in build.get("checkpoints", []) if c.get("name") != name]
    build["checkpoints"] = kept + [record]
    save_course(course_dir, course)
    return record


def _action(action: str, detail: str, module_id: str | None = None,
            module_status: str | None = None) -> dict:
    return {"action": action, "module_id": module_id, "module_status": module_status,
            "detail": detail}


def next_action(course_dir: Path) -> dict:
    course = load_course(course_dir)
    modules = course.get("modules", [])
    if not modules:
        bench = load_benchmarks(course_dir)
        if not bench.get("sources") and not str(bench.get("note", "")).strip():
            return _action("research_benchmarks",
                           "Research benchmark programs and register each one with aiu source add "
                           "--target benchmarks, or write in the note of research/benchmarks.json "
                           "why none exist.")
        return _action("design_syllabus",
                       "Design the syllabus (modules and outcomes) in course.json.")
    try:
        benchmarks = load_benchmarks(course_dir)
    except StoreError:
        benchmarks = {}   # validate reports the unreadable file as S5
    errors = sorted({p.code for p in validate_syllabus(course, benchmarks) if p.level == "error"})
    if errors:
        return _action("approve_syllabus",
                       f"The syllabus has errors ({', '.join(errors)}); run aiu validate --stage "
                       "syllabus, fix them, then get the syllabus approved.")
    build = course.get("build") if isinstance(course.get("build"), dict) else {}
    recorded = build.get("checkpoints") if isinstance(build.get("checkpoints"), list) else []
    checkpoints = {c.get("name"): c for c in recorded if isinstance(c, dict)}
    syl = checkpoints.get("syllabus")
    if syl is None:
        return _action("approve_syllabus",
                       "Validate the syllabus and ask the learner to approve it, then record the "
                       "syllabus checkpoint.")
    if syl.get("fingerprint") != syllabus_fingerprint(course):
        return _action("approve_syllabus",
                       "The syllabus was changed after it was approved; validate it and get "
                       "approval again.")
    statuses = {m["id"]: _status_of(course_dir, m["id"]) for m in modules}
    first = modules[0]["id"]
    if statuses[first] == "verified" and "pilot" not in checkpoints:
        return _action("approve_pilot",
                       f"Show the verified pilot module {first} to the learner and record the "
                       "pilot checkpoint.")
    incremental = build_mode(course.get("brief")) == "incremental"
    for i, m in enumerate(modules):
        if incremental and i > 0 and statuses[m["id"]] == "planned":
            return _action("wait_for_learner",
                           f"Module {m['id']} is built when the learner asks for it (\"продължи "
                           "курса\", \"continue the course\"). Stop here: render, report, and tell "
                           "the learner on which study day to ask. When they ask, build it as for "
                           "build_module.", m["id"], "planned")
        if statuses[m["id"]] != "verified":
            return _action("build_module",
                           f"Build module {m['id']} and move it up through the status gates "
                           f"(currently {statuses[m['id']]}).",
                           m["id"], statuses[m["id"]])
    if not build.get("finalized_at"):
        return _action("finalize",
                       "Write the capstone, then run the final validation and assemble the course.")
    if build.get("finalized_digest") != finalized_digest(course_dir, course):
        return _action("finalize",
                       "The course changed since it was finalized (the syllabus, a module's "
                       "module.json, lesson.md, practice.md or answers.md, or capstone.md); run "
                       "the final validation and finalize again.")
    return _action("done", "The course is finalized; nothing is left to do.")


MODULE_FILES = ("module.json", "lesson.md", "practice.md", "answers.md")


def finalized_digest(course_dir: Path, course: dict) -> str:
    """SHA-256 of what a full finalize covers (R18, R18b): the syllabus fingerprint, then per
    module in course order its module.json, lesson.md, practice.md and answers.md, then
    capstone.md; a missing file counts as b"missing"."""
    course_dir = Path(course_dir)
    digest = hashlib.sha256(syllabus_fingerprint(course).encode("ascii"))

    def add(path: Path | None) -> None:
        try:
            digest.update(path.read_bytes() if path is not None else b"missing")
        except OSError:
            digest.update(b"missing")

    modules = course.get("modules") if isinstance(course, dict) else None
    for m in modules if isinstance(modules, list) else []:
        slug = m.get("slug") if isinstance(m, dict) else None
        for name in MODULE_FILES:
            add(course_dir / "modules" / slug / name if isinstance(slug, str) and slug else None)
    add(course_dir / "capstone.md")
    return digest.hexdigest()


def finalize(course_dir: Path, allow_partial: bool = False, now: str | None = None,
             today: str | None = None) -> list[Problem]:
    """Full check, render, then record the finish. A partial run (allow_partial) records
    only build.partial_finalized_at: it never makes the course read as done."""
    problems = validate_final(course_dir, allow_partial)
    if has_errors(problems):
        raise GateError(problems, "Final validation failed")
    render_course(course_dir, today)
    course = load_course(course_dir)
    build = course.setdefault("build", {})
    if allow_partial:
        build["partial_finalized_at"] = now or _now()
    else:
        build["finalized_at"] = now or _now()
        build["finalized_digest"] = finalized_digest(course_dir, course)
    save_course(course_dir, course)
    return problems
