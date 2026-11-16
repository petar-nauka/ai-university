"""The course as web pages: web/index.html, and per verified module web/<ID>.html (the day
plan, the lesson, the tasks, the resources its steps open, the sources and what comes next) and
web/<ID>-answers.html. Each page is the shell assets/page-shell.html filled with content by the
contract in references/page-format.md; the shell's script builds the view in the browser.
Self-contained HTML: no external files, it opens from disk with a double click."""
import hashlib
import html
import re
from pathlib import Path
from urllib.parse import urlsplit

from .render import BAD_CHECK, WEAK_ACCESS, RenderError, _count, _dict, _num, _records
from .schedule import day_date, day_week, format_weeks
from .youtube import format_ts, parse_ts, watch_url

# The page shell: every web page is this file with its three slots filled
# (references/page-format.md). It sits in the skill's assets folder.
SHELL_PATH = Path(__file__).resolve().parents[2] / "assets" / "page-shell.html"
_SLOTS = ("{{AIU_LANG}}", "{{AIU_TITLE}}", "<!-- AIU:CONTENT -->")


def fill_shell(lang: str, title: str, content: str) -> str:
    """The shell with its language, title and content filled in. The content goes in last, so
    text in it that looks like a slot is never replaced."""
    try:
        shell = SHELL_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RenderError(f"The page shell is missing: {SHELL_PATH.name} ({exc})") from exc
    missing = [slot for slot in _SLOTS if slot not in shell]
    if missing:
        raise RenderError(f"The page shell {SHELL_PATH.name} has lost its slot(s): {', '.join(missing)}")
    shell = shell.replace(_SLOTS[0], html.escape(lang), 1).replace(_SLOTS[1], html.escape(title), 1)
    return shell.replace(_SLOTS[2], content, 1)


WEB = {
    "bg": {
        "day": "Ден", "week": "Седмица", "glossary": "Речник", "answers": "Отговори",
        "all_modules": "Всички модули", "goal": "Цел", "plan": "Учебен план", "topics": "Теми",
        "out_of_scope": "Извън курса", "deliverable": "Какво предаваш",
        "total": "{weeks} · {days} учебни дни в седмицата, по около {minutes} мин · общо {total} ч: "
                 "модули {modules} ч, краен проект {capstone} ч, резерв {reserve} ч.",
        "prompt_text": "Продължи курса „{title}“ (папка {folder}) с умението ai-university: "
                       "изгради модул {id} „{next_title}“.",
        "next_module": "Следващ модул", "capstone": "Краен проект", "pending": "предстои",
        "criteria": "Критерии", "turn_in": "Предаваш", "pts": "т.", "reliability": "надеждност",
        "sources_here": "Източници в този раздел", "hours": "ч", "outcomes": "Какво ще можеш след модула",
        "mode_full": "Пълен режим: скриптът е отворил и записал всеки източник, минутите на видеата са взети "
                     "от прочетения им текст, а всеки модул е минал автоматичните проверки, преди да бъде "
                     "отбелязан като готов.",
        "based_on": "Програми, на които стъпва курсът", "no_benchmarks": "Няма записани програми.",
        "assumptions": "Какво е прието вместо теб", "missing": "Какво липсва",
        "no_gaps": "В готовите модули няма записани липси.", "review": "Как е проверен всеки модул",
        "review_independent": "независим преглед от отделен ИИ агент и автоматичните проверки",
        "review_self": "самопроверка на ИИ и автоматичните проверки (без независим преглед)",
        "weak": "Източници с ограничен достъп или линк, който не се отваря",
        "no_weak": "В готовите модули няма източници с ограничен достъп или линк, за който е известно, че не се отваря.",
    },
    "en": {
        "day": "Day", "week": "Week", "glossary": "Glossary", "answers": "Answers",
        "all_modules": "All modules", "goal": "Goal", "plan": "Study plan", "topics": "Topics",
        "out_of_scope": "Left out of this course", "deliverable": "What you hand in",
        "total": "{weeks} · {days} study days a week, about {minutes} min each · {total} h in all: "
                 "modules {modules} h, capstone {capstone} h, reserve {reserve} h.",
        "prompt_text": "Continue the course “{title}” (folder {folder}) with the ai-university "
                       "skill: build module {id} “{next_title}”.",
        "next_module": "Next module", "capstone": "Capstone project", "pending": "not built yet",
        "criteria": "Criteria", "turn_in": "Turn in", "pts": "pts", "reliability": "reliability",
        "sources_here": "Sources in this section", "hours": "h", "outcomes": "What you can do after this module",
        "mode_full": "Full mode: the script opened and recorded every source, video minutes come from the "
                     "text that was read, and every module passed the automatic checks before it was "
                     "marked ready.",
        "based_on": "Programmes this course is based on", "no_benchmarks": "No programmes recorded.",
        "assumptions": "What was assumed for you", "missing": "What is missing",
        "no_gaps": "No gaps are recorded in the ready modules.", "review": "How each module was checked",
        "review_independent": "an independent review by a separate AI agent and the automatic checks",
        "review_self": "the AI's own review and the automatic checks (no independent review)",
        "weak": "Sources with limited access or a link that does not open",
        "no_weak": "No source in the ready modules has limited access or a link known not to open.",
    },
}

