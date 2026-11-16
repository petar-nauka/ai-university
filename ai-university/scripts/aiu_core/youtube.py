"""YouTube helpers: search, transcripts (cached per course) and transcript segments."""
import re
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from aiu_core.store import read_json, write_json

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_VTT_TS = re.compile(r"(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2}\.\d{3})")
_VTT_TAG = re.compile(r"<[^>]+>")


_ANSI = re.compile(r"\x1b\[[0-9;]*m")   # colour codes yt-dlp puts in its messages


class _Silent:
    """A yt-dlp logger that prints nothing: aiu prints one JSON object and nothing else."""

    def debug(self, msg):
        pass

    warning = info = error = debug


class TranscriptUnavailable(Exception):
    """No transcript could be obtained; `.reason` is no_subs | blocked | unavailable | error."""

    def __init__(self, reason: str, detail: str = ""):
        detail = _ANSI.sub("", detail or "")
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def video_id_from_url(url_or_id: str) -> str | None:
    text = (url_or_id or "").strip()
    if _ID_RE.match(text):
        return text
    try:
        parsed = urlparse(text)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    candidate = None
    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host == "youtube.com" or host.endswith(".youtube.com"):
        parts = [p for p in parsed.path.split("/") if p]
        if parsed.path.rstrip("/") == "/watch":
            candidate = (parse_qs(parsed.query).get("v") or [""])[0]
        elif len(parts) >= 2 and parts[0] in ("shorts", "embed", "live"):
            candidate = parts[1]
    return candidate if candidate and _ID_RE.match(candidate) else None


def watch_url(video_id: str, start_sec: int | None = None) -> str:
    url = f"https://www.youtube.com/watch?v={video_id}"
    return url if start_sec is None else f"{url}&t={int(start_sec)}s"


def parse_ts(text: str) -> int:
    parts = (text or "").strip().split(":")
    if not 1 <= len(parts) <= 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"invalid timestamp: {text!r}")
    nums = [int(p) for p in parts]
    if len(nums) > 1 and any(n >= 60 for n in nums[1:]):
        raise ValueError(f"invalid timestamp: {text!r}")
    total = 0
    for n in nums:
        total = total * 60 + n
    return total


