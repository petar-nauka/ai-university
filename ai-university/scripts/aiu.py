"""aiu - the command line of the course generator.

Every well-formed command prints exactly one JSON object on stdout:
{"ok", "command", "data", "warnings", "errors"}; each warning and error is
{"code", "where", "message"}. Exit code 0 = success, 1 = a rule failed or a status was
refused, 2 = usage or environment problem. The rules live in aiu_core; this file only
parses arguments, calls aiu_core and maps results and exceptions to the envelope.
Set AIU_DEBUG=1 to get the traceback of a failure on stderr."""
import argparse
import importlib.metadata
import json
import os
import platform
import sys
import tempfile
import traceback
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # python -I leaves this folder off the path
from aiu_core import pagecheck, render, sources, state, store, validate, web, youtube  # noqa: E402
from aiu_core.validate import Problem

PACKAGES = ("requests", "beautifulsoup4", "yt-dlp", "youtube-transcript-api")
PROBE_VIDEO = "jrHRe9lSqqA"
STAGES = ("syllabus", "module", "final")
USAGE_ERRORS = (store.StoreError, sources.SourceError, state.StateError, render.RenderError,
                ValueError)


class CliError(Exception):
    """A problem with the command line or the files it names; reported with exit code 2."""

    def __init__(self, code: str, where: str, message: str):
        super().__init__(message)
        self.problem = Problem("error", code, where, message)


def emit(command: str, ok: bool, data: dict, warnings: list, errors: list) -> None:
    envelope = {"ok": ok, "command": command, "data": data, "warnings": warnings, "errors": errors}
    sys.stdout.write(json.dumps(envelope, ensure_ascii=False) + "\n")


# --- helpers ------------------------------------------------------------------------------

def _load_course(course_dir: Path) -> dict:
    """course.json, or C1 (exit 2) when it cannot be read as a JSON object; a light-mode
    course folder is a usage error, because aiu never touches one."""
    if store.is_light_course(course_dir):
        raise CliError("E_USAGE", "course", store.LIGHT_COURSE)
    try:
        course = store.load_course(course_dir)
    except (store.StoreError, OSError, ValueError) as exc:
        raise CliError("C1", "course", f"course.json is unreadable: {exc}") from exc
    if not isinstance(course, dict):
        raise CliError("C1", "course", "course.json is not a JSON object")
    return course


def _split(text: str, option: str) -> list[str]:
    items = [item.strip() for item in text.split(",") if item.strip()]
    if not items:
        raise CliError("E_USAGE", option, f"{option} needs at least one comma-separated value")
    return items


def _langs(args, course: dict) -> list[str]:
    """--langs, else the brief's source_languages, else English."""
    if args.langs is not None:
        return _split(args.langs, "--langs")
    brief = course.get("brief")
    langs = brief.get("source_languages") if isinstance(brief, dict) else None
    if isinstance(langs, list) and langs and all(isinstance(x, str) and x.strip() for x in langs):
        return langs
    return ["en"]


def _video_id(text: str) -> str:
    video_id = youtube.video_id_from_url(text)
    if video_id is None:
        raise CliError("E_USAGE", "VIDEO", f"not a YouTube video id or URL: {text!r}")
    return video_id


def _module_state(course_dir: Path, module: dict) -> tuple:
    """(status, review) of a course.json module record; a missing module.json is a planned
    module, and a record without a valid slug has no folder to read: (None, None)."""
    slug = module.get("slug")
    if not (isinstance(slug, str) and validate.MODULE_SLUG_RE.match(slug)):
        return None, None
    path = Path(course_dir) / "modules" / slug / "module.json"
    data = store.read_json(path) if path.exists() else store.empty_module(module.get("id"))
    if not isinstance(data, dict):
        return None, None
    return data.get("status", "planned"), data.get("review")


def _can_write(folder: Path) -> bool:
    try:
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=".aiu-doctor-")
        os.write(fd, b"ok")
        os.close(fd)
        os.unlink(tmp)
        return True
    except OSError:
        return False


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        value = 0
    if value < 1:
        raise argparse.ArgumentTypeError(f"expected a whole number >= 1, got {text!r}")
    return value


# --- commands: each returns (data, problems) ----------------------------------------------