_SOURCE = re.compile(r"(?<![\w\[/])S\d+(?![\w\]])")
_TASK = re.compile(r"(?<![\w\[/-])M\d{2}-P\d+(?![\w\]-])")
_CITE = re.compile(r"\[(S\d+)(?:\s*@\s*(\d{1,2}:\d{2}(?::\d{2})?))?\]")
_LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_MARKER = re.compile(r"<!--\s*(?:outcome|practice|answer):\s*([\w-]+)\s*-->")
_LESSON_WORD = re.compile(r"\s*(урок|lesson)\b", re.IGNORECASE)

esc = html.escape


def _safe_url(url) -> str:
    """A link the pages may show: only web addresses (http, https). Anything else, such as a
    javascript: or data: address in a source record, is no link at all: sources are data."""
    url = str(url or "").strip()
    return url if urlsplit(url).scheme.lower() in ("http", "https") else ""


# --- Markdown (the subset lesson, practice, answers and capstone files use) ----------------
def _inline(text: str, sources: dict) -> str:
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f"<code>{esc(part[1:-1])}</code>")
            continue
        s = esc(part, quote=False)
        s = _LINK.sub(lambda m: (f'<a href="{esc(html.unescape(m.group(2)))}" target="_blank" rel="noopener">{m.group(1)}</a>'
                                 if re.match(r"https?://|#|[\w.-]+\.html(#[\w-]*)?$", m.group(2)) else m.group(0)), s)
        s = _CITE.sub(lambda m: _cite(m, sources), s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        out.append(s)
    return "".join(out)


def _cite(m, sources) -> str:
    sid, ts = m.group(1), m.group(2)
    s = sources.get(sid)
    if not s:
        return m.group(0)
    vid = (s.get("video") or {}).get("video_id") if isinstance(s.get("video"), dict) else None
    try:
        url = watch_url(vid, parse_ts(ts)) if vid and ts else _safe_url(s.get("url"))
    except ValueError:
        url = _safe_url(s.get("url"))
    if not url:
        return m.group(0)
    # a small number in the sentence; the full citation and the title show on pointing at it
    title = esc(f"{m.group(0)} · {s.get('title') or sid}")
    return (f'<sup><a class="cite" href="{esc(url)}" target="_blank" rel="noopener" title="{title}">'
            f'{sid[1:]}</a></sup>')


def md_to_html(md: str, sources: dict, shift: int = 1) -> str:
    lines, out, para, i = (md or "").splitlines(), [], [], 0

    def flush():
        if para:
            out.append(f"<p>{_inline(' '.join(para), sources)}</p>")
            para.clear()

    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("```"):
            flush()
            code, i = [], i + 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            out.append(f"<pre><code>{esc(chr(10).join(code))}</code></pre>")
            i += 1
            continue
        marker = _MARKER.fullmatch(s)
        if marker:
            flush()
            out.append(f'<a class="anchor" id="{esc(marker.group(1))}"></a>')
        elif s.startswith("<!--"):
            flush()
            while i < len(lines) and "-->" not in lines[i]:
                i += 1
        elif re.fullmatch(r"<details>\s*<summary>.*?</summary>.*\S.*</details>", s):   # a one-line self-check
            flush()
            m = re.fullmatch(r"<details>\s*<summary>(.*?)</summary>(.*)</details>", s)
            out.append(f"<details><summary>{_inline(m.group(1), sources)}</summary>"
                       f"<p>{_inline(m.group(2).strip(), sources)}</p></details>")
        elif re.fullmatch(r"<details>\s*(<summary>.*</summary>)?", s):
            flush()
            summary = re.search(r"<summary>(.*)</summary>", s)
            out.append("<details>" + (f"<summary>{_inline(summary.group(1), sources)}</summary>"
                                      if summary else ""))
        elif s == "</details>":
            flush()
            out.append("</details>")
        elif re.fullmatch(r"<summary>.*</summary>", s):   # a summary on its own line
            flush()
            out.append(f"<summary>{_inline(s[9:-10], sources)}</summary>")
        elif not s:
            flush()
        elif re.match(r"#{1,6}\s", s):
            flush()
            level = min(6, len(s) - len(s.lstrip("#")) + shift)
            out.append(f"<h{level}>{_inline(s.lstrip('#').strip(), sources)}</h{level}>")
        elif s.startswith("|") and i + 1 < len(lines) and re.fullmatch(r"\|?[\s:|-]+\|?", lines[i + 1].strip()):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in re.split(r"(?<!\\)\|", lines[i].strip().strip("|"))])
                i += 1
            head, body = rows[0], rows[2:]
            out.append("<div class=\"table\"><table><thead><tr>"
                       + "".join(f"<th>{_inline(c, sources)}</th>" for c in head) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_inline(c, sources)}</td>" for c in r) + "</tr>"
                                 for r in body) + "</tbody></table></div>")
            continue
        elif re.match(r"([-*+]|\d+[.)])\s+", s):
            flush()
            ordered = bool(re.match(r"\d", s))
            items = []
            while i < len(lines):
                t = lines[i].strip()
                m = re.match(r"([-*+]|\d+[.)])\s+(.*)", t)
                if m:
                    items.append(m.group(2))
                elif t and lines[i][:1] in (" ", "\t") and items:
                    items[-1] += " " + t
                else:
                    break
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(x, sources)}</li>" for x in items) + f"</{tag}>")
            continue
        elif s.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(quote), sources)}</blockquote>")
            continue
        elif re.fullmatch(r"(-{3,}|\*{3,})", s):
            flush()
            out.append("<hr>")
        elif s.endswith("</details>"):   # "The answer.</details>": the text, then the end of the block
            para.append(s[:-len("</details>")].strip())
            flush()
            out.append("</details>")
        else:
            para.append(s)
        i += 1
    flush()
    return "\n".join(out)


