"""Page text extraction and link checking."""
import re
from urllib.parse import urlparse

USER_AGENT = "Mozilla/5.0 (compatible; course-builder/1.0)"
FULL_TEXT_MIN = 1500
ABSTRACT_MIN = 200

_JUNK_TAGS = ("script", "style", "nav", "header", "footer", "aside", "form", "noscript")


def default_http_get(url: str, timeout: int = 20):
    import requests
    return requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT}, allow_redirects=True)


def extract_text(html: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    title = re.sub(r"\s+", " ", title).strip()
    for tag in soup.find_all(_JUNK_TAGS):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    text = re.sub(r"\s+", " ", root.get_text(" ")).strip()
    return title, text


def classify_access(status_code: int | None, content_type: str, text_len: int) -> str:
    if status_code is None or status_code >= 400:
        return "unavailable"
    if "application/pdf" in (content_type or "").lower():
        return "original_saved"
    if text_len >= FULL_TEXT_MIN:
        return "full_text"
    if text_len >= ABSTRACT_MIN:
        return "abstract_only"
    return "metadata_only"


def _content_type(resp) -> str:
    headers = getattr(resp, "headers", None) or {}
    for key in headers:  # works for plain dicts and case-insensitive requests headers
        if str(key).lower() == "content-type":
            return headers[key] or ""
    return ""


def _page_text(resp, ctype: str) -> str:
    """The page as text. requests decodes a text/* body without a header charset as
    ISO-8859-1, which turns UTF-8 and windows-1251 pages into mojibake; in that case
    decode the bytes ourselves: the page's own <meta> declaration, else UTF-8 if the
    bytes are valid UTF-8, else the encoding requests detects from the bytes. A UTF-16
    byte-order mark beats everything, the header included, as it does in browsers."""
    body = resp.content or b""
    if isinstance(body, bytes) and body[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return body.decode("utf-16")
        except UnicodeDecodeError:
            pass
    if "charset=" in ctype.lower():
        return resp.text
    from bs4.dammit import EncodingDetector
    declared = EncodingDetector.find_declared_encoding(body, is_html=True)
    for encoding in (declared, "utf-8-sig"):
        if encoding:
            try:
                return body.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                continue
    return body.decode(getattr(resp, "apparent_encoding", None) or "utf-8", errors="replace")


def _is_pdf(body: bytes) -> bool:
    """A PDF file starts with %PDF- (readers tolerate a little leading junk)."""
    return isinstance(body, bytes) and body[:1024].lstrip().startswith(b"%PDF-")


def fetch_source(url: str, http_get=None) -> dict:
    http_get = http_get or default_http_get
    result = {"access": "unavailable", "title": "", "text": "", "content_type": "",
              "http": None, "pdf_bytes": None}
    try:
        resp = http_get(url, 20)
    except Exception:
        return result
    ctype = _content_type(resp)
    result["http"] = resp.status_code
    result["content_type"] = ctype
    if resp.status_code is not None and resp.status_code >= 400:
        return result
    claims_pdf = "application/pdf" in ctype.lower() or urlparse(url).path.lower().endswith(".pdf")
    if claims_pdf:
        if _is_pdf(resp.content):
            result["access"] = "original_saved"
            result["pdf_bytes"] = resp.content
            return result
        if "html" not in ctype.lower():
            return result   # said PDF, is not one: nothing readable was received
        # a PDF link that answered with an HTML page (login, consent): read it as a page
    title, text = extract_text(_page_text(resp, ctype))
    result["title"], result["text"] = title, text
    result["access"] = classify_access(resp.status_code, ctype, len(text))
    return result


def check_url(url: str, http_get=None) -> dict:
    http_get = http_get or default_http_get
    resp, cert_failed = None, False
    for _ in range(2):
        try:
            resp = http_get(url, 20)
            break
        except Exception as exc:  # noqa: BLE001 - any failure means no answer this time
            # a certificate the script cannot verify is not a dead site: browsers usually
            # open it (an incomplete chain), so it counts like a site that refuses scripts
            cert_failed = (cert_failed or "SSLError" in type(exc).__name__
                           or "certificate verify failed" in str(exc))
            continue
    if resp is None:
        return {"status": "blocked" if cert_failed else "unreachable", "http": None}
    code = resp.status_code
    if 200 <= code <= 399:
        status = "ok"
    elif code in (401, 403, 429):
        status = "blocked"
    elif code in (404, 410):
        status = "dead"
    else:
        status = "unreachable"
    return {"status": status, "http": code}


def check_youtube(video_id: str, http_get=None) -> dict:
    http_get = http_get or default_http_get
    url = ("https://www.youtube.com/oembed?url="
           f"https://www.youtube.com/watch?v={video_id}&format=json")
    try:
        code = http_get(url, 20).status_code
    except Exception:
        return {"status": "unreachable", "http": None}
    if code == 200:
        status = "ok"
    elif code in (401, 403):
        status = "blocked"
    elif code in (400, 404):
        status = "dead"
    else:
        status = "unreachable"
    return {"status": status, "http": code}


WEB_PROBE = "https://example.org/"


def check_web(opener=None) -> dict:
    """Does the network answer at all? Asks a plain site with the standard library, so it works
    before the packages are installed. Any HTTP answer, an error code too, means the network is
    up; no answer means it is not. `aiu doctor --online` tells this apart from YouTube refusing."""
    import http.client
    import ssl
    import urllib.error
    import urllib.request

    def default(url, timeout):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        return urllib.request.urlopen(request, timeout=timeout)   # noqa: S310 - a fixed https address

    try:
        answer = (opener or default)(WEB_PROBE, 10)
    except urllib.error.HTTPError as exc:
        return {"status": "ok", "http": exc.code}
    except urllib.error.URLError as exc:
        # A certificate this Python cannot check (no CA files installed) is still an answer.
        return {"status": "ok" if isinstance(exc.reason, ssl.SSLError) else "unreachable", "http": None}
    except (ssl.SSLError, http.client.HTTPException):   # something answered, if not cleanly
        return {"status": "ok", "http": None}
    except (OSError, ValueError):   # TimeoutError is an OSError: no answer
        return {"status": "unreachable", "http": None}
    code = getattr(answer, "status", None)
    if hasattr(answer, "close"):
        answer.close()
    return {"status": "ok", "http": code}
