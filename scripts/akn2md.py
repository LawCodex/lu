"""Convert a Legilux Akoma Ntoso (CSD13 + scl: extensions) document to Markdown."""
from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass, field

from lxml import etree

SCL = "http://www.scl.lu"
MATHML = "http://www.w3.org/1998/Math/MathML"
LEGILUX = "https://legilux.public.lu"

# hierarchical containers rendered as headings
HIER = {
    "book", "part", "subpart", "title", "subtitle", "chapter", "subchapter", "section",
    "subsection", "division", "subdivision", "tome", "level", "hcontainer", "container",
}
BLOCK_SKIP = {"meta", "eop", "notes", "toc"}
INLINE_TAGS = {
    "b", "i", "u", "sup", "sub", "span", "ref", "noteRef", "br", "mod", "del", "ins",
    "docNumber", "docDate", "docTitle", "docType", "shortTitle", "person", "date", "term", "def",
    "abbr", "inline", "marker", "img", "quotedText", "eventRef", "passiveRef", "signature",
    "organization", "role", "location", "entity", "affectedDocument", "docProponent", "object",
    "math", "formula", "omissis", "a", "strong", "em", "font", "subFlow", "embeddedText",
    "concept", "legislature", "session", "docStatus", "docAuthority", "docCommittee",
    "relatedDocument", "vote", "outcome", "recordedTime", "process", "argument",
}


def lname(e) -> str:
    if not isinstance(e.tag, str):
        return ""
    return etree.QName(e).localname


def ns(e) -> str:
    return etree.QName(e).namespace or "" if isinstance(e.tag, str) else ""


def norm_ws(s: str) -> str:
    return re.sub(r"[ \t\r\n ]+", lambda m: " " if m.group(0) == " " else " ", s)