# --- data ---------------------------------------------------------------------------
def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _folder(course_dir: Path) -> str:
    """The course folder as the learner's next session will see it: relative to the folder
    the course was built from, else its last two parts (courses/<slug>)."""
    course_dir = Path(course_dir).resolve()
    try:
        return course_dir.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return f"{course_dir.parent.name}/{course_dir.name}"


def _item_kind(text, links, roles) -> str:
    if links and any(t in links["tasks"] for t in _TASK.findall(text)):
        return "task"
    sids = [s for s in _SOURCE.findall(text) if links and s in links["urls"]]
    if any(roles.get(s) == "video" for s in sids):
        return "video"
    if sids:
        return "reading"
    return "lesson" if _LESSON_WORD.match(text) else "other"


def _item_html(text, links) -> str:
    """The step text with its source ids and task ids as links."""
    def src(m):
        url = _safe_url(links["urls"].get(m.group(0))) if links else ""
        return f'<a href="{esc(url)}" target="_blank" rel="noopener">{m.group(0)}</a>' if url else m.group(0)

    def task(m):
        if not links or m.group(0) not in links["tasks"]:
            return m.group(0)
        return f'<a href="#{m.group(0)}">{m.group(0)}</a>'

    return _TASK.sub(task, _SOURCE.sub(src, esc(text, quote=False)))


def _module_days(c, index, roles):
    uid, first, n, hours, plan, links = c.days[index]
    start = c.brief.get("start_date")
    days = []
    for i, d in enumerate(plan):
        day = first + i
        items = []
        for x in d["items"]:
            if not x:
                continue
            text = str(x)
            items.append({"id": f"d{day}-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:8],
                          "kind": _item_kind(text, links, roles), "text": text, "html": _item_html(text, links)})
        days.append({"day": day, "week": day_week(day, c.dpw), "minutes": d.get("minutes"),
                     "date": day_date(start, day, c.dpw) if start else None, "items": items})
    return days


_YT_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_SECTION_REF = re.compile(r"(?:раздел|section)\w*\s+(\d+)", re.IGNORECASE)
_QUOTED = re.compile(r"[„“\"«]([^„“”\"«»]{3,})[“”\"»]")


