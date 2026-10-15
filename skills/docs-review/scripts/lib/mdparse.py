"""Line-oriented Markdown model for GitLab docs pages.

Python 3.9+, stdlib only. Not a full CommonMark parser: it knows what the
deterministic docs checks need, and keeps line and column positions intact.

- Front matter (`---` ... `---`) parsed as flat `key: value` pairs.
- Fenced code blocks (``` and ~~~, at any indent, as GitLab nests them in lists).
- HTML comments, including multi-line ones.
- Disable regions: `<!-- vale off/on -->`, `<!-- markdownlint-disable/enable -->`,
  and `<!-- docs-review-disable [ids] -->` / `<!-- docs-review-enable -->`.
- Headings with Hugo "github" anchors (the docs.gitlab.com default).
- A per-line "prose" view: code spans, URLs, comments, shortcodes, and HTML
  tags are blanked with spaces, so regex columns still match the source line.
"""

import re
import unicodedata

FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
CUSTOM_ID_RE = re.compile(r"\s*\{#([A-Za-z0-9_-]+)[^}]*\}\s*$")
INLINE_CODE_RE = re.compile(r"(`+)(.+?)(?<!`)\1(?!`)")
LINK_RE = re.compile(r"(!?)\[((?:[^\[\]]|\[[^\[\]]*\])*)\]\(\s*<?([^)\s>]*)>?(?:\s+\"[^\"]*\")?\s*\)")
URL_RE = re.compile(r"<?\bhttps?://[^\s)>\]]+>?")
SHORTCODE_RE = re.compile(r"\{\{[<%].*?[>%]\}\}")
HTML_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>")
PLACEHOLDER_RE = re.compile(r"<[a-z][a-z0-9_]*>")
HTML_ANCHOR_RE = re.compile(r"<a\s+[^>]*(?:id|name)=\"([^\"]+)\"", re.I)

# docs_lint.py rule ids that a `markdownlint-disable <rule>` comment also turns off.
MDL_EQUIV = {
    "lint.code-fence-language": {"md040", "fenced-code-language"},
    "lint.code-fence-unclosed": {"md040", "fenced-code-language"},
    "lint.heading-h1": {"md025", "single-title", "single-h1"},
    "lint.heading-duplicate": {"md024", "no-duplicate-heading"},
    "lint.heading-length": {"md013", "line-length"},
}


LEGACY_BADGE_RE = re.compile(r"\s*\*\*\((?:FREE|PREMIUM|ULTIMATE|EXPERIMENT|BETA)\b[^)]*\)\*\*")


def slugify(text):
    """Anchor for a heading, the way Hugo's `github` autoHeadingIDType builds it.

    Lowercase; keep letters, digits, `_`, and `-`; each space becomes `-`;
    drop all other characters. Inline Markdown is stripped first, and so are
    legacy tier badges such as `**(PREMIUM)**`, which the old site removed.
    """
    text = strip_inline_markdown(LEGACY_BADGE_RE.sub("", text))
    out = []
    for ch in text.lower():
        if ch == " ":
            out.append("-")
        elif ch in "-_":
            out.append(ch)
        elif unicodedata.category(ch)[0] in ("L", "N"):
            out.append(ch)
    return "".join(out)


def strip_inline_markdown(text):
    """Visible text of a heading or link: no links, code ticks, emphasis, tags."""
    spans = []

    def keep(m):  # code span content is literal: no tags or emphasis inside
        spans.append(m.group(2).strip())
        return "\x00{}\x00".format(len(spans) - 1)

    text = SHORTCODE_RE.sub("", text)
    text = LINK_RE.sub(lambda m: m.group(2), text)
    text = INLINE_CODE_RE.sub(keep, text)
    text = HTML_TAG_RE.sub("", text)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", text)
    text = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", r"\1", text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return text.strip()


def _blank(s):
    return " " * len(s)


def _blank_inner(m):
    """Keep the delimiters of a code span, blank its content."""
    ticks = m.group(1)
    return ticks + " " * (len(m.group(0)) - 2 * len(ticks)) + ticks


class Heading(object):
    __slots__ = ("line", "level", "raw", "text", "anchor", "custom_id")

    def __init__(self, line, level, raw, text, anchor, custom_id):
        self.line = line
        self.level = level
        self.raw = raw
        self.text = text
        self.anchor = anchor
        self.custom_id = custom_id


class Fence(object):
    __slots__ = ("start", "end", "indent", "marker", "info", "lang", "closed")

    def __init__(self, start, indent, marker, info):
        self.start = start
        self.end = None
        self.indent = indent
        self.marker = marker
        self.info = info.strip()
        self.lang = self.info.split()[0].strip("{}.") if self.info else ""
        self.closed = False