def cmd_doctor(args):
    problems = []
    packages = {}
    for name in PACKAGES:
        try:
            packages[name] = {"installed": True, "version": importlib.metadata.version(name)}
        except importlib.metadata.PackageNotFoundError:
            packages[name] = {"installed": False, "version": None}
            problems.append(Problem("error", "E_ENV", name, f"package {name} is not installed"))
    python_ok = sys.version_info >= (3, 10)
    if not python_ok:
        problems.append(Problem("error", "E_ENV", "python", "Python 3.10 or newer is needed"))
    write_access = _can_write(Path.cwd())
    if not write_access:
        problems.append(Problem("error", "E_ENV", "cwd", "cannot write to the current folder"))
    online = None
    if args.online:   # no network at all means light mode; a refusing YouTube does not
        online = {"web": web.check_web(),
                  "youtube": web.check_youtube(PROBE_VIDEO) if packages["requests"]["installed"] else None}
    return {"python": platform.python_version(), "python_ok": python_ok, "packages": packages,
            "write_access": write_access, "online": online}, problems


def cmd_init(args):
    brief = store.read_json(args.brief)
    if not isinstance(brief, dict):
        raise CliError("E_USAGE", "--brief", "the brief file must hold a JSON object")
    course_dir, created = store.new_course(args.root, args.title, brief, slug=args.slug)
    course = _load_course(course_dir)
    return {"course_dir": course_dir.as_posix(), "course_id": course.get("course_id"),
            "title": course.get("title"), "created": created}, []


def cmd_status(args):
    course = _load_course(args.course)
    next_action = state.next_action(args.course)
    modules = []
    records = course.get("modules")
    for m in records if isinstance(records, list) else []:
        if not isinstance(m, dict):
            continue
        status, review = _module_state(args.course, m)
        modules.append({"id": m.get("id"), "slug": m.get("slug"), "title": m.get("title"),
                        "status": status, "review": review})
    build = course.get("build") if isinstance(course.get("build"), dict) else {}
    return {"course_dir": args.course.as_posix(), "title": course.get("title"), "modules": modules,
            "checkpoints": build.get("checkpoints", []), "finalized_at": build.get("finalized_at"),
            "partial_finalized_at": build.get("partial_finalized_at"), "next": next_action}, []


def cmd_scaffold(args):
    course = _load_course(args.course)
    # Module slugs become folder names: refuse while any S3 error stands. Benchmarks only
    # matter for S5, so none are loaded here.
    unsafe = [p for p in validate.validate_syllabus(course, {}) if p.code == "S3"]
    if unsafe:
        return {"created": []}, unsafe
    return {"created": store.scaffold_modules(args.course)}, []


def cmd_validate(args):
    course = _load_course(args.course)
    if args.stage == "syllabus":
        problems = validate.validate_syllabus(course, store.load_benchmarks(args.course))
        problems += validate.validate_layout(args.course, course)
    elif args.stage == "module":
        if not args.module:
            raise CliError("E_USAGE", "--module", "--stage module needs --module ID")
        problems = validate.validate_module(args.course, course, args.module, gate=args.gate)
    else:
        problems = validate.validate_final(args.course, allow_partial=args.allow_partial)
    errors = sum(1 for p in problems if p.level == "error")
    return {"stage": args.stage, "errors": errors, "warnings": len(problems) - errors}, problems


def cmd_render(args):
    _load_course(args.course)
    return {"rendered": render.render_course(args.course)}, []


def cmd_checkpoint(args):
    _load_course(args.course)
    return {"checkpoint": state.record_checkpoint(args.course, args.name, args.by, args.note)}, []


def cmd_set_status(args):
    _load_course(args.course)
    module, warnings = state.set_module_status(args.course, args.module_id, args.status, args.review)
    return {"module_id": args.module_id, "status": module.get("status"),
            "review": module.get("review")}, warnings


def cmd_finalize(args):
    _load_course(args.course)
    warnings = state.finalize(args.course, allow_partial=args.allow_partial)
    # finalize has rendered the pages but does not return their list; rendering again
    # writes the same files and gives the list.
    rendered = render.render_course(args.course)
    build = _load_course(args.course).get("build") or {}
    return {"rendered": rendered, "partial": args.allow_partial,
            "finalized_at": build.get("finalized_at"),
            "partial_finalized_at": build.get("partial_finalized_at")}, warnings


