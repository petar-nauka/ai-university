"""Validation rules (spec §9): syllabus (S1-S12w), module (M1-M12), final (F1-F6).

All functions take plain data and never raise on malformed input or files: a
wrong type or an unreadable file simply yields the matching Problem and
checking continues.
"""
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from aiu_core.sources import RELIABILITIES, SOURCE_TYPES
from aiu_core.store import StoreError, load_benchmarks, load_course, read_json
from aiu_core.web import FULL_TEXT_MIN
from aiu_core.youtube import parse_ts

LEVELS = {"beginner", "intermediate", "advanced"}
DEPTHS = {"lite", "standard", "deep"}
APPROVAL_MODES = {"interactive", "auto", "confirm"}
LEARNING_PREFERENCES = {"read", "watch", "listen", "mixed"}
BUILD_MODES = {"incremental", "full"}   # incremental: each module when the learner asks
DOMAIN_TYPES = {"technical", "analytical", "applied", "mixed"}
VELOCITIES = {"fast", "medium", "stable"}
EVIDENCE_TYPES = {"explain", "apply", "analyze", "create"}
ORIGINS = {"benchmark", "ai_designed"}

LANGUAGE_RE = re.compile(r"[a-z]{2,3}(-[A-Za-z0-9]{2,8})?")   # bg, en, bg-BG (fullmatch)
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
REVIEWS = ("self", "independent")
MODULE_ID_RE = re.compile(r"^M\d{2}$")
MODULE_SLUG_RE = re.compile(r"^\d{2}-[a-z0-9]+(-[a-z0-9]+)*$")
OUTCOME_ID_RE = re.compile(r"^M\d{2}-O\d+$")
SOURCE_ID_RE = re.compile(r"^S\d+$")
TASK_ID_RE = re.compile(r"^M\d{2}-P\d+$")
CITATION_RE = re.compile(r"\[(S\d+)(?:\s*@\s*(\d{1,2}:\d{2}(?::\d{2})?))?\]")
CITATION_LIKE_RE = re.compile(r"\[(S\d+)[^\]\n]*\]")   # anything that starts like a citation
WORD_RE = re.compile(r"\w+")

MIN_WORDS = {"lite": 600, "standard": 1200, "deep": 2000}
TARGET_MAX_WORDS = {"lite": 1200, "standard": 2500, "deep": 4000}   # the top of each depth's target
OVER_TARGET = 1.2   # M7w: a lesson this far over the top of its target
# M14w: (video segments, readings) a module is expected to have, by learning preference and depth.
# The preference changes the mix of videos and readings, never the tasks or the recall.
EXPECTED_RESOURCES = {
    "mixed": {"lite": (1, 1), "standard": (2, 3), "deep": (4, 5)},
    "read": {"lite": (0, 2), "standard": (0, 4), "deep": (0, 6)},
    "watch": {"lite": (2, 1), "standard": (3, 1), "deep": (5, 3)},
}
EXPECTED_RESOURCES["listen"] = EXPECTED_RESOURCES["watch"]
CAPSTONE_MIN_WORDS = 150
GATES = ("sourced", "drafted", "verified")
MODULE_STATUSES = ("planned", "sourced", "drafted", "verified")
MODULE_LISTS = ("sources", "resources", "practice", "glossary", "gaps")
ROLES = {"video", "reading", "reference", "tool"}
TRANSCRIPT_KINDS = {"manual", "auto", "none"}
READING_ACCESS = {"full_text", "original_saved", "abstract_only"}
READABLE_ACCESS = READING_ACCESS | {"transcript"}   # anything else: no text was read
CHECKED_LINKS = {"ok", "blocked", "unreachable", "dead"}   # anything else counts as unchecked
TASK_KINDS = {"guided", "independent", "project", "recall"}
GRADED_KINDS = {"guided", "independent", "project"}
SEGMENT_SEC = (60, 2400)        # M4: allowed video segment length
SEGMENT_WARN_SEC = (120, 1500)  # M4w: recommended video segment length
DEFAULT_DAYS_PER_WEEK = 5       # brief.days_per_week when an older brief has none
PLAN_FIT = (0.75, 1.25)         # M13w: plan minutes against the module's hours
DAY_OVERLOAD = 1.5              # M13w: a day longer than this many day lengths


@dataclass(frozen=True)
class Problem:
    level: str  # "error" or "warning"
    code: str   # warning codes end in "w"
    where: str
    message: str


def has_errors(problems: list) -> bool:
    return any(p.level == "error" for p in problems)


def _err(code, where, message):
    return Problem("error", code, where, message)


def _warn(code, where, message):
    return Problem("warning", code, where, message)