class Doc(object):
    """Parsed page. Line numbers are 1-based everywhere."""

    def __init__(self, text, path=""):
        self.path = path
        self.text = text
        self.lines = text.split("\n")
        if self.lines and self.lines[-1] == "":
            self.lines.pop()
        n = len(self.lines)
        self.front_matter = {}
        self.front_matter_lines = {}  # key -> line number
        self.front_matter_range = None  # (start, end) of the --- lines
        self.fences = []
        self.headings = []
        self.in_fence = [False] * (n + 2)
        self.in_comment = [False] * (n + 2)  # whole line inside an HTML comment
        self.in_front_matter = [False] * (n + 2)
        self.vale_off = [False] * (n + 2)
        self.mdl_off = [False] * (n + 2)
        self.mdl_rules = [None] * (n + 2)  # rule names turned off by `markdownlint-disable MDxxx`
        self.disabled = [None] * (n + 2)  # None, or a set of ids ("*" = all)
        self.prose = [""] * (n + 2)  # masked prose view of each line
        self.html_anchors = set()
        self._parse()

    def line(self, num):
        return self.lines[num - 1] if 1 <= num <= len(self.lines) else ""

    def is_text(self, num):
        """True if the line is Markdown text (not code, comment, or front matter)."""
        return not (self.in_fence[num] or self.in_comment[num] or self.in_front_matter[num])

    def is_disabled(self, num, rule_id, kind):
        """kind: `prose` honors vale off, `markdown` honors markdownlint-disable."""
        if kind == "prose" and self.vale_off[num]:
            return True
        if kind == "markdown" and self.mdl_off[num]:
            return True
        if kind == "markdown" and self.mdl_rules[num] and MDL_EQUIV.get(rule_id, set()) & self.mdl_rules[num]:
            return True
        ids = self.disabled[num]
        if ids:
            if "*" in ids or rule_id in ids:
                return True
            for i in ids:
                if i.endswith("*") and rule_id.startswith(i[:-1]):
                    return True
        return False

    def anchors(self):
        """All anchors on the page, with Hugo's -1, -2 suffixes for duplicates."""
        used = set()
        for h in self.headings:
            if h.custom_id:
                used.add(h.custom_id)
                continue
            anchor, n = h.anchor, 0
            while anchor in used:  # A, A, A-1 -> a, a-1, a-1-1
                n += 1
                anchor = "{}-{}".format(h.anchor, n)
            used.add(anchor)
        return used | set(self.html_anchors)

    def _parse(self):
        lines = self.lines
        n = len(lines)
        i = 1
        # Front matter.
        if n and lines[0].strip() == "---":
            for j in range(2, n + 1):
                if lines[j - 1].strip() == "---":
                    self.front_matter_range = (1, j)
                    for k in range(1, j + 1):
                        self.in_front_matter[k] = True
                    self._parse_front_matter(2, j - 1)
                    i = j + 1
                    break
        fence = None
        comment_open = False
        vale_off = mdl_off = False
        mdl_rules = set()
        disabled = None
        for num in range(i, n + 1):
            raw = lines[num - 1]
            if fence is not None:
                self.in_fence[num] = True
                m = FENCE_RE.match(raw)
                if m and m.group(2)[0] == fence.marker[0] and len(m.group(2)) >= len(fence.marker) \
                        and not m.group(3).strip():
                    fence.end = num
                    fence.closed = True
                    fence = None
                continue
            if not comment_open:
                m = FENCE_RE.match(raw)
                if m and not (m.group(2)[0] == "`" and "`" in m.group(3)):
                    fence = Fence(num, len(m.group(1)), m.group(2), m.group(3))
                    self.fences.append(fence)
                    self.in_fence[num] = True
                    continue
            # Comments and directives on this line.
            masked = raw
            pos = 0
            line_all_comment = comment_open
            out = []
            while pos < len(raw):
                if comment_open:
                    end = raw.find("-->", pos)
                    body = raw[pos:end if end >= 0 else len(raw)]
                    out.append(_blank(body))
                    if end < 0:
                        pos = len(raw)
                        break
                    out.append("   ")
                    pos = end + 3
                    comment_open = False
                    continue
                start = raw.find("<!--", pos)
                if start < 0:
                    out.append(raw[pos:])
                    break
                out.append(raw[pos:start])
                end = raw.find("-->", start + 4)
                body = raw[start + 4:end if end >= 0 else len(raw)].strip()
                directive = body.lower()
                if directive == "vale off":
                    vale_off = True
                elif directive == "vale on":
                    vale_off = False
                elif directive.startswith("markdownlint-disable") and "line" not in directive \
                        and "next" not in directive and "file" not in directive:
                    names = body.split()[1:]
                    if names:
                        mdl_rules |= {x.lower() for x in names}
                    else:
                        mdl_off = True
                elif directive.startswith("markdownlint-enable"):
                    names = body.split()[1:]
                    if names:
                        mdl_rules -= {x.lower() for x in names}
                    else:
                        mdl_off = False
                        mdl_rules = set()
                elif directive.startswith("markdownlint-disable-file"):
                    mdl_off = True
                elif directive.startswith("docs-review-disable"):
                    ids = body.split()[1:]
                    disabled = set(ids) if ids else {"*"}
                elif directive.startswith("docs-review-enable"):
                    disabled = None
                if end < 0:
                    out.append(_blank(raw[start:]))
                    comment_open = True
                    pos = len(raw)
                else:
                    out.append(_blank(raw[start:end + 3]))
                    pos = end + 3
            masked = "".join(out)
            if line_all_comment and not masked.strip():
                self.in_comment[num] = True
            elif not masked.strip() and raw.strip().startswith("<!--"):
                self.in_comment[num] = True
            self.vale_off[num] = vale_off
            self.mdl_off[num] = mdl_off
            self.mdl_rules[num] = frozenset(mdl_rules) if mdl_rules else None
            self.disabled[num] = disabled
            self.prose[num] = self._mask_prose(masked)
            for a in HTML_ANCHOR_RE.findall(masked):
                self.html_anchors.add(a)
            if self.in_comment[num]:
                continue
            hm = HEADING_RE.match(masked)
            if hm and not raw.startswith("    "):
                level = len(hm.group(1))
                text = hm.group(2)
                cid = None
                cm = CUSTOM_ID_RE.search(text)
                if cm:
                    cid = cm.group(1)
                    text = text[:cm.start()]
                self.headings.append(Heading(num, level, raw, strip_inline_markdown(text),
                                             slugify(text), cid))

    def _parse_front_matter(self, start, end):
        key = None
        for num in range(start, end + 1):
            raw = self.lines[num - 1]
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", raw)
            if m:
                key = m.group(1)
                self.front_matter[key] = _unquote(m.group(2))
                self.front_matter_lines[key] = num
            elif key and raw.startswith((" ", "\t")) and raw.strip():
                prev = self.front_matter.get(key) or ""
                if prev in (">", "|", ">-", "|-"):
                    prev = ""
                self.front_matter[key] = (prev + " " + _unquote(raw.strip())).strip()

    @staticmethod
    def _mask_prose(line):
        line = INLINE_CODE_RE.sub(_blank_inner, line)
        line = SHORTCODE_RE.sub(lambda m: _blank(m.group(0)), line)

        def link(m):
            whole = m.group(0)
            tgt_start = whole.rfind("(")
            return whole[:tgt_start + 1] + _blank(whole[tgt_start + 1:-1]) + ")"

        line = LINK_RE.sub(link, line)
        line = URL_RE.sub(lambda m: _blank(m.group(0)), line)
        line = HTML_TAG_RE.sub(lambda m: _blank(m.group(0)), line)
        line = PLACEHOLDER_RE.sub(lambda m: _blank(m.group(0)), line)
        return line

    def sections(self):
        """[(heading or None, start_line, end_line)] covering the body."""
        body_start = self.front_matter_range[1] + 1 if self.front_matter_range else 1
        out = []
        prev_line, prev_h = body_start, None
        for h in self.headings:
            out.append((prev_h, prev_line, h.line - 1))
            prev_h, prev_line = h, h.line
        out.append((prev_h, prev_line, len(self.lines)))
        return [s for s in out if s[2] >= s[1]]

    def links(self):
        """Yield (line, col, is_image, text, target) for inline links in text lines."""
        for num in range(1, len(self.lines) + 1):
            if not self.is_text(num):
                continue
            raw = self.lines[num - 1]
            code_masked = INLINE_CODE_RE.sub(_blank_inner, raw)
            code_masked = re.sub(r"<!--.*?-->", lambda m: _blank(m.group(0)), code_masked)
            for m in LINK_RE.finditer(code_masked):
                yield num, m.start(), bool(m.group(1)), m.group(2), m.group(3)


def _unquote(v):
    v = v.strip()
    if len(v) >= 2 and v[0] in "'\"" and v[-1] == v[0]:
        return v[1:-1]
    return v


def parse_file(path, display=None):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return Doc(fh.read(), display or path)