def cmd_source_add(args):
    course = _load_course(args.course)
    if args.extract_file is not None and not args.extract_file.is_file():
        raise CliError("E_USAGE", "--extract-file", f"extract file not found: {args.extract_file}")
    record, created, upgraded = sources.add_source(
        args.course, args.target, args.url, args.type, args.reliability, args.why,
        title=args.title, author=args.author, published=args.published, language=args.language,
        best_use=args.best_use, extract_file=args.extract_file, langs=_langs(args, course))
    return {"source": record, "created": created, "upgraded": upgraded}, []


def cmd_source_set(args):
    _load_course(args.course)
    record, previous = sources.set_source_field(args.course, args.target, args.id, args.field,
                                                args.value)
    return {"source": record, "field": args.field, "previous": previous,
            "changed": previous != record.get(args.field)}, []


def cmd_linkcheck(args):
    _load_course(args.course)
    summary = sources.run_linkcheck(args.course, args.module)
    return summary, validate.dead_link_problems(args.course, summary["dead_sources"])


def cmd_yt_search(args):
    results = youtube.search(args.query, max_results=args.max,
                             min_seconds=args.min_minutes * 60, max_seconds=args.max_minutes * 60)
    return {"results": results}, []


def cmd_yt_transcript(args):
    course = _load_course(args.course)
    video_id = _video_id(args.video)
    langs = _langs(args, course)
    try:
        meta = youtube.fetch_metadata(video_id)
    except Exception as exc:  # noqa: BLE001 - any failure here means no usable video
        raise CliError("E_TRANSCRIPT", video_id, f"could not fetch video metadata: {exc}") from exc
    transcript = youtube.load_or_fetch_transcript(args.course, video_id, langs,
                                                  meta.get("duration_sec") or None)
    return {"video_id": video_id, "lang": transcript.get("lang"), "kind": transcript.get("kind"),
            "duration_sec": transcript.get("duration_sec"), "cues": len(transcript.get("cues", [])),
            "title": meta.get("title"), "channel": meta.get("channel"),
            "published": meta.get("published"),
            "path": f"research/transcripts/{video_id}.json"}, []


def cmd_yt_find(args):
    course = _load_course(args.course)
    video_id = _video_id(args.video)
    terms = _split(args.terms, "--terms")
    transcript = youtube.load_or_fetch_transcript(args.course, video_id, _langs(args, course))
    windows = youtube.find_windows(transcript, terms, window_sec=args.window, top=args.top)
    for w in windows:
        w["start"], w["end"] = youtube.format_ts(w["start_sec"]), youtube.format_ts(w["end_sec"])
    return {"windows": windows}, []


def cmd_yt_segment(args):
    course = _load_course(args.course)
    video_id = _video_id(args.video)
    start, end = youtube.parse_ts(args.start), youtube.parse_ts(args.end)
    if end <= start:
        raise CliError("E_USAGE", "--end", "--end must be later than --start")
    transcript = youtube.load_or_fetch_transcript(args.course, video_id, _langs(args, course))
    return {"video_id": video_id, "start_sec": start, "end_sec": end,
            "text": youtube.segment_text(transcript, start, end)}, []


def cmd_open(args):
    """Open web/index.html (or a module's page) in the browser and give its full path: the
    learner is told exactly where the course is."""
    course = _load_course(args.course)
    ids = [m.get("id") for m in course.get("modules") or [] if isinstance(m, dict)]
    name = f"{args.module}.html" if args.module else "index.html"
    path = (Path(args.course) / "web" / name).resolve()
    if (args.module and args.module not in ids) or not path.is_file():
        raise CliError("E_USAGE", "--module" if args.module else "--course",
                       f"no page web/{name}: unknown module or not rendered yet; run aiu render first")
    url = path.as_uri()
    opened = False if args.no_browser else _open_in_browser(path, url)
    return {"path": str(path), "url": url, "opened": opened}, []


def _open_in_browser(path: Path, url: str) -> bool:
    """Windows opens the plain path with the default browser: it misreads a file: address with
    Cyrillic in it, and the learner's folders often have Cyrillic names."""
    if hasattr(os, "startfile"):
        try:
            os.startfile(str(path))
            return True
        except OSError:
            return False
    return bool(webbrowser.open(url))


