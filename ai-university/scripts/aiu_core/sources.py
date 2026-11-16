"""Source registry: the gate through which every source enters a course."""
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from aiu_core import store, web, youtube

SOURCE_TYPES = {"video", "article", "paper", "book", "official_doc", "course",
                "framework", "tool", "dataset", "other"}
RELIABILITIES = {"high", "medium", "low"}
ACCESS_LEVELS = {"full_text", "transcript", "original_saved", "abstract_only",
                 "metadata_only", "unavailable"}

_TRACKING = ("utm_",)
_TRACKING_EXACT = {"fbclid", "gclid"}


class SourceError(Exception):
    pass


def normalize_url(url: str) -> str:
    url = url.strip()
    video_id = youtube.video_id_from_url(url)
    if video_id:
        return youtube.watch_url(video_id)
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith(_TRACKING) and k.lower() not in _TRACKING_EXACT]
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def _container(course_dir: Path, target: str) -> tuple[dict, str, str]:
    """Return (data, id prefix, name used in file names' module part)."""
    if target == "benchmarks":
        return store.load_benchmarks(course_dir), "B", ""
    try:
        store.find_module(store.load_course(course_dir), target)
        return store.load_module(course_dir, target), "S", target
    except store.StoreError as exc:
        raise SourceError(f"unknown target {target!r}: {exc}") from exc


def _next_id(sources: list[dict], prefix: str) -> str:
    nums = [int(s["id"][1:]) for s in sources if str(s.get("id", ""))[1:].isdigit()]
    return f"{prefix}{max(nums, default=0) + 1}"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _read_extract(extract_file: Path) -> str:
    try:
        text = Path(extract_file).read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceError(f"extract file {Path(extract_file).name} is not UTF-8 text; save it as "
                          "UTF-8") from exc
    if len(text) < web.FULL_TEXT_MIN:
        raise SourceError(f"extract is shorter than {web.FULL_TEXT_MIN} characters")
    return text


def _save(course_dir: Path, target: str, data: dict) -> None:
    if target == "benchmarks":
        store.save_benchmarks(course_dir, data)
    else:
        store.save_module(course_dir, target, data)


def _upgrade_with_extract(course_dir: Path, target: str, data: dict, record: dict,
                          module_id: str, title: str | None, extract_file: Path) -> None:
    """R20: text the agent read replaces whatever the script stored for this record."""
    if record.get("video") or record.get("extract_method") == "agent_tool":
        what = "a video" if record.get("video") else "text you supplied before"
        raise SourceError(f"{record.get('id')} is {what}; the extract file was not used and "
                          "nothing changed")
    text = _read_extract(extract_file)
    name = f"{module_id}-{record['id']}" if module_id else record["id"]
    record["access"] = "full_text"
    record["extract_method"] = "agent_tool"
    record["extract_path"] = f"research/extracts/{name}.md"
    if title:
        record["title"] = title
    _write_text(course_dir / record["extract_path"], text)
    _save(course_dir, target, data)


def _transcript_failed(exc: "youtube.TranscriptUnavailable", outcome: str) -> SourceError:
    detail = f": {exc.detail}" if exc.detail else ""
    return SourceError(f"transcript fetch failed ({exc.reason}{detail}); {outcome}; retry later "
                       "or choose another video")


def _set_transcript(record: dict, transcript: dict, language: str | None) -> None:
    video = record["video"]
    record["access"] = "transcript"
    video["transcript_kind"] = transcript["kind"]
    video["transcript_path"] = f"research/transcripts/{video['video_id']}.json"
    record["language"] = language or transcript.get("lang")


def _retry_transcript(course_dir: Path, target: str, data: dict, record: dict,
                      langs: list[str] | None, language: str | None, today: str | None,
                      fetcher) -> bool:
    """R19: a video registered without subtitles gets another try (a cached transcript
    makes it free); on success the record is upgraded in place."""
    video = record["video"]
    try:
        transcript = youtube.load_or_fetch_transcript(
            course_dir, video["video_id"], langs or ["en"], video.get("duration_sec"),
            fetcher=fetcher, today=today)
    except youtube.TranscriptUnavailable as exc:
        if exc.reason == "no_subs":
            return False
        raise _transcript_failed(exc, f"{record.get('id')} is unchanged") from exc
    _set_transcript(record, transcript, language)
    video.pop("transcript_note", None)
    _save(course_dir, target, data)
    return True