def _text(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def _list(v) -> list:
    return v if isinstance(v, list) else []


def _one_of(v, allowed) -> bool:
    return isinstance(v, str) and v in allowed


def _read_text(path) -> str | None:
    """The file as UTF-8 text (a byte-order mark is dropped); None when missing or not UTF-8."""
    if path is None:
        return None
    try:
        return Path(path).read_text(encoding="utf-8-sig")
    except (OSError, ValueError):
        return None


def _course_file(course_dir, rel) -> Path | None:
    """A path stored in JSON (relative, with '/'); None when absent or leaving the course folder."""
    if not _text(rel) or rel.startswith("/") or "\\" in rel or ":" in rel or ".." in rel.split("/"):
        return None
    return Path(course_dir) / rel


def count_words(text: str) -> int:
    """Words of prose: citations such as [S1 @02:33] are not counted."""
    return len(WORD_RE.findall(CITATION_LIKE_RE.sub(" ", text)))


def _iso_date(v) -> bool:
    if not (isinstance(v, str) and ISO_DATE_RE.fullmatch(v)):
        return False
    try:
        date.fromisoformat(v)
    except ValueError:
        return False
    return True


def _check_brief(brief, out):
    if not isinstance(brief, dict):
        out.append(_err("S1", "course", "brief is missing or not an object"))
        brief = {}
    for key in ("topic", "goal", "language"):
        if not _text(brief.get(key)):
            out.append(_err("S1", "course", f"brief.{key} must be a non-empty string"))
    language = brief.get("language")
    if _text(language) and not LANGUAGE_RE.fullmatch(language):
        out.append(_err("S1", "course", f"brief.language must be a language code such as 'bg', "
                                        f"'en' or 'bg-BG', got {language!r}"))
    start = brief.get("start_date")
    if start is not None and not _iso_date(start):
        out.append(_err("S1", "course", f"brief.start_date must be null or a date YYYY-MM-DD, "
                                        f"got {start!r}"))
    hpw = brief.get("hours_per_week")
    if not (_num(hpw) and hpw > 0):
        out.append(_err("S1", "course", "brief.hours_per_week must be a number > 0"))
    weeks = brief.get("weeks")
    if not (_num(weeks) and weeks >= 1):
        out.append(_err("S1", "course", "brief.weeks must be a number >= 1"))
    if "days_per_week" in brief and not _days_per_week_ok(brief["days_per_week"]):
        out.append(_err("S1", "course", "brief.days_per_week must be a whole number from 1 to 7"))
    pref = brief.get("learning_preference", "mixed")
    if not (isinstance(pref, str) and pref in LEARNING_PREFERENCES):
        out.append(_err("S1", "course", f"brief.learning_preference must be one of "
                                        f"{sorted(LEARNING_PREFERENCES)}, got {pref!r}"))
    if "build_mode" in brief and brief["build_mode"] not in BUILD_MODES:
        out.append(_err("S1", "course", f"brief.build_mode must be one of {sorted(BUILD_MODES)}, "
                                        f"got {brief['build_mode']!r}"))
    for key, allowed in (("level", LEVELS), ("depth", DEPTHS),
                         ("approval_mode", APPROVAL_MODES),
                         ("domain_type", DOMAIN_TYPES),
                         ("topic_velocity", VELOCITIES)):
        v = brief.get(key)
        if not (isinstance(v, str) and v in allowed):
            out.append(_err("S1", "course",
                            f"brief.{key} must be one of {sorted(allowed)}, got {v!r}"))
    return brief


def learning_preference(brief) -> str:
    """How the learner prefers to study: read, watch, listen or mixed. A brief without the
    field (made before it existed) or with an unknown value reads as "mixed"."""
    pref = _dict(brief).get("learning_preference")
    return pref if isinstance(pref, str) and pref in LEARNING_PREFERENCES else "mixed"


def expected_resources(depth: str, preference: str) -> tuple[int, int]:
    """(video segments, readings) below which a module gets M14w; an unknown preference reads
    as mixed and an unknown depth as standard."""
    table = EXPECTED_RESOURCES.get(preference, EXPECTED_RESOURCES["mixed"])
    return table.get(depth, table["standard"])


def build_mode(brief) -> str:
    """How the modules get built: "incremental" (after the pilot, each module when the learner
    asks for it) or "full" (all at once). A brief without the field predates building by
    module, so it reads as "full"."""
    mode = _dict(brief).get("build_mode")
    return mode if mode in BUILD_MODES else "full"


def _days_per_week_ok(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 7


def day_minutes(brief) -> float:
    """The length of one study day: the weekly hours spread over brief.days_per_week."""
    brief = _dict(brief)
    dpw = brief.get("days_per_week")
    dpw = dpw if _days_per_week_ok(dpw) else DEFAULT_DAYS_PER_WEEK
    hpw = brief.get("hours_per_week")
    return (float(hpw) if _num(hpw) and hpw > 0 else 5.0) * 60 / dpw


def _check_plan_shape(plan, code, where, out) -> list:
    """A study plan is a non-empty list of days {day: 1, 2, ..., minutes > 0, items: [text]}.
    Returns the days that are well formed."""
    if not isinstance(plan, list) or not plan:
        out.append(_err(code, where, "study_plan must be a non-empty list of days"))
        return []
    good = []
    for i, d in enumerate(plan):
        at = f"{where}:day#{i + 1}"
        if not isinstance(d, dict):
            out.append(_err(code, at, "a day must be an object {day, minutes, items}"))
            continue
        ok = True
        if d.get("day") != i + 1 or isinstance(d.get("day"), bool):
            out.append(_err(code, at, f"day must be {i + 1}: days run 1, 2, 3, ... in order"))
            ok = False
        if not (_num(d.get("minutes")) and d["minutes"] > 0):
            out.append(_err(code, at, "minutes must be a number > 0"))
            ok = False
        items = d.get("items")
        if not (isinstance(items, list) and items and all(_text(x) for x in items)):
            out.append(_err(code, at, "items must be a non-empty list of non-empty strings"))
            ok = False
        if ok:
            good.append(d)
    return good


def _check_capstone(capstone, out):
    if not isinstance(capstone, dict):
        out.append(_err("S2", "course", "capstone is missing or not an object"))
        return 0.0
    for key in ("title", "deliverable"):
        if not _text(capstone.get(key)):
            out.append(_err("S2", "course", f"capstone.{key} must be non-empty"))
    if "study_plan" in capstone:
        _check_plan_shape(capstone["study_plan"], "S11", "capstone", out)
    hours = capstone.get("hours")
    if not (_num(hours) and hours >= 0):
        out.append(_err("S2", "course", "capstone.hours must be a number >= 0"))
        return 0.0
    return float(hours)


def _benchmark_map(benchmarks) -> dict:
    """{id: record} of the registered benchmarks (the first record of an id wins)."""
    found = {}
    for s in _list(_dict(benchmarks).get("sources")):
        if isinstance(s, dict) and isinstance(s.get("id"), str):
            found.setdefault(s["id"], s)
    return found


def cited_benchmarks(course) -> dict:
    """{benchmark id: [outcome ids]} for every outcome with origin benchmark."""
    cited: dict = {}
    for m in _list(_dict(course).get("modules")):
        for o in _list(_dict(m).get("outcomes")):
            o = _dict(o)
            if o.get("origin") != "benchmark":
                continue
            for ref in _list(o.get("benchmark_refs")):
                if isinstance(ref, str):
                    cited.setdefault(ref, []).append(str(o.get("id")))
    return cited


def _check_outcomes(mid, module, bench, out):
    outcomes = module.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        out.append(_err("S4", mid, "module has no outcomes"))
        return []
    if not 3 <= len(outcomes) <= 5:
        out.append(_warn("S4w", mid, f"module has {len(outcomes)} outcomes; 3-5 expected"))
    seen = set()
    kinds = []
    for i, o in enumerate(outcomes):
        if not isinstance(o, dict):
            out.append(_err("S5", f"{mid}-outcome#{i + 1}", "outcome is not an object"))
            continue
        oid = o.get("id")
        where = oid if isinstance(oid, str) and oid else f"{mid}-outcome#{i + 1}"
        if not (isinstance(oid, str) and OUTCOME_ID_RE.match(oid)
                and isinstance(mid, str) and oid.startswith(mid + "-")):
            out.append(_err("S5", where, f"outcome id must match {mid}-O<n>"))
        elif oid in seen:
            out.append(_err("S5", where, "duplicate outcome id"))
        if isinstance(oid, str):
            seen.add(oid)
        if not _text(o.get("statement")):
            out.append(_err("S5", where, "outcome statement must be non-empty"))
        ev = o.get("evidence_type")
        if not (isinstance(ev, str) and ev in EVIDENCE_TYPES):
            out.append(_err("S5", where, f"evidence_type must be one of {sorted(EVIDENCE_TYPES)}"))
        kinds.append(ev)
        origin = o.get("origin")
        if not (isinstance(origin, str) and origin in ORIGINS):
            out.append(_err("S5", where, f"origin must be one of {sorted(ORIGINS)}"))
        elif origin == "benchmark":
            refs = o.get("benchmark_refs")
            if not isinstance(refs, list) or not refs:
                out.append(_err("S5", where, "benchmark outcome needs non-empty benchmark_refs"))
            else:
                for r in refs:
                    if not (isinstance(r, str) and r in bench):
                        out.append(_err("S5", where, f"unknown benchmark ref {r!r}"))
                    elif not _one_of(bench[r].get("access"), READABLE_ACCESS):
                        out.append(_err("S5", where, f"benchmark {r} was never read (access "
                                                     f"{bench[r].get('access')!r}); register its text "
                                                     "with --extract-file or cite another benchmark"))
    return kinds


def _check_short_list(value, key, where, out):
    """S12/S12w: a module's topics and the course's out_of_scope are what the learner reads
    at Checkpoint 1 to judge the plan: a list of short texts, and not an empty one."""
    if value is not None and not (isinstance(value, list) and all(_text(x) for x in value)):
        out.append(_err("S12", where, f"{key} must be a list of non-empty strings"))
    elif not value:
        out.append(_warn("S12w", where, f"{key} is missing; the learner judges the plan by it"))


def validate_syllabus(course: dict, benchmarks: dict) -> list:
    out: list = []
    course = _dict(course)
    brief = _check_brief(course.get("brief"), out)
    capstone_hours = _check_capstone(course.get("capstone"), out)
    _check_short_list(course.get("out_of_scope"), "out_of_scope", "course", out)
    bench = _benchmark_map(benchmarks)

    modules = course.get("modules")
    if not isinstance(modules, list) or not modules:
        out.append(_err("S3", "course", "course needs at least one module"))
        modules = []

    # Pass 1: ids (needed for prerequisite checks) and slug/id uniqueness.
    ids = [m.get("id") if isinstance(m, dict) else None for m in modules]
    order = {mid: i for i, mid in reversed(list(enumerate(ids))) if isinstance(mid, str)}
    seen_ids, seen_slugs = set(), set()
    planned = capstone_hours

    for i, m in enumerate(modules):
        if not isinstance(m, dict):
            out.append(_err("S3", f"module#{i + 1}", "module is not an object"))
            continue
        mid = m.get("id")
        where = mid if isinstance(mid, str) and mid else f"module#{i + 1}"
        if not (isinstance(mid, str) and MODULE_ID_RE.match(mid)):
            out.append(_err("S3", where, "module id must match M<nn>"))
        elif mid in seen_ids:
            out.append(_err("S3", where, "duplicate module id"))
        if isinstance(mid, str):
            seen_ids.add(mid)
        slug = m.get("slug")
        if not (isinstance(slug, str) and MODULE_SLUG_RE.match(slug)):
            out.append(_err("S3", where, "module slug must match <nn>-<ascii-words>"))
        elif slug in seen_slugs:
            out.append(_err("S3", where, "duplicate module slug"))
        if isinstance(slug, str):
            seen_slugs.add(slug)
        if not _text(m.get("title")):
            out.append(_err("S3", where, "module title must be non-empty"))
        hours = m.get("hours")
        if _num(hours) and hours > 0:
            planned += hours
            if not 3 <= hours <= 8:
                out.append(_warn("S9w", where, f"module has {hours} hours; 3-8 expected"))
        else:
            out.append(_err("S3", where, "module hours must be a number > 0"))

        kinds = _check_outcomes(mid if isinstance(mid, str) else where, m, bench, out)
        _check_short_list(m.get("topics"), "topics", where, out)
        if kinds and all(k == "explain" for k in kinds):
            out.append(_warn("S8w", where, "all outcomes are 'explain'; add applied work"))

        prereqs = m.get("prerequisites", [])
        if not isinstance(prereqs, list):
            out.append(_err("S6", where, "prerequisites must be a list"))
            continue
        for p in prereqs:
            if not isinstance(p, str) or p not in order:
                out.append(_err("S6", where, f"unknown prerequisite {p!r}"))
            elif p == mid:
                out.append(_err("S6", where, "module cannot require itself"))
            elif order[p] >= i:
                out.append(_err("S6", where, f"prerequisite {p} must come earlier in the order"))

    hpw, weeks = brief.get("hours_per_week"), brief.get("weeks")
    if _num(hpw) and _num(weeks) and hpw > 0 and weeks >= 1:
        budget = hpw * weeks
        if planned > budget + 1e-9:
            out.append(_err("S7", "course",
                            f"planned {planned:g} h exceeds budget {budget:g} h"))
        elif planned < 0.7 * budget:
            out.append(_warn("S7w", "course",
                             f"planned {planned:g} h is under 70% of budget {budget:g} h"))
    return out


def validate_layout(course_dir: Path, course: dict) -> list[Problem]:
    """S10w: folders in modules/ that belong to no module of course.json."""
    slugs = {m.get("slug") for m in _list(_dict(course).get("modules"))
             if isinstance(m, dict) and isinstance(m.get("slug"), str)}
    try:
        names = sorted(p.name for p in (Path(course_dir) / "modules").iterdir() if p.is_dir())
    except OSError:
        return []
    return [_warn("S10w", name, f"modules/{name} matches no module in course.json; "
                                "remove or rename it") for name in names if name not in slugs]


# --- module stage (M1-M12) -------------------------------------------------
def _load_module(course_dir, course, module_id, out):
    """M1: read module.json; returns (folder, module, outcome ids) or None to stop."""
    cmod = next((m for m in _list(_dict(course).get("modules"))
                 if isinstance(m, dict) and m.get("id") == module_id), None)
    if cmod is None or not _text(cmod.get("slug")):
        out.append(_err("M1", module_id, "module is not in course.json or has no slug"))
        return None
    mdir = Path(course_dir) / "modules" / cmod["slug"]
    try:
        module = read_json(mdir / "module.json")
    except (StoreError, OSError, ValueError) as e:
        out.append(_err("M1", module_id, f"module.json is missing or unreadable: {e}"))
        return None
    if not isinstance(module, dict):
        out.append(_err("M1", module_id, "module.json is not a JSON object"))
        return None
    before = len(out)
    if module.get("module_id") != module_id:
        out.append(_err("M1", module_id,
                        f"module_id {module.get('module_id')!r} does not match {module_id}"))
    if not _one_of(module.get("status"), MODULE_STATUSES):
        out.append(_err("M1", module_id, f"unknown status {module.get('status')!r}"))
    for key in MODULE_LISTS:
        if not isinstance(module.get(key), list):
            out.append(_err("M1", module_id, f"{key} must be a list"))
    if len(out) > before:
        return None
    outcome_ids = [o["id"] for o in _list(cmod.get("outcomes"))
                   if isinstance(o, dict) and isinstance(o.get("id"), str)]
    return mdir, module, outcome_ids


def _http_url(v) -> bool:
    if not isinstance(v, str):
        return False
    try:
        parsed = urlparse(v)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _check_sources(mid, sources, out) -> dict:
    """M6: complete source records; returns {id: source} (the first record wins)."""
    smap = {}
    for i, s in enumerate(sources):
        if not isinstance(s, dict):
            out.append(_err("M6", f"{mid}:source#{i + 1}", "source is not an object"))
            continue
        sid = s.get("id")
        where = f"{mid}:{sid}" if _text(sid) else f"{mid}:source#{i + 1}"
        if not (isinstance(sid, str) and SOURCE_ID_RE.fullmatch(sid)):
            out.append(_err("M6", where, "source id must match S<n>"))
        elif sid in smap:
            out.append(_err("M6", where, "duplicate source id"))
        if isinstance(sid, str):
            smap.setdefault(sid, s)
        for key in ("title", "accessed", "why_selected"):
            if not _text(s.get(key)):
                out.append(_err("M6", where, f"source {key} must be non-empty"))
        if not _http_url(s.get("url")):
            out.append(_err("M6", where, "source url must be an http(s) URL"))
        if not _one_of(s.get("type"), SOURCE_TYPES):
            out.append(_err("M6", where, f"source type must be one of {sorted(SOURCE_TYPES)}"))
        if not _one_of(s.get("reliability"), RELIABILITIES):
            out.append(_err("M6", where, f"reliability must be one of {sorted(RELIABILITIES)}"))
        if s.get("type") != "video":
            continue
        video = s.get("video")
        if not isinstance(video, dict):
            out.append(_err("M6", where, "video source needs a video record"))
            continue
        if not _text(video.get("video_id")):
            out.append(_err("M6", where, "video.video_id must be non-empty"))
        duration = video.get("duration_sec")
        if not (_num(duration) and duration > 0):
            out.append(_err("M6", where, "video.duration_sec must be a number > 0"))
        if not _one_of(video.get("transcript_kind"), TRANSCRIPT_KINDS):
            out.append(_err("M6", where,
                            f"video.transcript_kind must be one of {sorted(TRANSCRIPT_KINDS)}"))
    return smap


def _transcript_cues(course_dir, rel) -> list | None:
    """Cue start times of a cached transcript; None when the file is missing or unreadable."""
    path = _course_file(course_dir, rel)
    if path is None:
        return None
    try:
        transcript = read_json(path)
    except (StoreError, OSError, ValueError):
        return None
    return [c["start_sec"] for c in _list(_dict(transcript).get("cues"))
            if isinstance(c, dict) and _num(c.get("start_sec"))]


def _check_video_resource(course_dir, res, src, where, out):
    """M4: a bounded segment of a transcribed video, framed by a question and a task."""
    for key in ("before_question", "after_task"):
        if not _text(res.get(key)):
            out.append(_err("M4", where, f"video resource needs a non-empty {key}"))
    video = _dict(src.get("video"))
    if src.get("type") != "video" or not _one_of(video.get("transcript_kind"), ("manual", "auto")):
        out.append(_err("M4", where, "role video needs a video source with a transcript; "
                                     "a video without one may only be a reference"))
        return
    locator = _dict(res.get("locator"))
    start, end = locator.get("start_sec"), locator.get("end_sec")
    if not (_num(start) and _num(end)):
        out.append(_err("M4", where, "video resource needs locator {start_sec, end_sec}"))
        return
    duration = video.get("duration_sec")
    if not (_num(duration) and 0 <= start < end <= duration):
        out.append(_err("M4", where, f"segment {start:g}-{end:g} s must satisfy "
                                     f"0 <= start < end <= duration ({duration})"))
        if start >= end:
            return
    length = end - start
    (lo, hi), (warn_lo, warn_hi) = SEGMENT_SEC, SEGMENT_WARN_SEC
    if not lo <= length <= hi:
        out.append(_err("M4", where, f"segment is {length:g} s; {lo}-{hi} s allowed"))
    elif not warn_lo <= length <= warn_hi:
        out.append(_warn("M4w", where, f"segment is {length:g} s; {warn_lo}-{warn_hi} s recommended"))
    cues = _transcript_cues(course_dir, video.get("transcript_path"))
    if cues is None:
        out.append(_err("M4", where, "transcript file is missing or unreadable"))
    elif not any(start <= c < end for c in cues):
        out.append(_err("M4", where, "transcript has no cue inside the segment"))


def _nonempty_file(path) -> bool:
    try:
        return path is not None and path.is_file() and path.stat().st_size > 0
    except (OSError, ValueError):
        return False


def _check_reading(course_dir, where, src, out):
    """M5: a reading has text the author actually read."""
    access = src.get("access")
    if not _one_of(access, READING_ACCESS):
        out.append(_err("M5", where,
                        f"reading needs access in {sorted(READING_ACCESS)}, got {access!r}"))
    elif access == "full_text":
        text = _read_text(_course_file(course_dir, src.get("extract_path")))
        if text is None or len(text) < FULL_TEXT_MIN:
            out.append(_err("M5", where,
                            f"full_text needs an extract file with >= {FULL_TEXT_MIN} characters"))
    elif access == "original_saved":
        if not _nonempty_file(_course_file(course_dir, src.get("original_path"))):
            out.append(_err("M5", where, "original_saved needs the saved original file"))
    else:
        out.append(_warn("M5w", where, "reading has only an abstract"))


def _check_resources(course_dir, mid, module, smap, outcome_ids, out) -> set:
    """M2-M5; returns the outcomes that rest only on a recorded gap."""
    resources = module["resources"]
    covered = {r.get("outcome_id") for r in resources if isinstance(r, dict)
               and isinstance(r.get("outcome_id"), str) and r.get("role") in ("video", "reading")}
    gapped = {g.get("outcome_id") for g in module["gaps"]
              if isinstance(g, dict) and isinstance(g.get("outcome_id"), str)}
    gap_only = set()
    for oid in outcome_ids:
        if oid in covered:
            continue
        if oid in gapped:
            gap_only.add(oid)
            out.append(_warn("M2w", oid, "outcome rests only on a recorded gap (no video or reading)"))
        else:
            out.append(_err("M2", oid, "outcome has no video or reading resource and no gap entry"))

    readings = []
    for i, r in enumerate(resources):
        if not isinstance(r, dict):
            out.append(_err("M3", f"{mid}:resource#{i + 1}", "resource is not an object"))
            continue
        oid, sid, role = r.get("outcome_id"), r.get("source_id"), r.get("role")
        where = (f"{oid}/{sid}" if isinstance(oid, str) and isinstance(sid, str)
                 else f"{mid}:resource#{i + 1}")
        src = smap.get(sid) if isinstance(sid, str) else None
        if oid not in outcome_ids:
            out.append(_err("M3", where, f"unknown outcome_id {oid!r}"))
        if src is None:
            out.append(_err("M3", where, f"unknown source_id {sid!r}"))
        if not _one_of(role, ROLES):
            out.append(_err("M3", where, f"unknown role {role!r}; use one of {sorted(ROLES)}"))
        elif src is None:
            continue
        elif role == "video":
            _check_video_resource(course_dir, r, src, where, out)
        elif role == "reading" and sid not in readings:
            readings.append(sid)
    for sid in readings:
        _check_reading(course_dir, f"{mid}:{sid}", smap[sid], out)
    return gap_only


def _check_lesson(lesson, mid, depth, smap, outcome_ids, gap_only, out) -> list:
    """M7 and M8; returns the source ids the lesson cites."""
    if lesson is None:
        out.append(_err("M7", mid, "lesson.md is missing or is not UTF-8 text"))
        return []
    depth = depth if _one_of(depth, MIN_WORDS) else "standard"
    words, minimum = count_words(lesson), MIN_WORDS[depth]
    if words < minimum:
        out.append(_err("M7", mid, f"lesson.md has {words} words; depth {depth} needs {minimum}"))
    if words > TARGET_MAX_WORDS[depth] * OVER_TARGET:
        out.append(_warn("M7w", mid, f"lesson.md has {words} words, far over the target of at most "
                                     f"{TARGET_MAX_WORDS[depth]} for depth {depth}; cut repetition, add nothing"))
    for m in CITATION_LIKE_RE.finditer(lesson):
        if not CITATION_RE.fullmatch(m.group(0)):
            out.append(_err("M8", f"{mid}:{m.group(1)}",
                            f"malformed citation {m.group(0)}; write [S3] or [S2 @12:30], one source "
                            "per bracket, H:MM:SS past 99 minutes"))
    cited = []
    for m in CITATION_RE.finditer(lesson):
        cite, sid, stamp = m.group(0), m.group(1), m.group(2)
        cited.append(sid)
        where, src = f"{mid}:{sid}", smap.get(sid)
        if src is None:
            out.append(_err("M8", where, f"citation {cite} points to an unknown source"))
            continue
        if not _one_of(src.get("access"), READABLE_ACCESS):
            out.append(_err("M8", where, f"citation {cite} points to a source without read text "
                                         f"(access {src.get('access')!r})"))
        if stamp is not None:
            duration = _dict(src.get("video")).get("duration_sec")
            try:
                sec = parse_ts(stamp)
            except ValueError:
                sec = None
            if sec is None or not (_num(duration) and sec <= duration):
                out.append(_err("M8", where, f"citation {cite}: time is invalid or outside the video"))
    for oid in outcome_ids:
        marker = f"<!-- outcome: {oid} -->"
        pos = lesson.find(marker)
        if pos < 0:
            out.append(_err("M7", mid, f"lesson.md lacks the marker {marker}"))
            continue
        if oid in gap_only:
            continue
        start = pos + len(marker)
        stop = lesson.find("<!-- outcome:", start)
        section = lesson[start:] if stop < 0 else lesson[start:stop]
        if not CITATION_RE.search(section):
            out.append(_err("M8", oid, "the outcome's lesson section cites no source"))
        if "<details" not in section:
            out.append(_warn("M15w", oid, "the outcome's lesson section has no self-check: end it with "
                                          "1-2 questions in <details><summary>...</summary> answer </details>"))
    return cited


def _check_rubric(task, where, out):
    if not _text(task.get("deliverable")):
        out.append(_err("M9", where, "graded task needs a deliverable"))
    criteria = task.get("criteria")
    if not (isinstance(criteria, list) and 3 <= len(criteria) <= 5):
        out.append(_err("M9", where, "graded task needs 3-5 criteria"))
        return
    for c in criteria:
        c = _dict(c)
        if not (_text(c.get("text")) and _num(c.get("points")) and c["points"] >= 1):
            out.append(_err("M9", where, "each criterion needs text and points >= 1"))


def _check_practice(mid, practice, outcome_ids, out):
    """M9: valid tasks (id, kind, title, minutes, outcomes, rubric), a guided task per outcome,
    an independent task; M9w: one project task."""
    seen, guided, kinds = set(), set(), []
    for i, t in enumerate(practice):
        if not isinstance(t, dict):
            out.append(_err("M9", f"{mid}:task#{i + 1}", "task is not an object"))
            continue
        tid, kind = t.get("id"), t.get("kind")
        where = tid if _text(tid) else f"{mid}:task#{i + 1}"
        if not (isinstance(tid, str) and TASK_ID_RE.fullmatch(tid) and tid.startswith(f"{mid}-")):
            out.append(_err("M9", where, f"task id must match {mid}-P<n>"))
        elif tid in seen:
            out.append(_err("M9", where, "duplicate task id"))
        if isinstance(tid, str):
            seen.add(tid)
        if not _one_of(kind, TASK_KINDS):
            out.append(_err("M9", where, f"task kind must be one of {sorted(TASK_KINDS)}"))
        if not _text(t.get("title")):
            out.append(_err("M9", where, "task needs a non-empty title"))
        if not (_num(t.get("minutes")) and t["minutes"] > 0):
            out.append(_err("M9", where, "task needs minutes, a number > 0"))
        oids = t.get("outcome_ids")
        if not isinstance(oids, list):
            out.append(_err("M9", where, "outcome_ids must be a list"))
            oids = []
        elif not oids and kind in ("guided", "independent"):
            out.append(_err("M9", where, f"{kind} task needs at least one outcome"))
        for oid in oids:
            if oid not in outcome_ids:
                out.append(_err("M9", where, f"unknown outcome {oid!r}"))
        if _one_of(kind, GRADED_KINDS):
            _check_rubric(t, where, out)
        if kind == "guided":
            guided.update(o for o in oids if isinstance(o, str))
        kinds.append(kind)
    for oid in outcome_ids:
        if oid not in guided:
            out.append(_err("M9", oid, "outcome has no guided task"))
    if "independent" not in kinds:
        out.append(_err("M9", mid, "module has no independent task"))
    projects = kinds.count("project")
    if projects != 1:
        out.append(_warn("M9w", mid, f"module has {projects} project tasks; 1 expected"))


def _check_markers(mdir, mid, practice, out):
    """M10: every task has its marker in practice.md and answers.md; no answers in practice.md."""
    ids = [t["id"] for t in practice if isinstance(t, dict) and _text(t.get("id"))]
    for name, tag in (("practice.md", "practice"), ("answers.md", "answer")):
        text = _read_text(mdir / name)
        if text is None:
            out.append(_err("M10", mid, f"{name} is missing or is not UTF-8 text"))
            continue
        for tid in ids:
            if f"<!-- {tag}: {tid} -->" not in text:
                out.append(_err("M10", mid, f"{name} lacks the marker <!-- {tag}: {tid} -->"))
        if tag == "practice" and "<!-- answer:" in text:
            out.append(_err("M10", mid, "practice.md contains an answer marker; "
                                        "answers belong in answers.md"))


def _check_glossary(mid, glossary, out):
    """M11: every entry has a term and a definition; M11w: at least 3 entries."""
    for i, g in enumerate(glossary):
        g = _dict(g)
        if not (_text(g.get("term")) and _text(g.get("definition"))):
            out.append(_err("M11", mid, f"glossary entry #{i + 1} needs a term and a definition"))
    if len(glossary) < 3:
        out.append(_warn("M11w", mid, f"glossary has {len(glossary)} entries; at least 3 expected"))


def _check_links(mid, used, smap, gate, out):
    """M12: a used source's link is not dead; unchecked is M12w, and an error at gate verified;
    a link that did not answer (unreachable) is M12w at every gate."""
    for sid in dict.fromkeys(used):
        src = smap.get(sid)
        if src is None:
            continue
        status = _dict(src.get("check")).get("status")
        where = f"{mid}:{sid}"
        if status == "dead":
            out.append(_err("M12", where, "link is dead; replace the source"))
        elif status == "unreachable":
            out.append(_warn("M12w", where, "link did not answer at the last check; open it with "
                                            "your own tool and replace the source if it is gone"))
        elif not _one_of(status, CHECKED_LINKS):
            message = "link has not been checked; run linkcheck"
            out.append(_err("M12", where, message) if gate == "verified"
                       else _warn("M12w", where, message))


def _used_source_ids(course_dir, course, module_id) -> set:
    """Source ids a module uses: its resources and every citation in lesson.md."""
    cmod = next((m for m in _list(_dict(course).get("modules"))
                 if isinstance(m, dict) and m.get("id") == module_id), {})
    slug = cmod.get("slug")
    if not (isinstance(slug, str) and MODULE_SLUG_RE.match(slug)):
        return set()
    mdir = Path(course_dir) / "modules" / slug
    try:
        module = _dict(read_json(mdir / "module.json"))
    except (StoreError, OSError, ValueError):
        module = {}
    used = {r["source_id"] for r in _list(module.get("resources"))
            if isinstance(r, dict) and isinstance(r.get("source_id"), str)}
    used |= {m.group(1) for m in CITATION_LIKE_RE.finditer(_read_text(mdir / "lesson.md") or "")}
    return used


def dead_link_problems(course_dir: Path, dead_sources: list[str]) -> list[Problem]:
    """R22: a dead link found by linkcheck ("<module id>:S<n>" or "benchmarks:B<n>") is an
    M12 error when a resource, a lesson citation or an outcome uses the source; a dead link
    nothing uses blocks nothing and is only M12w."""
    try:
        course = load_course(course_dir)
    except (StoreError, OSError, ValueError):
        course = {}
    cited = cited_benchmarks(course)
    used: dict = {}
    out = []
    for where in dead_sources:
        label, _, sid = where.partition(":")
        if label == "benchmarks":
            outcomes = cited.get(sid)
            if outcomes:
                out.append(_err("M12", where, f"link is dead and outcomes cite this benchmark "
                                              f"({', '.join(outcomes)}); register a live copy and "
                                              "cite it, or change those outcomes (F5 blocks finalize)"))
                continue
        else:
            if label not in used:
                used[label] = _used_source_ids(course_dir, course, label)
            if sid in used[label]:
                out.append(_err("M12", where, "link is dead; replace the source"))
                continue
        out.append(_warn("M12w", where, "link is dead, but nothing uses this source, so it blocks "
                                        "nothing; it is listed in gaps.md"))
    return out


def _check_study_plan(course, module_id, module, out):
    """M13: the day-by-day route schedules every task and every video and reading resource;
    M13w: its minutes stray from the module's hours, or one day is far longer than a day."""
    days = _check_plan_shape(module.get("study_plan"), "M13", module_id, out)
    if not days or len(days) != len(module.get("study_plan")):
        return
    text = "\n".join(x for d in days for x in d["items"])
    for t in module["practice"]:
        tid = _dict(t).get("id")
        if _text(tid) and not re.search(rf"(?<![\w-]){re.escape(tid)}(?![\w-])", text):
            out.append(_err("M13", module_id, f"task {tid} is on no day of the study_plan"))
    for sid in dict.fromkeys(r.get("source_id") for r in module["resources"]
                             if isinstance(r, dict) and r.get("role") in ("video", "reading")):
        if _text(sid) and not re.search(rf"(?<!\w){re.escape(sid)}(?!\w)", text):
            out.append(_err("M13", module_id, f"source {sid} is on no day of the study_plan"))
    brief = _dict(_dict(course).get("brief"))
    hours = next((m.get("hours") for m in _list(_dict(course).get("modules"))
                  if isinstance(m, dict) and m.get("id") == module_id), None)
    total = sum(d["minutes"] for d in days)
    if _num(hours) and hours > 0:
        lo, hi = PLAN_FIT[0] * hours * 60, PLAN_FIT[1] * hours * 60
        if not lo <= total <= hi:
            out.append(_warn("M13w", module_id, f"study_plan has {total:g} min; the module's "
                                                f"{hours:g} h need {lo:g}-{hi:g}"))
    limit = DAY_OVERLOAD * day_minutes(brief)
    for d in days:
        if d["day"] < len(days) and d["minutes"] < day_minutes(brief) / 2:
            out.append(_warn("M13w", f"{module_id}:day#{d['day']}",
                             f"day has {d['minutes']:g} min, under half a study day of about "
                             f"{day_minutes(brief):g} min; join it with the next or add work"))
        if d["minutes"] > limit:
            out.append(_warn("M13w", f"{module_id}:day#{d['day']}",
                             f"day has {d['minutes']:g} min; a study day is about "
                             f"{day_minutes(brief):g} min"))


def _check_depth(module_id, module, depth, preference, out):
    """M14w: fewer video segments or readings than the brief's depth and learning preference
    expect."""
    res = [r for r in module["resources"] if isinstance(r, dict)]
    segments = {(r.get("source_id"), str(r.get("locator"))) for r in res if r.get("role") == "video"}
    readings = {r.get("source_id") for r in res if r.get("role") == "reading"}
    min_segments, min_readings = expected_resources(depth, preference)
    why = f"depth {depth}" + (f" with learning preference {preference}" if preference != "mixed" else "")
    for found, minimum, what in ((len(segments), min_segments, "video segments"),
                                 (len(readings), min_readings, "readings")):
        if minimum and found < minimum:
            out.append(_warn("M14w", module_id, f"module has {found} {what}; {why} "
                                                f"expects at least {minimum}"))


def validate_module(course_dir: Path, course: dict, module_id: str,
                    gate: str = "drafted") -> list[Problem]:
    """Module stage: M1-M6 at gate sourced; M1-M14 at drafted and verified, where an
    unchecked link is an error only at verified. The review field is checked elsewhere."""
    if gate not in GATES:
        raise ValueError(f"unknown gate {gate!r}; use one of {list(GATES)}")
    out: list = []
    loaded = _load_module(course_dir, course, module_id, out)
    if loaded is None:
        return out
    mdir, module, outcome_ids = loaded
    smap = _check_sources(module_id, module["sources"], out)
    gap_only = _check_resources(course_dir, module_id, module, smap, outcome_ids, out)
    if gate != "sourced":
        depth = _dict(_dict(course).get("brief")).get("depth")
        cited = _check_lesson(_read_text(mdir / "lesson.md"), module_id, depth, smap,
                              outcome_ids, gap_only, out)
        _check_practice(module_id, module["practice"], outcome_ids, out)
        _check_markers(mdir, module_id, module["practice"], out)
        _check_glossary(module_id, module["glossary"], out)
        _check_study_plan(course, module_id, module, out)
        _check_depth(module_id, module, depth, learning_preference(_dict(course).get("brief")), out)
        used = [r["source_id"] for r in module["resources"]
                if isinstance(r, dict) and isinstance(r.get("source_id"), str)]
        _check_links(module_id, used + cited, smap, gate, out)
    return list(dict.fromkeys(out))   # the same problem found twice is reported once


# --- syllabus fingerprint and final stage (F1-F6) ---------------------------
def _pick(obj, strings=(), numbers=(), lists=()) -> dict:
    """Copy the named fields of obj; a missing or wrongly typed value becomes None."""
    obj = _dict(obj)
    picked = {k: obj.get(k) if isinstance(obj.get(k), str) else None for k in strings}
    picked.update({k: obj.get(k) if _num(obj.get(k)) else None for k in numbers})
    picked.update({k: obj.get(k) if isinstance(obj.get(k), list) else None for k in lists})
    return picked


def _fingerprint_module(m):
    if not isinstance(m, dict):
        return None
    entry = _pick(m, strings=("id", "title"), numbers=("hours",), lists=("prerequisites",))
    outcomes = m.get("outcomes")
    entry["outcomes"] = ([_pick(o, strings=("id", "statement", "evidence_type", "origin"),
                                lists=("benchmark_refs",))
                          if isinstance(o, dict) else None for o in outcomes]
                         if isinstance(outcomes, list) else None)
    return entry


def syllabus_fingerprint(course: dict) -> str:
    """SHA-256 of the approved syllabus (spec §7.1): the capstone and, per module, its id,
    title, hours, prerequisites and outcomes (with their origin and benchmark_refs, ruling
    R21). Never raises."""
    course = _dict(course)
    modules = course.get("modules")
    data = {"capstone": _pick(course.get("capstone"), strings=("title", "deliverable"),
                              numbers=("hours",)),
            "modules": ([_fingerprint_module(m) for m in modules]
                        if isinstance(modules, list) else None)}
    blob = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8", "surrogatepass")).hexdigest()


def _stored_state(course_dir, cmod):
    """(status, review) in module.json: a missing file counts as planned, an unreadable one
    as (None, None)."""
    if not _text(cmod.get("slug")):
        return None, None
    path = Path(course_dir) / "modules" / cmod["slug"] / "module.json"
    if not path.exists():
        return "planned", None
    try:
        module = read_json(path)
    except (StoreError, OSError, ValueError):
        return None, None
    return (module.get("status"), module.get("review")) if isinstance(module, dict) else (None, None)


def _check_dead_benchmarks(course, benchmarks, out):
    """F5: a benchmark an outcome rests on must not be dead."""
    bench = _benchmark_map(benchmarks)
    for bid, outcomes in cited_benchmarks(course).items():
        if bid in bench and _dict(bench[bid].get("check")).get("status") == "dead":
            out.append(_err("F5", bid, f"benchmark {bid} is dead (cited by {', '.join(outcomes)}); "
                                       "register a live copy and cite it, or change the outcomes, "
                                       "then get the syllabus approved again"))


def validate_final(course_dir: Path, allow_partial: bool = False) -> list[Problem]:
    """Final stage: S rules, S10w, F1-F6 and, per verified module, the M rules at gate verified."""
    course_dir = Path(course_dir)
    try:
        course = load_course(course_dir)
    except (StoreError, OSError, ValueError) as e:
        return [_err("C1", "course", f"course.json is unreadable: {e}")]
    if not isinstance(course, dict):
        return [_err("C1", "course", "course.json is not a JSON object")]
    out: list = []
    try:
        benchmarks = load_benchmarks(course_dir)
    except (StoreError, OSError, ValueError) as e:
        benchmarks = {}
        out.append(_err("S5", "course", f"research/benchmarks.json is unreadable: {e}"))
    out += validate_syllabus(course, benchmarks)
    out += validate_layout(course_dir, course)

    recorded = _list(_dict(course.get("build")).get("checkpoints"))
    checkpoints = {c.get("name"): c for c in recorded
                   if isinstance(c, dict) and isinstance(c.get("name"), str)}
    approval = checkpoints.get("syllabus")
    if approval is None:
        out.append(_err("F1", "course", "no syllabus checkpoint; get the syllabus approved"))
    elif approval.get("fingerprint") != syllabus_fingerprint(course):
        out.append(_err("F1", "course", "the syllabus changed after approval; get it approved again"))
    if "pilot" not in checkpoints:
        out.append(_warn("F4w", "course", "no pilot checkpoint"))
    _check_dead_benchmarks(course, benchmarks, out)

    for cmod in _list(course.get("modules")):
        mid = _dict(cmod).get("id")
        if not isinstance(mid, str):
            continue
        status, review = _stored_state(course_dir, cmod)
        if _one_of(status, ("planned", "sourced", "drafted")):
            make = _warn if allow_partial else _err
            out.append(make("F2", mid, f"module is {status}, not verified"))
            continue
        if status == "verified" and not _one_of(review, REVIEWS):
            out.append(_err("F6", mid, f"module is verified without a review (review {review!r}); "
                                       f"run aiu module set-status --course <dir> {mid} verified "
                                       "--review self|independent"))
        out += validate_module(course_dir, course, mid, gate="verified")   # or M1 if unreadable

    capstone = _read_text(course_dir / "capstone.md")
    if capstone is None:
        out.append(_err("F3", "course", "capstone.md is missing or is not UTF-8 text"))
    elif count_words(capstone) < CAPSTONE_MIN_WORDS:
        out.append(_err("F3", "course", f"capstone.md has {count_words(capstone)} words; "
                                        f"{CAPSTONE_MIN_WORDS} needed"))
    return out