def format_ts(sec: int) -> str:
    sec = int(sec)
    h, rest = divmod(sec, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _vtt_sec(ts: str) -> int:
    h, m, rest = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + int(rest.split(".")[0])


def parse_vtt(text: str) -> list[dict]:
    """Parse WebVTT text into cues, removing the rolling repetition of auto-captions."""
    cues: list[dict] = []
    lines = text.splitlines()
    i = 0
    last_text = ""
    while i < len(lines):
        m = _VTT_TS.search(lines[i])
        if not m:
            i += 1
            continue
        start = _vtt_sec(m.group(1))
        i += 1
        chunk = []
        while i < len(lines) and lines[i].strip():
            cleaned = _VTT_TAG.sub("", lines[i]).strip()
            if cleaned:
                chunk.append(cleaned)
            i += 1
        joined = " ".join(chunk).strip()
        if joined and joined != last_text and not last_text.endswith(joined):
            if last_text and joined.startswith(last_text):
                new_part = joined[len(last_text):].strip()
            else:
                new_part = joined
            if new_part:
                cues.append({"start_sec": start, "text": new_part})
            last_text = joined
    return cues


def filter_candidates(entries: list[dict], max_results: int, min_seconds: int,
                      max_seconds: int) -> list[dict]:
    out = []
    for e in entries:
        if not e or not e.get("id") or e.get("duration") is None:
            continue
        duration = int(e["duration"])
        if not min_seconds <= duration <= max_seconds:
            continue
        out.append({"video_id": e["id"], "title": e.get("title") or "",
                    "channel": e.get("channel") or e.get("uploader") or "",
                    "duration_sec": duration, "url": watch_url(e["id"])})
        if len(out) >= max_results:
            break
    return out


def segment_text(transcript: dict, start_sec: int, end_sec: int) -> str:
    return "\n".join(f"[{format_ts(c['start_sec'])}] {c['text']}"
                     for c in transcript["cues"] if start_sec <= c["start_sec"] < end_sec)


def find_windows(transcript: dict, terms: list[str], window_sec: int = 90, top: int = 5) -> list[dict]:
    cues = transcript["cues"]
    needles = [t.lower() for t in terms if t]
    duration = transcript.get("duration_sec")
    if duration is None:
        duration = cues[-1]["start_sec"] + 5 if cues else 0
    candidates = []
    for cue in cues:
        start = cue["start_sec"]
        joined = " ".join(c["text"] for c in cues if start <= c["start_sec"] < start + window_sec)
        low = joined.lower()
        hits = sum(low.count(n) for n in needles)
        if hits > 0:
            candidates.append({"start_sec": start, "end_sec": min(start + window_sec, duration),
                               "hits": hits, "preview": joined[:200]})
    candidates.sort(key=lambda w: (-w["hits"], w["start_sec"]))
    chosen: list[dict] = []
    for w in candidates:
        if len(chosen) >= top:
            break
        if all(abs(w["start_sec"] - c["start_sec"]) >= window_sec for c in chosen):
            chosen.append(w)
    return chosen


def load_or_fetch_transcript(course_dir: Path, video_id: str, langs: list[str],
                             duration_sec: int | None = None, fetcher=None,
                             today: str | None = None) -> dict:
    path = Path(course_dir) / "research" / "transcripts" / f"{video_id}.json"
    if path.is_file():
        return read_json(path)
    transcript = (fetcher or fetch_transcript)(video_id, langs)
    cues = transcript["cues"]
    if duration_sec is None:
        duration_sec = (cues[-1]["start_sec"] + 5) if cues else 0
    transcript = dict(transcript, duration_sec=duration_sec,
                      fetched_at=today or date.today().isoformat())
    write_json(path, transcript)
    return transcript


# --- network functions (checked live in Task 11) ----------------------------

def search(query: str, max_results: int = 10, min_seconds: int = 240,
           max_seconds: int = 7200) -> list[dict]:
    import yt_dlp
    opts = {"quiet": True, "logger": _Silent(), "no_warnings": True, "skip_download": True,
            "extract_flat": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{max_results * 2}:{query}", download=False)
    return filter_candidates(info.get("entries") or [], max_results, min_seconds, max_seconds)


def fetch_metadata(video_id: str) -> dict:
    import yt_dlp
    opts = {"quiet": True, "logger": _Silent(), "no_warnings": True, "skip_download": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(watch_url(video_id), download=False)
    upload = info.get("upload_date") or ""
    published = f"{upload[:4]}-{upload[4:6]}-{upload[6:8]}" if re.fullmatch(r"\d{8}", upload) else None
    return {"title": info.get("title") or "",
            "channel": info.get("channel") or info.get("uploader") or "",
            "duration_sec": int(info.get("duration") or 0), "published": published}


def _classify(exc: Exception) -> str:
    name = type(exc).__name__
    message = str(exc).lower()
    if name == "VideoUnavailable":
        return "unavailable"
    if name in ("NoTranscriptFound", "TranscriptsDisabled"):
        return "no_subs"
    if any(k in message for k in ("blocked", "too many requests", "sign in")):
        return "blocked"
    return "error"


def _fetch_via_yt_dlp(video_id: str, langs: list[str]) -> dict:
    import yt_dlp
    with tempfile.TemporaryDirectory() as tmp:
        opts = {"skip_download": True, "writesubtitles": True, "writeautomaticsub": True,
                "subtitleslangs": langs, "subtitlesformat": "vtt",
                "outtmpl": f"{tmp}/%(id)s.%(ext)s", "quiet": True, "logger": _Silent(), "no_warnings": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(watch_url(video_id), download=True)
        # downloaded files are named <id>.<lang>.vtt; take them in the order of langs, so an
        # auto-translated track never wins over the language asked for first
        files = {f.name[len(video_id) + 1:-len(".vtt")]: f for f in Path(tmp).glob("*.vtt")}
        if not files:
            raise TranscriptUnavailable("no_subs")
        lang = next((code for code in langs if code in files), sorted(files)[0])
        cues = parse_vtt(files[lang].read_text(encoding="utf-8", errors="replace"))
        lang = lang or langs[0]
    kind = "manual" if lang in (info.get("subtitles") or {}) else "auto"
    return {"video_id": video_id, "lang": lang, "kind": kind, "cues": cues}


def fetch_transcript(video_id: str, langs: list[str]) -> dict:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=langs)
        cues = [{"start_sec": int(s.start), "text": s.text.strip()}
                for s in fetched.snippets if s.text.strip()]
        if cues:
            return {"video_id": video_id, "lang": fetched.language_code,
                    "kind": "auto" if fetched.is_generated else "manual", "cues": cues}
        first_error: Exception = TranscriptUnavailable("no_subs")
    except Exception as exc:  # noqa: BLE001 - classified below
        first_error = exc
    if type(first_error).__name__ == "VideoUnavailable":
        raise TranscriptUnavailable("unavailable", str(first_error)) from first_error
    try:
        result = _fetch_via_yt_dlp(video_id, langs)
        if not result["cues"]:
            raise TranscriptUnavailable("no_subs")
        return result
    except TranscriptUnavailable as exc:
        if exc.reason == "no_subs" and not isinstance(first_error, TranscriptUnavailable):
            raise TranscriptUnavailable(_classify(first_error), str(first_error)) from first_error
        raise
    except Exception as exc:  # noqa: BLE001
        reason = _classify(exc)
        if reason == "error":
            reason = _classify(first_error)
        raise TranscriptUnavailable(reason, str(exc)) from exc