def cmd_page_check(args):
    try:
        text = args.file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CliError("E_USAGE", "FILE", f"cannot read the page: {exc}") from exc
    problems = [Problem("error", "P1", "page", message) for message in pagecheck.check_page(text)]
    return {"file": str(args.file), "problems": len(problems)}, problems


# --- argument parsing -----------------------------------------------------------------------

def _command(subparsers, name: str, func, full_name: str, help_text: str, course: bool = True):
    parser = subparsers.add_parser(name, help=help_text, description=help_text)
    parser.set_defaults(func=func, command_name=full_name)   # not "name": checkpoint has --name
    if course:
        parser.add_argument("--course", required=True, type=Path, metavar="DIR",
                            help="the course folder (holds course.json)")
    return parser


def _langs_option(parser) -> None:
    parser.add_argument("--langs", metavar="en,bg",
                        help="transcript languages in order of preference "
                             "(default: brief.source_languages)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aiu", description="Course generator tools. Every "
                                     "command prints one JSON object on stdout.")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = _command(sub, "doctor", cmd_doctor, "doctor",
                 "Check Python, packages and write access", course=False)
    p.add_argument("--online", action="store_true",
                   help="also probe the network (a plain site) and YouTube, once each")

    p = _command(sub, "init", cmd_init, "init", "Create the course folder; safe to repeat",
                 course=False)
    p.add_argument("--root", required=True, type=Path, metavar="DIR")
    p.add_argument("--title", required=True, metavar="T")
    p.add_argument("--brief", required=True, type=Path, metavar="FILE",
                   help="JSON file with the course brief")
    p.add_argument("--slug", metavar="S")

    _command(sub, "status", cmd_status, "status", "Module statuses, checkpoints, next action")
    _command(sub, "scaffold", cmd_scaffold, "scaffold",
             "Create missing module folders and empty module.json files")

    p = _command(sub, "validate", cmd_validate, "validate", "Check the rules")
    p.add_argument("--stage", required=True, choices=STAGES)
    p.add_argument("--module", metavar="ID")
    p.add_argument("--gate", choices=validate.GATES, default="drafted")
    p.add_argument("--allow-partial", action="store_true")

    _command(sub, "render", cmd_render, "render", "Rebuild the readable pages")

    p = _command(sub, "checkpoint", cmd_checkpoint, "checkpoint", "Record an approval")
    p.add_argument("--name", required=True, metavar="syllabus|pilot")
    p.add_argument("--by", required=True, metavar="user|auto")
    p.add_argument("--note", default="", metavar="T")

    module = sub.add_parser("module", help="Module commands")
    module_sub = module.add_subparsers(dest="action", required=True, metavar="ACTION")
    p = _command(module_sub, "set-status", cmd_set_status, "module set-status",
                 "Move a module to a status; refuses if its checks fail")
    p.add_argument("module_id", metavar="ID")
    p.add_argument("status", metavar="STATUS")
    p.add_argument("--review", metavar="self|independent")

    p = _command(sub, "finalize", cmd_finalize, "finalize",
                 "Full check, render, mark the course finished")
    p.add_argument("--allow-partial", action="store_true")

    source = sub.add_parser("source", help="Source commands")
    source_sub = source.add_subparsers(dest="action", required=True, metavar="ACTION")
    p = _command(source_sub, "add", cmd_source_add, "source add", "Fetch and register a source")
    p.add_argument("--target", required=True, metavar="benchmarks|ID")
    p.add_argument("--url", required=True, metavar="U")
    p.add_argument("--type", required=True, metavar="T")
    p.add_argument("--reliability", required=True, metavar="R")
    p.add_argument("--why", required=True, metavar="T")
    p.add_argument("--title", metavar="T")
    p.add_argument("--author", metavar="T")
    p.add_argument("--published", metavar="D")
    p.add_argument("--language", metavar="L")
    p.add_argument("--best-use", default="", metavar="T")
    p.add_argument("--extract-file", type=Path, metavar="F",
                   help="text you read yourself when the page blocks scripts")
    _langs_option(p)

    p = _command(source_sub, "set", cmd_source_set, "source set",
                 "Correct one metadata field of a registered source")
    p.add_argument("--target", required=True, metavar="benchmarks|ID")
    p.add_argument("--id", required=True, metavar="S1|B1", help="the source's id in that target")
    p.add_argument("--field", required=True, metavar="F",
                   help=f"one of: {', '.join(sources.SETTABLE_FIELDS)}")
    p.add_argument("--value", required=True, metavar="V",
                   help='the new value; "null" or "none", any case (or an empty value), clears author, published, '
                        "language or best_use")

    p = _command(sub, "linkcheck", cmd_linkcheck, "linkcheck",
                 "Check every link and record the result")
    p.add_argument("--module", metavar="ID")

    yt = sub.add_parser("yt", help="YouTube commands")
    yt_sub = yt.add_subparsers(dest="action", required=True, metavar="ACTION")
    p = _command(yt_sub, "search", cmd_yt_search, "yt search", "Find candidate videos",
                 course=False)
    p.add_argument("query", metavar="QUERY")
    p.add_argument("--max", type=_positive_int, default=10, metavar="N")
    p.add_argument("--min-minutes", type=int, default=4, metavar="N")
    p.add_argument("--max-minutes", type=int, default=120, metavar="N")

    p = _command(yt_sub, "transcript", cmd_yt_transcript, "yt transcript",
                 "Fetch and cache a transcript")
    p.add_argument("video", metavar="VIDEO", help="video id or URL")
    _langs_option(p)

    p = _command(yt_sub, "find", cmd_yt_find, "yt find", "Locate where terms are discussed")
    p.add_argument("video", metavar="VIDEO", help="video id or URL")
    p.add_argument("--terms", required=True, metavar="a,b,c")
    p.add_argument("--window", type=_positive_int, default=90, metavar="SEC")
    p.add_argument("--top", type=_positive_int, default=5, metavar="N")
    _langs_option(p)

    p = _command(yt_sub, "segment", cmd_yt_segment, "yt segment", "Print the text of a segment")
    p.add_argument("video", metavar="VIDEO", help="video id or URL")
    p.add_argument("--start", required=True, metavar="MM:SS")
    p.add_argument("--end", required=True, metavar="MM:SS")
    _langs_option(p)

    p = _command(sub, "open", cmd_open, "open", "Open the course page in the browser; give its full path")
    p.add_argument("--module", metavar="ID", help="open this module's page instead of web/index.html")
    p.add_argument("--no-browser", action="store_true", help="only report the path")

    p = _command(sub, "page-check", cmd_page_check, "page-check",
                 "Check that a web page follows the page contract", course=False)
    p.add_argument("file", type=Path, metavar="FILE", help="the HTML page")
    return parser