def clean_inline(s: str) -> str:
    s = re.sub(r"[ \t\r\n]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"^(\s*<br>\s*)+|(\s*<br>\s*)+$", "", s)
    s = re.sub(r"(\s*<br>\s*){2,}", " <br> ", s)
    return s.strip()


MD_START = re.compile(r"^(\d+[.)]\s|[-+*>#|]|=+\s*$|`{3})")


def esc_start(s: str) -> str:
    if MD_START.match(s):
        return "\\" + s
    return s


@dataclass
class Ctx:
    notes: dict = field(default_factory=dict)      # id -> label
    note_text: dict = field(default_factory=dict)  # label -> md
    used_notes: list = field(default_factory=list)
    images: list = field(default_factory=list)     # (name, bytes)
    image_prefix: str = ""                          # relative path for links
    in_table: bool = False


def absurl(href: str) -> str:
    href = (href or "").strip()
    if href.startswith("/eli/"):
        return LEGILUX + href
    if href.startswith("http://data.legilux.public.lu/eli/"):
        return LEGILUX + href[len("http://data.legilux.public.lu"):]
    return href


class Converter:
    def __init__(self, ctx: Ctx):
        self.ctx = ctx

    # ------------------------------------------------------------------ inline
    def inline(self, e, top=True) -> str:
        """Render the content of e (text + children) as inline markdown."""
        out = [e.text or ""] if top else []
        for c in e:
            out.append(self.inline_el(c))
            out.append(c.tail or "")
        return "".join(out)

    def inline_el(self, c) -> str:
        if not isinstance(c.tag, str):
            return ""
        if ns(c) == SCL:
            return ""
        t = lname(c)
        if ns(c) == MATHML:
            return self.math(c)
        inner = lambda: self.inline(c)  # noqa: E731
        if t == "signature":
            return " <br>" + inner() + " <br>"
        if t == "br":
            return "<br>"
        if t in ("b", "strong"):
            s = inner()
            return wrap(s, "**")
        if t in ("i", "em"):
            return wrap(inner(), "*")
        if t == "sup":
            s = inner().strip()
            return f"<sup>{s}</sup>" if s else ""
        if t == "sub":
            s = inner().strip()
            return f"<sub>{s}</sub>" if s else ""
        if t == "ref":
            s = inner()
            href = absurl(c.get("href"))
            if href and s.strip() and href.startswith("http"):
                return f"[{s.strip()}]({href})" if s == s.strip() else \
                    (" " if s[:1].isspace() else "") + f"[{s.strip()}]({href})" + (" " if s[-1:].isspace() else "")
            return s
        if t == "noteRef":
            nid = (c.get("href") or "").lstrip("#")
            label = self.ctx.notes.get(nid)
            if label:
                if label not in self.ctx.used_notes:
                    self.ctx.used_notes.append(label)
                return f"[^{label}]"
            return ""
        if t == "img":
            return self.image(c)
        if t in ("p", "content", "alinea", "li", "blockList", "item", "listIntroduction",
                 "listWrapUp", "ol", "ul", "table", "tr", "td", "th", "heading", "num",
                 "subheading", "paragraph", "intro", "wrapUp", "tblock", "blockContainer",
                 "crossHeading", "embeddedStructure", "quotedStructure", "article", "list"):
            # block inside inline context: flatten
            return " " + self.inline(c) + " "
        return inner()

    def math(self, e) -> str:
        t = lname(e)
        if t == "mfrac":
            kids = [self.math(k) for k in e if isinstance(k.tag, str)]
            if len(kids) == 2:
                return f"({kids[0]})/({kids[1]})"
        if t == "msup":
            kids = [self.math(k) for k in e if isinstance(k.tag, str)]
            if len(kids) == 2:
                return f"{kids[0]}<sup>{kids[1]}</sup>"
        if t == "msub":
            kids = [self.math(k) for k in e if isinstance(k.tag, str)]
            if len(kids) == 2:
                return f"{kids[0]}<sub>{kids[1]}</sub>"
        s = e.text or ""
        for k in e:
            s += self.math(k) if isinstance(k.tag, str) else ""
            s += k.tail or ""
        return s

    def image(self, c) -> str:
        src = c.get("src") or ""
        m = re.match(r"data:image/([a-zA-Z0-9.+-]+);base64,(.*)", src, re.S)
        if m:
            ext = {"jpeg": "jpg", "svg+xml": "svg"}.get(m.group(1).lower(), m.group(1).lower())
            try:
                data = base64.b64decode(re.sub(r"\s+", "", m.group(2)))
            except Exception:  # noqa: BLE001
                return "*[image]*"
            name = hashlib.sha1(data).hexdigest()[:16] + "." + ext
            self.ctx.images.append((name, data))
            return f"![image]({self.ctx.image_prefix}{name[:2]}/{name})"
        if src:
            return f"![image]({absurl(src)})"
        return "*[image]*"

    def text(self, e) -> str:
        return clean_inline(self.inline(e))

    # ------------------------------------------------------------------ blocks
    def blocks(self, e, level: int, quoted=False) -> list[str]:
        """Render children of e as a list of markdown blocks."""
        out: list[str] = []
        lead = clean_inline(e.text or "")
        if lead:
            out.append(esc_start(lead))
        pending_inline = []

        def flush():
            if pending_inline:
                s = clean_inline("".join(pending_inline))
                if s:
                    out.append(esc_start(s))
                pending_inline.clear()

        for c in e:
            if not isinstance(c.tag, str) or ns(c) == SCL:
                if isinstance(c.tag, str):
                    tail = c.tail or ""
                    if tail.strip():
                        pending_inline.append(tail)
                continue
            t = lname(c)
            if t in INLINE_TAGS or ns(c) == MATHML:
                pending_inline.append(self.inline_el(c))
                pending_inline.append(c.tail or "")
                continue
            flush()
            out.extend(self.block(c, level, quoted))
            tail = clean_inline(c.tail or "")
            if tail:
                out.append(esc_start(tail))
        flush()
        return out

    def num_heading(self, e) -> tuple[str, str]:
        num = e.find("{*}num")
        head = e.find("{*}heading")
        sub = e.find("{*}subheading")
        n = self.text(num) if num is not None else ""
        h = self.text(head) if head is not None else ""
        if sub is not None:
            s = self.text(sub)
            if s:
                h = f"{h} — {s}" if h else s
        n = strip_bold(n)
        h = strip_bold(h)
        return n, h

    def heading_line(self, level: int, text: str) -> str:
        text = re.sub(r"\s*<br>\s*", " ", text.replace("\n", " ")).strip()
        if level <= 6:
            return "#" * level + " " + text
        return f"**{text}**"

    def block(self, c, level: int, quoted=False) -> list[str]:
        t = lname(c)
        if t in BLOCK_SKIP:
            return []
        if t in ("num", "heading", "subheading"):
            return []  # consumed by the parent
        if t in HIER and not quoted:
            n, h = self.num_heading(c)
            title = " — ".join(x for x in (n.rstrip(" .") if h else n, h) if x) or ""
            out = [self.heading_line(level, title)] if title else []
            out += self.blocks(c, level + 1 if title else level)
            return out
        if t == "article":
            n, h = self.num_heading(c)
            title = " — ".join(x for x in (n.rstrip(" .") if h else n, h) if x)
            if quoted:
                out = [f"**{title}**"] if title else []
            else:
                out = [self.heading_line(max(level, 2), title)] if title else []
            return out + self.blocks(c, level + 1, quoted)
        if t == "ol" or t == "ul" or t == "blockList" or t == "list":
            return self.list_block(c, level, quoted, ordered=(t == "ol"))
        if t == "table":
            return [self.table(c)]
        if t in ("embeddedStructure", "quotedStructure"):
            inner = self.blocks(c, level, quoted=True)
            return [blockquote(b) for b in inner]
        if t in ("paragraph", "subparagraph", "point", "indent", "clause", "alinea", "item",
                 "subclause", "subpoint", "subsubpoint", "level"):
            n, h = self.num_heading(c)
            inner = self.blocks(c, level, quoted)
            prefix = " ".join(x for x in (n, f"**{h}**" if h else "") if x)
            if prefix:
                if inner and not inner[0].startswith(("#", "|", "<table", ">", "- ", "**")):
                    inner[0] = esc_start(prefix + " " + inner[0].lstrip("\\"))
                else:
                    inner.insert(0, esc_start(prefix))
            return inner
        if t == "p":
            s = self.text(c)
            return [esc_start(s)] if s else []
        if t in ("attachments", "components"):
            return self.blocks(c, level, quoted)
        if t in ("attachment", "component", "doc", "interstitial"):
            return self.blocks(c, level, quoted)
        if t in ("preface", "preamble", "conclusions", "mainBody", "body", "content",
                 "intro", "wrapUp", "listIntroduction", "listWrapUp", "tblock",
                 "blockContainer", "formula", "citations", "citation", "recitals", "recital",
                 "longTitle", "container", "tocItem", "subFlow", "foreign", "div", "td", "th",
                 "act", "akomaNtoso", "coverPage", "scl"):
            if t == "tocItem":
                s = self.text(c)
                return [esc_start(s)] if s else []
            return self.blocks(c, level, quoted)
        if t == "crossHeading":
            s = self.text(c)
            return [f"**{s}**"] if s else []
        if t == "li":
            return self.blocks(c, level, quoted)
        # unknown: render children
        return self.blocks(c, level, quoted)

    def list_block(self, c, level, quoted, ordered) -> list[str]:
        out = []
        items = [k for k in c if isinstance(k.tag, str) and lname(k) in ("li", "item", "point")]
        others_first = []
        for k in c:
            if not isinstance(k.tag, str) or ns(k) == SCL:
                continue
            if lname(k) in ("listIntroduction", "intro"):
                others_first += self.blocks(k, level, quoted)
        out += others_first
        for i, li in enumerate(items, 1):
            inner = self.blocks(li, level, quoted)
            if not inner:
                continue
            marker = f"{i}. " if ordered and not li.get("value") else "- "
            body = "\n\n".join(inner)
            body = body.replace("\n", "\n  " + (" " if marker.startswith(tuple("0123456789")) else ""))
            first = inner[0]
            out.append(marker + body.lstrip("\\") if not first.startswith("\\") else marker + body[1:])
        for k in c:
            if isinstance(k.tag, str) and lname(k) in ("listWrapUp", "wrapUp"):
                out += self.blocks(k, level, quoted)
        # join consecutive list items into one block (tight list)
        merged, cur = [], []
        for b in out:
            if b.startswith(("- ",)) or re.match(r"^\d+\. ", b):
                cur.append(b)
            else:
                if cur:
                    merged.append("\n".join(cur))
                    cur = []
                merged.append(b)
        if cur:
            merged.append("\n".join(cur))
        return merged

    def table(self, tbl) -> str:
        rows = [r for r in tbl.iter("{*}tr")]
        simple = True
        grid = []
        for r in rows:
            cells = [c for c in r if isinstance(c.tag, str) and lname(c) in ("td", "th")]
            for c in cells:
                if c.get("colspan") not in (None, "1") or c.get("rowspan") not in (None, "1"):
                    simple = False
                if c.find(".//{*}table") is not None:
                    simple = False
            grid.append(cells)
        widths = {len(r) for r in grid if r}
        if len(widths) > 1:
            simple = False
        self.ctx.in_table = True
        try:
            if simple and grid and widths:
                lines = []
                for i, cells in enumerate(grid):
                    vals = [self.cell_text(c).replace("|", "\\|") for c in cells]
                    lines.append("| " + " | ".join(vals) + " |")
                    if i == 0:
                        lines.append("|" + "|".join(["---"] * len(cells)) + "|")
                return "\n".join(lines)
            # complex table: HTML
            parts = ["<table>"]
            for cells in grid:
                parts.append("<tr>")
                for c in cells:
                    tag = lname(c)
                    attrs = ""
                    for a in ("colspan", "rowspan"):
                        if c.get(a) not in (None, "1"):
                            attrs += f' {a}="{c.get(a)}"'
                    parts.append(f"<{tag}{attrs}>{self.cell_text(c, html=True)}</{tag}>")
                parts.append("</tr>")
            parts.append("</table>")
            return "\n".join(parts)
        finally:
            self.ctx.in_table = False

    def cell_text(self, c, html=False) -> str:
        if c.find(".//{*}table") is not None and html:
            # nested table: render the nested ones inline as HTML
            bits = []
            for k in c:
                if isinstance(k.tag, str) and lname(k) == "table":
                    bits.append(self.table(k))
                    self.ctx.in_table = True
                elif isinstance(k.tag, str):
                    s = clean_inline(self.inline_el(k))
                    if s:
                        bits.append(s)
            return "<br>".join(bits)
        paras = []
        for k in c:
            if isinstance(k.tag, str) and ns(k) != SCL:
                s = clean_inline(self.inline_el(k))
                if s:
                    paras.append(s)
        lead = clean_inline(c.text or "")
        if lead:
            paras.insert(0, lead)
        return "<br>".join(p.replace("\n", "<br>") for p in paras)


def wrap(s: str, mark: str) -> str:
    core = s.strip()
    if not core:
        return s
    if core.startswith(mark) and core.endswith(mark):
        inner = core
    else:
        inner = f"{mark}{core}{mark}"
    lead = " " if s[:1].isspace() else ""
    trail = " " if s[-1:].isspace() else ""
    return lead + inner + trail


def strip_bold(s: str) -> str:
    s = s.strip()
    while s.startswith("**") and s.endswith("**") and len(s) > 4 and "**" not in s[2:-2]:
        s = s[2:-2].strip()
    return s.replace("**", "") if s.count("**") % 2 else s


def blockquote(b: str) -> str:
    return "\n".join("> " + l if l else ">" for l in b.split("\n"))


def strip_scl(root):
    """Remove scl: metadata elements (JOLUX blocks, index terms) keeping their tails."""
    for el in list(root.iter("{%s}*" % SCL)):
        if lname(el) in ("JOLUXWork", "JOLUXExpression", "JOLUXManifestation", "indexterms",
                         "index", "articles", "jolux", "rdf"):
            parent = el.getparent()
            if parent is None:
                continue
            tail = el.tail or ""
            prev = el.getprevious()
            if tail:
                if prev is not None:
                    prev.tail = (prev.tail or "") + tail
                else:
                    parent.text = (parent.text or "") + tail
            parent.remove(el)


def convert(xml_bytes: bytes, image_prefix: str = "") -> tuple[str, list, dict]:
    """Return (markdown body without H1, images, info)."""
    parser = etree.XMLParser(huge_tree=True, recover=True, remove_comments=True)
    root = etree.fromstring(xml_bytes, parser)
    strip_scl(root)
    ctx = Ctx(image_prefix=image_prefix)
    conv = Converter(ctx)
    act = root.find("{*}act")
    if act is None:
        act = root.find("{*}doc") or root
    meta = act.find("{*}meta")
    # notes
    labels_seen = set()
    note_els = []
    if meta is not None:
        note_els = [n for n in meta.iter("{*}note")]
    for n in note_els:
        nid = n.get("id") or ""
        label = (n.get("marker") or nid or str(len(labels_seen) + 1)).strip().replace(" ", "")
        label = re.sub(r"[^\w-]", "", label) or "n"
        base, k = label, 1
        while label in labels_seen:
            k += 1
            label = f"{base}-{k}"
        labels_seen.add(label)
        ctx.notes[nid] = label
    for n in note_els:
        label = ctx.notes[n.get("id") or ""]
        txt = " ".join(conv.blocks(n, 7, quoted=True)).replace("\n", " ")
        ctx.note_text[label] = clean_inline(txt)
    blocks = []
    for part in act:
        if not isinstance(part.tag, str):
            continue
        t = lname(part)
        if t in ("meta",):
            continue
        if t == "preface":
            continue  # the title is rendered as H1 from the catalogue
        blocks.extend(conv.block(part, 2))
    body = "\n\n".join(b for b in blocks if b.strip())
    if ctx.used_notes:
        foot = [f"[^{l}]: {ctx.note_text.get(l, '')}".rstrip() for l in ctx.used_notes]
        body += "\n\n---\n\n" + "\n".join(foot)
    body = re.sub(r"\n{3,}", "\n\n", body)
    info = {"name": act.get("name"), "contains": act.get("contains")}
    return body.strip() + "\n", ctx.images, info


def preface_title(xml_bytes: bytes) -> str:
    parser = etree.XMLParser(huge_tree=True, recover=True)
    root = etree.fromstring(xml_bytes, parser)
    lt = root.find(".//{*}preface/{*}longTitle")
    if lt is None:
        return ""
    return clean_inline(" ".join(lt.itertext()))