def _check_url(norm: str, type_: str) -> None:
    """Minor 14: refuse records that no later command could correct."""
    parts = urlsplit(norm)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise SourceError(f"not an http(s) URL: {norm!r}; give the full address with https://")
    if type_ != "video" and youtube.video_id_from_url(norm):
        raise SourceError("this URL is a YouTube video; register it with --type video")


def add_source(course_dir: Path, target: str, url: str, type_: str, reliability: str,
               why_selected: str, *, title: str | None = None, author: str | None = None,
               published: str | None = None, language: str | None = None, best_use: str = "",
               extract_file: Path | None = None, langs: list[str] | None = None,
               today: str | None = None, fetch_metadata=None, transcript_fetcher=None,
               http_get=None) -> tuple[dict, bool, bool]:
    """Register a source; returns (record, created, upgraded). The same URL again returns
    the existing record, upgraded in place when an extract file is given (R20) or when a
    video without subtitles now has a transcript (R19)."""
    course_dir = Path(course_dir)
    if type_ not in SOURCE_TYPES:
        raise SourceError(f"unknown source type {type_!r}; use one of {', '.join(sorted(SOURCE_TYPES))}")
    if reliability not in RELIABILITIES:
        raise SourceError(f"unknown reliability {reliability!r}; use one of {', '.join(sorted(RELIABILITIES))}")
    if not (why_selected or "").strip():
        raise SourceError("why_selected must not be empty")
    if type_ == "video" and extract_file is not None:
        raise SourceError("extract_file cannot be used with a video source")
    norm = normalize_url(url)
    _check_url(norm, type_)
    data, prefix, module_id = _container(course_dir, target)

    for existing in data["sources"]:
        if existing.get("url") != norm:
            continue
        if extract_file is not None:
            _upgrade_with_extract(course_dir, target, data, existing, module_id,
                                  title, Path(extract_file))
            return existing, False, True
        video = existing.get("video")
        if isinstance(video, dict) and video.get("transcript_kind") == "none":
            return existing, False, _retry_transcript(course_dir, target, data, existing, langs,
                                                      language, today, transcript_fetcher)
        return existing, False, False

    today = today or date.today().isoformat()
    source_id = _next_id(data["sources"], prefix)
    name = f"{module_id}-{source_id}" if module_id else source_id
    record = {"id": source_id, "type": type_, "title": title, "author": author,
              "published": published, "url": norm, "accessed": today, "language": language,
              "access": "unavailable", "reliability": reliability,
              "why_selected": why_selected.strip(), "best_use": best_use, "video": None,
              "extract_path": None, "original_path": None, "extract_method": None,
              "check": {"status": "unchecked", "http": None, "checked_at": None}}
    writes: list[tuple[Path, str | bytes]] = []

    if type_ == "video":
        video_id = youtube.video_id_from_url(norm)
        if not video_id:
            raise SourceError("a video source needs a YouTube URL")
        try:
            meta = (fetch_metadata or youtube.fetch_metadata)(video_id)
        except Exception as exc:
            raise SourceError(f"could not fetch video metadata: {exc}") from exc
        duration = meta.get("duration_sec")
        if not (isinstance(duration, (int, float)) and duration > 0):
            raise SourceError("YouTube gives no duration for this video (a live stream or a "
                              "premiere?); nothing registered")
        record["title"] = title or meta.get("title")
        record["author"] = author or meta.get("channel")
        record["published"] = published or meta.get("published")
        record["video"] = {"video_id": video_id, "duration_sec": duration,
                           "transcript_kind": "none", "transcript_path": None}
        try:
            transcript = youtube.load_or_fetch_transcript(
                course_dir, video_id, langs or ["en"], duration,
                fetcher=transcript_fetcher, today=today)
        except youtube.TranscriptUnavailable as exc:
            if exc.reason not in ("no_subs", "blocked"):   # error, unavailable: try again later
                raise _transcript_failed(exc, "nothing registered") from exc
            # A whole video nobody read: only an extra (role reference), never cited, never
            # minutes. A video YouTube blocks today upgrades itself on a later `source add`.
            record["access"] = "metadata_only"
            if exc.reason == "blocked":
                record["video"]["transcript_note"] = "blocked"
        else:
            _set_transcript(record, transcript, language)
    elif extract_file is not None:
        if not title:
            raise SourceError("title is required when an extract file is given")
        text = _read_extract(extract_file)
        record["access"] = "full_text"
        record["extract_method"] = "agent_tool"
        record["extract_path"] = f"research/extracts/{name}.md"
        writes.append((course_dir / record["extract_path"], text))
    else:
        page = web.fetch_source(norm, http_get=http_get)
        record["title"] = title or page["title"]
        if not record["title"]:
            raise SourceError("no title given and none could be extracted")
        record["access"] = page["access"]
        if page["access"] in ("full_text", "abstract_only"):
            record["extract_method"] = "script"
            record["extract_path"] = f"research/extracts/{name}.md"
            writes.append((course_dir / record["extract_path"], page["text"]))
        elif page["access"] == "original_saved":
            record["original_path"] = f"research/originals/{name}.pdf"
            writes.append((course_dir / record["original_path"], page["pdf_bytes"] or b""))

    if not record["title"]:
        raise SourceError("could not determine a title; pass one explicitly")
    if language and not record["language"]:
        record["language"] = language

    for path, content in writes:
        if isinstance(content, bytes):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        else:
            _write_text(path, content)
    data["sources"].append(record)
    _save(course_dir, target, data)
    return record, True, False


