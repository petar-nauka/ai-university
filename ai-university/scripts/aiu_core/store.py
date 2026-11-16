"""Course file store: JSON read/write, course skeleton, module folders."""
import copy
import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path

SCHEMA_VERSION = "1.0"

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

COURSE_SUBDIRS = ("research/transcripts", "research/extracts", "research/originals", "modules")

DEFAULT_BRIEF = {
    "level": "beginner",
    "prior_knowledge": "",
    "hours_per_week": 5,
    "weeks": 8,
    "days_per_week": 5,
    "session_minutes": 45,
    "language": "bg",
    "source_languages": ["en", "bg"],
    "depth": "standard",
    "approval_mode": "confirm",
    "learning_preference": "mixed",
    "build_mode": "incremental",
    "domain_type": "mixed",
    "topic_velocity": "medium",
    "practice_context": "",
    "constraints": [],
    "assumptions": [],
    "style_notes": [],
    "start_date": None,
}

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
    "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "sht", "ъ": "a", "ь": "y", "ю": "yu", "я": "ya",
}


class StoreError(Exception):
    pass


def slugify(text: str, max_len: int = 60) -> str:
    latin = "".join(_TRANSLIT.get(ch, ch) for ch in text.lower())
    slug = re.sub(r"[^a-z0-9]+", "-", latin).strip("-")
    slug = slug[:max_len].strip("-")
    return slug or "course"


def read_json(path: Path) -> dict:
    """Read a JSON file as UTF-8; a byte-order mark (as Windows PowerShell 5.1 writes) is fine."""
    path = Path(path)
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        raise StoreError(f"Missing file: {path.name} ({path})")
    except UnicodeDecodeError as e:
        raise StoreError(f"{path.name} ({path}) is not UTF-8 text; save it as UTF-8: {e.reason}")
    except json.JSONDecodeError as e:
        raise StoreError(f"Invalid JSON in {path.name} ({path}): {e}")


def write_json(path: Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


LIGHT_COURSE = ("this folder is a light-mode course (course-card.md and no course.json): continue it in "
                "light mode (references/light-mode.md); aiu does not touch it")


def is_light_course(course_dir: Path) -> bool:
    """A course made without the script: the two modes never mix in one folder."""
    return (Path(course_dir) / "course-card.md").is_file() and not (Path(course_dir) / "course.json").exists()


def new_course(root_dir: Path, title: str, brief: dict, slug: str | None = None,
               today: str | None = None) -> tuple[Path, bool]:
    for key in ("topic", "goal"):
        value = brief.get(key)
        if not isinstance(value, str) or not value.strip():
            raise StoreError(f"Brief is missing required field: {key}")
    if slug is None:
        slug = slugify(title)
    elif not SLUG_RE.match(slug):
        raise StoreError(f"Unsafe course slug: {slug!r}")

    course_dir = Path(root_dir) / slug
    if (course_dir / "course.json").exists():
        return course_dir, False
    if is_light_course(course_dir):
        raise StoreError(LIGHT_COURSE)

    for sub in COURSE_SUBDIRS:
        (course_dir / sub).mkdir(parents=True, exist_ok=True)
    merged = copy.deepcopy(DEFAULT_BRIEF)
    merged.update(copy.deepcopy(brief))
    course = {
        "schema_version": SCHEMA_VERSION,
        "course_id": slug,
        "title": title,
        "created_at": today or date.today().isoformat(),
        "brief": merged,
        "capstone": {"title": "", "deliverable": "", "description": "", "hours": 0},
        "modules": [],
        "build": {"checkpoints": [], "finalized_at": None},
    }
    write_json(course_dir / "research" / "benchmarks.json",
               {"schema_version": SCHEMA_VERSION, "sources": [], "note": ""})
    write_json(course_dir / "course.json", course)
    return course_dir, True


def load_course(course_dir: Path) -> dict:
    return read_json(Path(course_dir) / "course.json")


def save_course(course_dir: Path, course: dict) -> None:
    write_json(Path(course_dir) / "course.json", course)


def load_benchmarks(course_dir: Path) -> dict:
    return read_json(Path(course_dir) / "research" / "benchmarks.json")


def save_benchmarks(course_dir: Path, data: dict) -> None:
    write_json(Path(course_dir) / "research" / "benchmarks.json", data)


def find_module(course: dict, module_id: str) -> dict:
    for module in course.get("modules", []):
        if module.get("id") == module_id:
            return module
    raise StoreError(f"Unknown module: {module_id}")


def module_dir(course_dir: Path, course: dict, module_id: str) -> Path:
    return Path(course_dir) / "modules" / find_module(course, module_id)["slug"]


def load_module(course_dir: Path, module_id: str) -> dict:
    course = load_course(course_dir)
    return read_json(module_dir(course_dir, course, module_id) / "module.json")


def save_module(course_dir: Path, module_id: str, data: dict) -> None:
    course = load_course(course_dir)
    write_json(module_dir(course_dir, course, module_id) / "module.json", data)


def empty_module(module_id: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "module_id": module_id,
        "status": "planned",
        "review": None,
        "sources": [],
        "resources": [],
        "practice": [],
        "glossary": [],
        "gaps": [],
    }


def scaffold_modules(course_dir: Path) -> list[str]:
    course = load_course(course_dir)
    created = []
    for module in course["modules"]:
        path = Path(course_dir) / "modules" / module["slug"] / "module.json"
        if path.exists():
            continue
        write_json(path, empty_module(module["id"]))
        created.append(module["slug"])
    return created