def _lesson_sections(md: str) -> list[dict]:
    """The lesson split at its ## headings: {"no", "title", "md"}; the first part is the intro."""
    sections = [{"no": None, "title": "", "lines": []}]
    for line in (md or "").splitlines():
        m = re.match(r"##(?!#)\s+(.*)", line)
        if m:
            title = m.group(1).strip()
            no = re.match(r"(\d+)[.)]?\s+", title)
            sections.append({"no": int(no.group(1)) if no else None,
                             "title": title[no.end():] if no else title, "lines": [line]})
        else:
            sections[-1]["lines"].append(line)
    for s in sections:
        s["md"] = "\n".join(s.pop("lines"))
    return sections


def _matching_sections(text: str, sections: list[dict]) -> list[int]:
    """The lesson sections a plan step names: by number ("раздел 2"), by a quoted title, or
    else by a title the step contains."""
    nos = {int(n) for n in _SECTION_REF.findall(text)}
    quoted = [q.strip().casefold() for q in _QUOTED.findall(text)]
    hits = [k for k, s in enumerate(sections) if s["title"] and (
        (s["no"] is not None and s["no"] in nos)
        or any(q == s["title"].casefold() or q in s["title"].casefold() for q in quoted))]
    low = text.casefold()
    return hits or [k for k, s in enumerate(sections) if len(s["title"]) >= 4 and s["title"].casefold() in low]


def _loc(r, key):
    loc = r.get("locator")
    return loc.get(key) if isinstance(loc, dict) else None


def _source_link(sid, s):
    url, title = _safe_url(s.get("url")), esc(str(s.get("title") or sid))
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{title}</a>' if url else title


# --- what the steps open: resources, lesson parts, tasks --------------------------------
def _head(s):
    meta = " · ".join(esc(str(x)) for x in (s.get("author"), s.get("published")) if x)
    return (f"<h2>{esc(str(s.get('title') or s.get('id') or ''))}</h2>"
            + (f"<p data-meta>{meta}</p>" if meta else ""))


def _video_article(r, s, whole=False):
    """(id, article) for a video segment the learner can open at its minute, else None. With
    `whole`, the whole video of a source nobody read (role reference): unverified, no minutes."""
    video = s.get("video") if isinstance(s.get("video"), dict) else {}
    vid, start, end = video.get("video_id"), _loc(r, "start_sec"), _loc(r, "end_sec")
    if whole:
        start, end = 0, None
    if not (isinstance(vid, str) and _YT_ID.fullmatch(vid) and isinstance(start, int)):
        return None
    end = end if isinstance(end, int) and end > start else None
    rid = f"v-{s.get('id')}-{start}"
    body = [_head(s)]
    for key, attr in (("before_question", "data-before"), ("after_task", "data-after")):
        if r.get(key):
            body.append(f"<p {attr}>{esc(str(r[key]))}</p>")
    if r.get("note"):
        body.append(f'<p class="muted small">{esc(str(r["note"]))}</p>')
    if whole:
        url, span = f"https://www.youtube.com/watch?v={vid}", ' data-verified="false"'
    else:
        url = watch_url(vid, start)
        span = (f' data-from="{format_ts(start)}"' + (f' data-to="{format_ts(end)}"' if end else "")
                + ' data-verified="true"')
    return rid, f'<article id="{esc(rid)}" data-kind="video" data-url="{esc(url)}"{span}>{"".join(body)}</article>'



def _reading_article(sid, s, rs):
    url = _safe_url(s.get("url"))
    what = list(dict.fromkeys(str(_loc(r, "section")) for r in rs if _loc(r, "section")))
    body = ([_head(s)] + ([f"<p data-what>{esc('; '.join(what))}</p>"] if what else [])
            + [f"<p>{esc(str(r['note']))}</p>" for r in rs if r.get("note")])
    return (f'<article id="r-{esc(sid)}" data-kind="reading"' + (f' data-url="{esc(url)}"' if url else "")
            + f'>{"".join(body)}</article>')