SETTABLE_FIELDS = ("title", "author", "published", "language", "reliability", "why_selected",
                   "best_use")
_NULLABLE_FIELDS = {"author", "published", "language", "best_use"}


def _published_ok(value: str) -> bool:
    """A real calendar date written exactly YYYY-MM-DD."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def set_source_field(course_dir: Path, target: str, source_id: str, field: str,
                     value: str | None) -> tuple[dict, object]:
    """R34: correct one metadata field of a registered source; returns (record, previous value).
    "", "null" or "none", in any letter case, clears an optional field. What the script derived
    from the fetch or the link check (access, check, paths, video, url, id, type, accessed) is never settable."""
    if field not in SETTABLE_FIELDS:
        raise SourceError(f"field {field!r} cannot be set; settable fields: "
                          f"{', '.join(SETTABLE_FIELDS)}. Everything else in a source record is "
                          "written only by aiu source add and aiu linkcheck")
    value = (value or "").strip()
    new = None if value.lower() in ("", "null", "none") else value
    if new is None and field not in _NULLABLE_FIELDS:
        raise SourceError(f"{field} cannot be empty or null")
    if field == "published" and new is not None and not _published_ok(new):
        raise SourceError(f"published must be a date YYYY-MM-DD, or null when the source shows "
                          f"none; got {new!r}")
    if field == "reliability" and new not in RELIABILITIES:
        raise SourceError(f"reliability must be one of {', '.join(sorted(RELIABILITIES))}; "
                          f"got {new!r}")
    data, _, _ = _container(Path(course_dir), target)
    record = next((s for s in data["sources"] if isinstance(s, dict) and s.get("id") == source_id),
                  None)
    if record is None:
        raise SourceError(f"no source {source_id!r} in {target}")
    previous = record.get(field)
    record[field] = new
    _save(Path(course_dir), target, data)
    return record, previous


def _check_sources(sources: list[dict], label: str, today: str, http_get, summary: dict) -> None:
    for src in sources:
        video = src.get("video")
        if video:
            result = web.check_youtube(video["video_id"], http_get=http_get)
        else:
            result = web.check_url(src["url"], http_get=http_get)
        src["check"] = {"status": result["status"], "http": result["http"], "checked_at": today}
        summary["checked"] += 1
        summary[result["status"]] += 1
        if result["status"] == "dead":
            summary["dead_sources"].append(f"{label}:{src['id']}")


def run_linkcheck(course_dir: Path, module_id: str | None = None, *, today: str | None = None,
                  http_get=None) -> dict:
    course_dir = Path(course_dir)
    today = today or date.today().isoformat()
    summary = {"checked": 0, "ok": 0, "blocked": 0, "dead": 0, "unreachable": 0,
               "dead_sources": []}
    if module_id is None:
        benchmarks = store.load_benchmarks(course_dir)
        _check_sources(benchmarks["sources"], "benchmarks", today, http_get, summary)
        store.save_benchmarks(course_dir, benchmarks)
        module_ids = [m["id"] for m in store.load_course(course_dir)["modules"]]
    else:
        try:
            store.find_module(store.load_course(course_dir), module_id)
        except store.StoreError as exc:
            raise SourceError(f"unknown module {module_id!r}: {exc}") from exc
        module_ids = [module_id]
    for mid in module_ids:
        module = store.load_module(course_dir, mid)
        _check_sources(module["sources"], mid, today, http_get, summary)
        store.save_module(course_dir, mid, module)
    return summary
