"""Does a web page follow the page contract (references/page-format.md)? check_page lists every
broken rule in plain words; an empty list means the page follows the contract. Used by
`aiu page-check`, by the tests, and by a light-mode run that can start Python."""
import re
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from .render import GENERATED_MARK

PAGES = {"module", "index", "answers"}
MODES = {"full", "light"}
STEPS = {"video", "reading", "lesson", "task", "other"}
NEXT_KINDS = {"prompt", "link", "pending", "capstone"}
VERIFIED = {"true", "false"}
_PAGE_FILE = re.compile(r"[\w.-]+\.html(#.*)?")
_SLOTS = ("{{AIU_", "<!-- AIU:CONTENT -->")
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
# The content is data: it may not run code, load outside files, carry forms or drawings (which hold
# addresses and parse differently), or use an element whose text a browser reads as raw text.
_NOT_IN_CONTENT = {"script", "iframe", "object", "embed", "link", "style", "base", "meta", "frame", "frameset",
                   "form", "svg", "math", "template", "noscript", "applet", "portal", "textarea", "title",
                   "xmp", "plaintext", "noembed", "noframes"}
_LINK_ATTRS = {"href", "xlink:href", "action", "formaction", "poster", "cite", "background", "ping",
               "longdesc", "usemap", "codebase", "manifest", "archive", "profile", "data-url"}
_SRC_ATTRS = {"src", "srcset", "lowsrc", "dynsrc"}
# In the content every "<" opens a start or an end tag; anything else (a comment, <!, <?, "< ") is
# where a browser and this parser can disagree, and a literal "<" is written "&lt;".
_LOOSE_LT = re.compile(r"<(?![A-Za-z]|/[A-Za-z])")
_TAG = re.compile(r"<[A-Za-z][^>]*>")
_ON_ATTR = re.compile(r"""[\s"'/]on[a-z-]+\s*=""", re.IGNORECASE)
_SKILL = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def _skeletons():
    """The shell and the plain skeleton as patterns: everything outside the three slots is fixed,
    character for character (aiu render may put its own mark above the doctype)."""
    texts = []
    try:
        texts.append((_SKILL / "assets" / "page-shell.html").read_text(encoding="utf-8"))
    except OSError:
        pass
    try:
        fmt = (_SKILL / "references" / "page-format.md").read_text(encoding="utf-8")
        texts.append(fmt.split("## Plain page")[1].split("```html")[1].split("```")[0].strip())
    except (OSError, IndexError):
        pass
    patterns = []
    for text in texts:
        pat = re.escape(text.replace("\r\n", "\n"))
        pat = pat.replace(re.escape("{{AIU_LANG}}"), r"(?P<lang>[A-Za-z]{2,3}(?:-[A-Za-z0-9]{1,8})*)", 1)
        pat = pat.replace(re.escape("{{AIU_TITLE}}"), r"(?P<title>[^<]*)", 1)
        pat = pat.replace(re.escape("<!-- AIU:CONTENT -->"), r"(?P<content>.*)", 1)
        patterns.append(re.compile(r"\s*(?:" + re.escape(GENERATED_MARK) + r"\s*)?" + pat + r"\s*", re.DOTALL))
    return patterns