def _step_refs(text, kind, links, data, sources, sections, task_ids, arts) -> list[str]:
    """The ids of what a plan step opens; the resources it needs are added to `arts`."""
    if kind == "task":
        tid = next((x for x in _TASK.findall(text) if x in links["tasks"]), None)
        return [tid] if tid in task_ids else []
    if kind in ("video", "reading"):
        resources = [r for r in _records(data, "resources") if isinstance(r, dict)]
        for sid in [x for x in _SOURCE.findall(text) if x in sources]:
            rs = [r for r in resources if r.get("source_id") == sid]
            videos = [r for r in rs if r.get("role") == "video"]
            extras = [r for r in rs if r.get("role") == "reference"]
            if kind == "video" and (videos or extras):
                r = next((v for v in videos if isinstance(_loc(v, "start_sec"), int)
                          and format_ts(_loc(v, "start_sec")) in text), (videos or extras)[0])
                found = _video_article(r, sources[sid], whole=not videos)
                if found:
                    arts.setdefault(*found)
                    return [found[0]]
            if kind == "reading":
                arts.setdefault(f"r-{sid}", _reading_article(sid, sources[sid], rs))
                return [f"r-{sid}"]
    if kind == "lesson":
        hits = _matching_sections(text, sections) or [k for k, s in enumerate(sections) if s["md"].strip()]
        return [f"ls-{k}" for k in hits]
    return []


def _next_info(c, index, W):
    """What comes after module `index`: a prompt to build the next module, a link to its
    page, or the capstone."""
    m = c.mods[index][0]
    if index + 1 >= len(c.mods):
        return {"kind": "capstone"}
    nxt, ndata = c.mods[index + 1]
    if m["id"] in c.remind:
        text = W["prompt_text"].format(title=c.title, folder=_folder(c.course_dir), id=nxt["id"],
                                       next_title=nxt["title"])
        return {"kind": "prompt", "text": text, "id": nxt["id"], "title": nxt["title"]}
    if ndata.get("status") == "verified":
        return {"kind": "link", "id": nxt["id"], "title": nxt["title"]}
    return {"kind": "pending", "id": nxt["id"], "title": nxt["title"]}


def _next_html(info, W):
    kind = info["kind"]
    if kind == "prompt":
        body = f"<pre data-prompt>{esc(info['text'])}</pre>"
    elif kind == "link":
        body = (f'<a href="{esc(info["id"])}.html">{W["next_module"]}: {esc(info["id"])} · '
                f'{esc(info["title"])} →</a>')
    elif kind == "pending":
        body = f'{W["next_module"]}: {esc(info["id"])} · {esc(info["title"])} ({W["pending"]})'
    else:
        body = f'<a href="index.html#capstone">{W["capstone"]} →</a>'
    return f'<section data-next data-kind="{kind}">{body}</section>'


def _rubric(t, W):
    crit = "".join(f"<li>{esc(str(k.get('text', '')))} <span class=\"pts\">{esc(str(k.get('points', '')))} "
                   f"{W['pts']}</span></li>" for k in t.get("criteria") or [] if isinstance(k, dict))
    body = ((f"<p><strong>{W['turn_in']}:</strong> {esc(str(t['deliverable']))}</p>" if t.get("deliverable") else "")
            + (f"<p><strong>{W['criteria']}:</strong></p><ul>{crit}</ul>" if crit else ""))
    return f"<div data-rubric>{body}</div>" if body else ""


def _tasks_html(practice_md, data, sources, W) -> tuple[str, set]:
    """section[data-tasks]: each task of practice.md as article[data-task] with its rubric,
    and the set of task ids it holds."""
    tasks = {t.get("id"): t for t in _records(data, "practice") if isinstance(t, dict)}
    out, ids = [], set()
    for chunk in re.split(r"(?=<!--\s*practice:)", practice_md or ""):
        m = _MARKER.search(chunk)
        body = md_to_html(_MARKER.sub("", chunk), sources, shift=2)
        if not m or m.group(1) in ids:   # the text before the first task, or a repeated marker
            out.append(body)
            continue
        tid = m.group(1)
        ids.add(tid)
        t = tasks.get(tid)
        out.append(f'<article data-task id="{esc(tid)}">{body}{_rubric(t, W) if t else ""}</article>')
    return "<section data-tasks>" + "\n".join(out) + "</section>", ids


def _lesson_html(sections, sources, W):
    """section[data-lesson]: a part per ## heading, each with the sources it cites."""
    parts = []
    for k, s in enumerate(sections):
        cited = list(dict.fromkeys(sid for sid, _ts in _CITE.findall(s["md"]) if sid in sources))
        aside = ("" if not cited else
                 f'<aside class="pop-sources"><p><strong>{W["sources_here"]}:</strong></p><ul>'
                 + "".join(f'<li><span class="sid">{sid}</span> {_source_link(sid, sources[sid])}</li>' for sid in cited)
                 + "</ul></aside>")
        parts.append(f'<section id="ls-{k}">{md_to_html(s["md"], sources)}{aside}</section>')
    return "<section data-lesson>" + "\n".join(parts) + "</section>"