# --- entry point ----------------------------------------------------------------------------

def _problems_from(exc: Exception, where: str) -> list:
    if isinstance(exc, state.GateError):
        return list(exc.problems)
    if isinstance(exc, render.RenderError) and exc.problems:
        return list(exc.problems)
    if isinstance(exc, CliError):
        return [exc.problem]
    if isinstance(exc, youtube.TranscriptUnavailable):
        detail = f": {exc.detail}" if exc.detail else ""
        return [Problem("error", "E_TRANSCRIPT", where, f"no transcript ({exc.reason}){detail}")]
    if isinstance(exc, USAGE_ERRORS):
        return [Problem("error", "E_USAGE", where, str(exc))]
    return [Problem("error", "E_INTERNAL", where, f"{type(exc).__name__}: {exc}")]


def _item(problem: Problem) -> dict:
    return {"code": problem.code, "where": problem.where, "message": problem.message}


def _exit_code(errors: list) -> int:
    """2 for course.json (C1) and usage/environment (E_*) errors, 1 for rule errors."""
    if any(e["code"] == "C1" or e["code"].startswith("E_") for e in errors):
        return 2
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            # A lone surrogate (possible in scraped titles and captions) is written as \udcxx,
            # which is still valid JSON, instead of crashing the one envelope we print.
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:   # malformed command line or --help: argparse has printed
        return exc.code if isinstance(exc.code, int) else 0
    try:
        data, problems = args.func(args)
    except Exception as exc:  # noqa: BLE001 - every failure becomes one JSON envelope
        if os.environ.get("AIU_DEBUG") == "1":
            traceback.print_exc(file=sys.stderr)
        data, problems = {}, _problems_from(exc, args.command_name)
    errors = [_item(p) for p in problems if p.level == "error"]
    warnings = [_item(p) for p in problems if p.level != "error"]
    code = _exit_code(errors)
    emit(args.command_name, code == 0, data, warnings, errors)
    return code


if __name__ == "__main__":
    sys.exit(main())