class _Elements(HTMLParser):
    """Every start tag with its attributes and the index of the element it sits in, the text of
    each pre[data-prompt], and whether any text stands outside every element."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements, self.parents, self.prompts, self._prompt, self._open = [], [], [], None, []
        self.loose_text = False

    def _add(self, tag, attrs, opens):
        a = {k: (v or "") for k, v in attrs}
        self.parents.append(self._open[-1] if self._open else None)
        self.elements.append((tag, a))
        if opens and tag not in _VOID:
            self._open.append(len(self.elements) - 1)
        return a

    def handle_starttag(self, tag, attrs):
        a = self._add(tag, attrs, True)
        if tag == "pre" and "data-prompt" in a:
            self._prompt = []

    def handle_startendtag(self, tag, attrs):
        self._add(tag, attrs, False)

    def handle_data(self, data):
        if self._prompt is not None:
            self._prompt.append(data)
        if not self._open and data.strip():
            self.loose_text = True

    def handle_endtag(self, tag):
        for i in range(len(self._open) - 1, -1, -1):   # close up to the matching open element
            if self.elements[self._open[i]][0] == tag:
                del self._open[i:]
                break
        if tag == "pre" and self._prompt is not None:
            self.prompts.append("".join(self._prompt).strip())
            self._prompt = None


def _web(url: str) -> bool:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return False
    return parts.scheme.lower() in ("http", "https") and bool(parts.netloc)


def _link_ok(url: str) -> bool:
    url = url.strip()
    return _web(url) or url.startswith("#") or bool(_PAGE_FILE.fullmatch(url))


def check_page(html_text: str) -> list[str]:
    problems = []
    say = problems.append
    for slot in _SLOTS:
        if slot in html_text:
            say(f"the shell slot {slot}... is still unfilled (AIU placeholder)")
    if "\x00" in html_text:
        say("the page holds a null character: remove it")
    page_text = html_text.replace("\r\n", "\n")
    found = next((m for m in (p.fullmatch(page_text) for p in _skeletons()) if m), None)
    if found is None:
        say("the page is not the shell or the plain skeleton with only their three slots filled: outside "
            "main#aiu nothing may be added or changed, the shell's script included")
        return problems
    content = found.group("content")
    if _LOOSE_LT.search(content):
        say("the content holds a \"<\" that opens no tag, such as a comment (<!-- -->) or another <! or <? "
            "declaration: a browser and this check can read those differently and hide code in them; "
            "write \"&lt;\" for a literal \"<\"")
    if any(_ON_ATTR.search(tag) for tag in _TAG.findall(content)):
        say("a tag in the content has an on… attribute, which runs code: remove it")
    if not content.strip().endswith("</main>"):
        say("the content must end with </main>: a tag left open at its end runs on into the shell's text "
            "in the browser")
    parser = _Elements()
    parser.feed(content)
    if parser.rawdata.strip():   # something the parser could not finish, e.g. an unclosed tag
        say("the content ends in the middle of a tag or a declaration: close it before </main>")
    parser.close()
    els = parser.elements
    mains = [i for i, (tag, a) in enumerate(els) if tag == "main" and a.get("id") == "aiu"]
    if len(mains) != 1:
        say(f"the page needs exactly one <main id=\"aiu\">, found {len(mains)}")
        return problems
    main = els[mains[0]][1]
    if parser.loose_text or [i for i, p in enumerate(parser.parents) if p is None] != [mains[0]]:
        say("the content must be exactly one <main id=\"aiu\">: nothing may stand outside it")

    for tag, a in els:
        if tag in _NOT_IN_CONTENT:
            say(f"the content holds a <{tag}> element: the page must work alone and run only the shell's script")
        for name, value in a.items():
            if name.startswith("on"):
                say(f"attribute {name} runs code: remove it")
            if name in _LINK_ATTRS and not _link_ok(value):
                say(f"{name} {value!r} is not a web address, a #jump or a neighbouring .html page")
            if name in _SRC_ATTRS and not value.strip().lower().startswith("data:"):
                say(f"{name} {value!r} loads an outside file: the page must be self-contained")
            if name == "style":
                say("the content holds a style attribute: the shell styles the page, and CSS can load "
                    "outside files; remove it")
    page, mode = main.get("data-page"), main.get("data-mode")
    if page not in PAGES:
        say(f"main#aiu data-page must be one of {sorted(PAGES)}, not {page!r}")
    if mode not in MODES:
        say(f"main#aiu data-mode must be one of {sorted(MODES)}, not {mode!r}")
    for attr in ("data-course", "data-lang"):
        if not main.get(attr, "").strip():
            say(f"main#aiu needs a non-empty {attr}")

    def having(attr, tag=None):
        return [a for t, a in els if attr in a and (tag is None or t == tag)]

    if page == "module":
        if not main.get("data-module", "").strip():
            say("a module page needs data-module on main#aiu")
        days = having("data-day", "section")
        if not days:
            say("a module page needs at least one section[data-day]")
        for d in days:
            if not d.get("data-minutes", "").strip():
                say(f"section[data-day={d.get('data-day')!r}] needs data-minutes")
        numbers = [d.get("data-day") for d in days]
        for n in sorted({n for n in numbers if numbers.count(n) > 1}):
            say(f"data-day {n!r} is used by more than one day")
        day_ids = {i for i, (tag, a) in enumerate(els) if tag == "section" and "data-day" in a}
        for i, (tag, a) in enumerate(els):
            if parser.parents[i] in day_ids and "data-step" not in a:
                day = els[parser.parents[i]][1].get("data-day")
                say(f"section[data-day={day!r}] holds a <{tag}>, which is not a step: a day holds only "
                    f"[data-step] elements, and the page drops anything else")
        for part in ("data-lesson", "data-tasks"):
            if not having(part, "section"):
                say(f"a module page needs section[{part}]")
    for a in having("data-step"):
        if a["data-step"] not in STEPS:
            say(f"data-step must be one of {sorted(STEPS)}, not {a['data-step']!r}")
    ids = [a["id"] for _, a in els if "id" in a]
    seen = set()
    for i in ids:
        if i in seen:
            say(f"the id {i!r} is used more than once")
        seen.add(i)
    for a in having("data-ref"):
        for ref in a["data-ref"].split():
            if ref not in seen:
                say(f"data-ref names {ref!r}, but no element has that id")
    for a in having("data-kind", "article"):
        if a["data-kind"] != "video":
            continue
        where = f"video {a.get('id', '')!r}"
        if not _web(a.get("data-url", "")):
            say(f"{where} needs an http(s) data-url")
        if a.get("data-verified") not in VERIFIED:
            say(f"{where}: data-verified must be \"true\" or \"false\", not {a.get('data-verified')!r}")
        elif a["data-verified"] == "true" and not a.get("data-from", "").strip():
            say(f"{where} is verified but has no data-from (its start)")
        elif a["data-verified"] == "false" and (a.get("data-from") or a.get("data-to")):
            say(f"{where} is not verified but has data-from or data-to: minutes come only from text that was read")
    for a in having("data-next", "section"):
        kind = a.get("data-kind")
        if kind not in NEXT_KINDS:
            say(f"section[data-next] data-kind must be one of {sorted(NEXT_KINDS)}, not {kind!r}")
        elif kind == "prompt" and not any(parser.prompts):
            say("section[data-next] of kind prompt needs a non-empty pre[data-prompt]")
    if mode == "light" and not having("data-about", "section"):
        say("a light-mode page needs section[data-about] (how the course was made, what was not checked)")
    return problems