def _sources_html(data, W):
    rows = []
    for s in _records(data, "sources"):
        if not isinstance(s, dict):
            continue
        meta = " · ".join(esc(str(x)) for x in (s.get("author"), s.get("published"), s.get("type")) if x)
        url, title = _safe_url(s.get("url")), esc(str(s.get("title") or ""))
        link = f'<a href="{esc(url)}" target="_blank" rel="noopener">{title}</a>' if url else title
        rows.append(f'<li><span class="sid">{esc(str(s.get("id", "")))}</span> {link}'
                    f'<div class="meta">{meta} · {W["reliability"]}: {esc(str(s.get("reliability", "")))}</div></li>')
    return f'<ul class="sources">{"".join(rows)}</ul>'


def _glossary_html(data, W):
    rows = []
    for g in _records(data, "glossary"):
        if isinstance(g, dict) and g.get("term"):
            en = f" ({esc(str(g['term_en']))})" if g.get("term_en") and g["term_en"] != g["term"] else ""
            rows.append(f"<dt>{esc(str(g['term']))}{en}</dt><dd>{esc(str(g.get('definition', '')))}</dd>")
    return f'<h3 class="subhead">{W["glossary"]}</h3><dl class="glossary">{"".join(rows)}</dl>' if rows else ""


# --- pages ------------------------------------------------------------------------------
def _lang(c):
    code = str(c.brief.get("language", "en")).split("-")[0].lower()
    return code, WEB.get(code, WEB["en"])


def _main(c, page, extra=""):
    code = _lang(c)[0]
    cid = c.course.get("course_id") or c.course_dir.name
    return (f'<main id="aiu" data-page="{page}" data-course="{esc(str(cid))}"{extra} data-lang="{esc(code)}" '
            f'data-mode="full">')


def _sources_of(data):
    return {s["id"]: s for s in _records(data, "sources") if isinstance(s, dict) and isinstance(s.get("id"), str)}


def module_content(c, index) -> str:
    """The content of web/<ID>.html: the days with their steps, the lesson, the tasks, the
    resources the steps open, the sources and what comes next."""
    code, W = _lang(c)
    m, data = c.mods[index]
    mdir = c.course_dir / "modules" / m["slug"]
    sources = _sources_of(data)
    roles = {r.get("source_id"): r.get("role") for r in _records(data, "resources") if isinstance(r, dict)}
    for r in _records(data, "resources"):   # a video kept as a whole extra is still a video step
        sid = r.get("source_id") if isinstance(r, dict) else None
        if isinstance(sid, str) and sid in sources and r.get("role") in ("video", "reference") and isinstance(sources[sid].get("video"), dict):
            roles[sid] = "video"
    sections = _lesson_sections(_read(mdir / "lesson.md"))
    tasks, task_ids = _tasks_html(_read(mdir / "practice.md"), data, sources, W)
    links, arts, days = c.days[index][5], {}, []
    for d in _module_days(c, index, roles):
        steps = []
        for it in d["items"]:
            refs = _step_refs(it["text"], it["kind"], links, data, sources, sections, task_ids, arts) if links else []
            ref = f' data-ref="{esc(" ".join(refs))}"' if refs else ""
            steps.append(f'<div data-step="{it["kind"]}"{ref} data-id="{it["id"]}">{it["html"]}</div>')
        mins = f' data-minutes="{d["minutes"]:g}"' if isinstance(d["minutes"], (int, float)) else ""
        date = f' data-date="{esc(d["date"])}"' if d["date"] else ""
        days.append(f'<section data-day="{d["day"]}"{mins} data-week="{d["week"]}"{date}>' + "".join(steps) + "</section>")
    span = c.alloc["modules"][index]
    weeks = f"{span[0]}" if span[0] == span[1] else f"{span[0]}–{span[1]}"
    hours = _num(m["hours"], c.L)
    sub = (f"{W['week']} {weeks} · {hours} h · {len(days)} {W['day'].lower()}" if code == "en"
           else f"{W['week']} {weeks} · {hours} ч · {len(days)} учебни дни")
    head = (f'<header data-top><p><a data-up href="index.html">← {W["all_modules"]}</a> · {esc(c.title)}</p>'
            f'<h1>{esc(m["id"])} · {esc(m["title"])}</h1><p data-sub>{sub}</p></header>')
    return "\n".join([
        _main(c, "module", f' data-module="{esc(m["id"])}"'), head, *days,
        _lesson_html(sections, sources, W), tasks,
        f'<a data-answers href="{esc(m["id"])}-answers.html">{W["answers"]}</a>',
        f'<section data-resources>{"".join(arts.values())}</section>',
        f"<section data-sources>{_sources_html(data, W)}{_glossary_html(data, W)}</section>",
        _next_html(_next_info(c, index, W), W), "</main>"])


def answers_content(c, index) -> str:
    _, W = _lang(c)
    m, data = c.mods[index]
    text = md_to_html(_read(c.course_dir / "modules" / m["slug"] / "answers.md"), _sources_of(data))
    return (_main(c, "answers", f' data-module="{esc(m["id"])}"')
            + f'<header data-top><a data-up href="{esc(m["id"])}.html">← {esc(m["id"])} · {esc(m["title"])}</a></header>'
            + f"<section data-answers>{text}</section></main>")


def module_items(c, index) -> int:
    """How many check boxes the module page has (the index page shows progress with it)."""
    days = _module_days(c, index, {})
    info = _next_info(c, index, _lang(c)[1])
    return sum(len(d["items"]) for d in days) + (1 if info["kind"] == "prompt" and days else 0)


def _list(items):
    return "<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>"


def about_html(c) -> str:
    """section[data-about], "How this course was made": the mode, the programmes the course is
    based on, what was assumed for the learner, what is missing, how each ready module was
    checked, and which sources have limited access or a link that does not open."""
    _, W = _lang(c)
    out = [f"<p>{W['mode_full']}</p>", f"<h3>{W['based_on']}</h3>"]
    programmes = []
    cited = {r for m, _ in c.mods for o in m.get("outcomes") or [] if isinstance(o, dict)
             for r in o.get("benchmark_refs") or []}
    for b in _records(c.benchmarks, "sources"):
        if b.get("id") in cited:
            url, title = _safe_url(b.get("url")), esc(str(b.get("title") or b.get("id") or ""))
            name = f'<a href="{esc(url)}" target="_blank" rel="noopener">{title}</a>' if url else title
            programmes.append(name + (f" · {esc(str(b['author']))}" if b.get("author") else ""))
    out.append(_list(programmes) if programmes else f"<p>{W['no_benchmarks']}</p>")
    assumptions = [esc(str(a)) for a in c.brief.get("assumptions") or [] if str(a).strip()]
    if assumptions:
        out += [f"<h3>{W['assumptions']}</h3>", _list(assumptions)]
    ready = [(m, data) for m, data in c.mods if data.get("status") == "verified"]
    gaps = [f"{esc(m['id'])} · {esc(str(g.get('outcome_id') or '-'))}: {esc(str(g.get('note', '')))}"
            for m, data in ready for g in _records(data, "gaps") if isinstance(g, dict)]
    out += [f"<h3>{W['missing']}</h3>", _list(gaps) if gaps else f"<p>{W['no_gaps']}</p>"]
    if ready:
        out += [f"<h3>{W['review']}</h3>", _list(
            f"{esc(m['id'])} · {esc(m['title'])}: "
            + W["review_independent" if data.get("review") == "independent" else "review_self"]
            for m, data in ready)]
    weak = [f"{m['id']}:{s.get('id')}" for m, data in ready for s in _records(data, "sources")
            if isinstance(s, dict) and (s.get("access") in WEAK_ACCESS
                                        or _dict(s.get("check")).get("status") in BAD_CHECK)]
    out.append(f"<p>{W['weak']}: {len(weak)} ({esc(', '.join(weak))}).</p>" if weak else f"<p>{W['no_weak']}</p>")
    return "<section data-about>" + "".join(out) + "</section>"


def _when(c, span, hours):
    """"Седмици 1–2 · 3,5 ч": where a part of the course falls and how long it takes."""
    label = c.L["week_label"][0 if span[0] == span[1] else 1]
    return f"{label} {format_weeks(span)} · {_num(hours, c.L)} {_lang(c)[1]['hours']}"


def _texts(values):
    return [esc(str(x)) for x in values or [] if isinstance(x, str) and x.strip()]


def _total_html(c, W):
    """The time in total, as the brief set it, and how it splits."""
    budget = c.brief["hours_per_week"] * c.brief["weeks"]
    modules = sum(m["hours"] for m, _ in c.mods)
    capstone = c.course["capstone"]["hours"]
    text = W["total"].format(
        weeks=_count(c.L, c.brief["weeks"], "weeks_word"), days=c.dpw, minutes=_num(round(c.day_min), c.L),
        total=_num(round(budget, 2), c.L), modules=_num(round(modules, 2), c.L),
        capstone=_num(capstone, c.L), reserve=_num(round(budget - modules - capstone, 2), c.L))
    return f"<p>{text}</p>"


def _capstone_plan(c, W):
    """The capstone as the syllabus describes it, shown until capstone.md is written."""
    cap = c.course["capstone"]
    span = c.alloc["capstone"]
    parts = [f"<p><strong>{esc(str(cap['title']))}</strong></p>"]
    if span:
        parts.append(f"<p>{_when(c, span, cap['hours'])}</p>")
    parts.append(f"<p><strong>{W['deliverable']}:</strong> {esc(str(cap['deliverable']))}</p>")
    if isinstance(cap.get("description"), str) and cap["description"].strip():
        parts.append(f"<p>{esc(cap['description'])}</p>")
    return "".join(parts)


def index_content(c, built) -> str:
    """The start page: the whole study plan (each module with its weeks, hours, what it is
    about, its topics and outcomes; the capstone; what stays out; the time in total), the ready
    prompt for the next module and how the course was made. A module not built yet is shown
    open: before the first one is built, this page is what the learner judges the plan by."""
    _, W = _lang(c)
    rows = []
    for i, (m, data) in enumerate(c.mods):
        mid, title = esc(m["id"]), esc(m["title"])
        body = f"<p>{esc(m['summary'])}</p>" if isinstance(m.get("summary"), str) and m["summary"].strip() else ""
        topics = _texts(m.get("topics"))
        if topics:
            body += f"<p><strong>{W['topics']}</strong></p><ol>" + "".join(f"<li>{t}</li>" for t in topics) + "</ol>"
        outcomes = _list(esc(str(o.get("statement", ""))) for o in m.get("outcomes") or [] if isinstance(o, dict))
        body += f"<p><strong>{W['outcomes']}</strong></p>{outcomes}"
        details = (f'<details{"" if i in built else " open"}><summary>'
                   f'{_when(c, c.alloc["modules"][i], m["hours"])}</summary>{body}</details>')
        if i in built:
            rows.append(f'<article data-module="{mid}" data-status="ready" data-href="{mid}.html" '
                        f'data-steps="{module_items(c, i)}"><span class="mid">{mid}</span> '
                        f'<a class="mtitle" href="{mid}.html">{title}</a>{details}</article>')
        else:
            rows.append(f'<article data-module="{mid}" data-status="pending"><span class="mid">{mid}</span> '
                        f'<span class="mtitle">{title}</span> <span class="muted">{W["pending"]}</span>{details}</article>')
    left_out = _texts(c.course.get("out_of_scope"))
    left_out_html = f"<p><strong>{W['out_of_scope']}</strong></p>{_list(left_out)}" if left_out else ""
    prompt = ""
    for i in built:
        info = _next_info(c, i, W)
        if info["kind"] == "prompt":
            prompt = _next_html(info, W)
    cap = _read(c.course_dir / "capstone.md")
    cap_body = md_to_html(cap, {}) if cap.strip() else _capstone_plan(c, W)
    return "\n".join([
        _main(c, "index"),
        f'<header data-top><h1>{esc(c.title)}</h1><p data-sub><strong>{W["goal"]}:</strong> '
        f'{esc(str(c.brief.get("goal", "")))}</p></header>',
        f'<section data-modules><h2>{W["plan"]}</h2>{_total_html(c, W)}{"".join(rows)}{left_out_html}</section>',
        prompt, f'<section data-capstone id="capstone">{cap_body}</section>',
        about_html(c), "</main>"])


def site_pages(c) -> dict[str, str]:
    """Every web page of the course, keyed by its path in the course folder."""
    code, W = _lang(c)
    built = [i for i, (m, data) in enumerate(c.mods)
             if data.get("status") == "verified" and c.days[i][4]]
    pages = {"web/index.html": fill_shell(code, c.title, index_content(c, built))}
    for i in built:
        m = c.mods[i][0]
        pages[f"web/{m['id']}.html"] = fill_shell(code, f"{m['id']} · {m['title']}", module_content(c, i))
        pages[f"web/{m['id']}-answers.html"] = fill_shell(code, f"{W['answers']} · {m['id']}", answers_content(c, i))
    return pages
