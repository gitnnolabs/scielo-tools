"""
Cross-reference (xref) linking for the DOCX → SPS XML pipeline.

Official convention
-------------------
- Each reference entry in the reference list receives a bookmark named
  ``xref_B{n}`` (1-indexed, n = position in the reference list).
- Each in-text citation becomes a Word internal hyperlink whose anchor
  points to the corresponding ``xref_B{n}`` bookmark.

This convention allows:
- Clicking a citation in Word → jumps to the reference entry.
- Clicking the reference entry bookmark → jumps back (if a reverse
  hyperlink is added by the editor).

Supported citation styles (auto-detected for unmarked documents):
- ABNT        : (Autor, 2020)  or  (Autor et al., 2020)
- Vancouver bracket    : [1]  or  [7,8]  or  [3-5]
- Vancouver superscript: runs with font.superscript == True containing digits

Validation rules:
- ERROR   : a hyperlink points to a bookmark that does not exist.
- WARNING : a bookmark has no corresponding hyperlink (uncited reference).
"""

import copy
import re
import unicodedata

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

BOOKMARK_PREFIX = "xref_B"

_REF_HEADINGS = {
    "references",
    "referências",
    "referências bibliográficas",
    "referencias",
    "referencias bibliográficas",
    "bibliography",
    "bibliografia",
}

_STOP_HEADINGS = {
    "figures captions",
    "figure captions",
    "figures",
    "supplementary material",
    "supplementary materials",
    "appendix",
    "appendices",
    "supporting information",
    "acknowledgements",
    "acknowledgments",
    "agradecimentos",
    "material suplementar",
    "notas",
    "notes",
    # author/editor metadata sections
    "author contributions",
    "contribuições dos autores",
    "contribuciones de los autores",
    "data availability",
    "data availability statement",
    "disponibilidade dos dados",
    "funding",
    "financiamento",
    "conflict of interest",
    "conflicts of interest",
    "conflito de interesses",
    "declaration of competing interest",
    "editors",
    "editor associado",
    "editor científico",
    "associate editor",
    "scientific editor",
}

_ALLCAPS_STOP_RE = re.compile(r'^[A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇÄÖÏËØÅÆŒ\s\-]{4,60}$')


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_marked(doc: Document) -> bool:
    """Return True if *doc* contains xref_B* bookmarks AND hyperlinks."""
    xml = doc.element.xml
    has_bk = bool(re.search(rf'w:name="{BOOKMARK_PREFIX}\d+"', xml))
    has_hl = bool(re.search(rf'w:anchor="{BOOKMARK_PREFIX}\d+"', xml))
    return has_bk and has_hl


def validate_marks(doc: Document) -> dict:
    """
    Validate consistency of xref markup.

    Returns a dict::

        {
            "valid": bool,               # False when any hyperlink is orphaned
            "bookmarks": set[str],       # all xref_B* bookmarks found
            "hyperlinks": set[str],      # all xref_B* anchors found
            "orphaned_bookmarks": list,  # bookmarks without a citation (warnings)
            "orphaned_hyperlinks": list, # citations without a reference (errors)
            "warnings": list[str],
            "errors": list[str],
        }
    """
    xml = doc.element.xml
    bookmarks = set(re.findall(rf'w:name="({BOOKMARK_PREFIX}\d+)"', xml))
    hyperlinks = set(re.findall(rf'w:anchor="({BOOKMARK_PREFIX}\d+)"', xml))

    orphaned_bk = sorted(bookmarks - hyperlinks)
    orphaned_hl = sorted(hyperlinks - bookmarks)

    warnings = [f"Reference {b} has no in-text citation." for b in orphaned_bk]
    errors = [f"Citation links to {h} but no matching reference bookmark found." for h in orphaned_hl]

    return {
        "valid": len(orphaned_hl) == 0,
        "bookmarks": bookmarks,
        "hyperlinks": hyperlinks,
        "orphaned_bookmarks": orphaned_bk,
        "orphaned_hyperlinks": orphaned_hl,
        "warnings": warnings,
        "errors": errors,
    }


def read_marks(doc: Document) -> list:
    """
    Extract xref data from a marked document.

    Returns a list of dicts (one per reference), ordered by bookmark index::

        [
            {
                "rid": "B1",
                "bookmark": "xref_B1",
                "ref_text": "AUTOR, A. 2020. Título...",
                "citations": ["(Autor, 2020)", ...],   # in-text citation texts
            },
            ...
        ]
    """
    xml = doc.element.xml

    # Collect all bookmark names present
    bk_names = sorted(
        set(re.findall(rf'w:name="({BOOKMARK_PREFIX}\d+)"', xml)),
        key=lambda s: int(s[len(BOOKMARK_PREFIX):]),
    )

    # Map anchor → list of citation texts extracted from hyperlinks
    citation_map: dict[str, list[str]] = {b: [] for b in bk_names}

    # Scan ALL paragraphs (including those inside table cells)
    for p_elem in doc.element.body.iter(qn("w:p")):
        p_xml = p_elem.xml
        for m in re.finditer(
            rf'<w:hyperlink[^>]+w:anchor="({BOOKMARK_PREFIX}\d+)"[^>]*>(.*?)</w:hyperlink>',
            p_xml,
            re.DOTALL,
        ):
            anchor = m.group(1)
            inner = m.group(2)
            # Extract plain text from the hyperlink's runs and unescape XML entities
            texts = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', inner)
            citation_text = "".join(texts).strip().replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
            if anchor in citation_map:
                citation_map[anchor].append(citation_text)

    # Map bookmark → reference paragraph text
    ref_paragraphs = _find_references_section(doc)
    ref_text_map: dict[str, str] = {}
    for idx, (_, para) in enumerate(ref_paragraphs, start=1):
        bk = f"{BOOKMARK_PREFIX}{idx}"
        ref_text_map[bk] = para.text.strip()

    result = []
    for bk in bk_names:
        n = bk[len(BOOKMARK_PREFIX):]
        result.append({
            "rid": f"B{n}",
            "bookmark": bk,
            "ref_text": ref_text_map.get(bk, ""),
            "citations": citation_map.get(bk, []),
        })
    return result


def apply_xml_xrefs_to_docx(doc: Document, xml_tree) -> Document:
    """
    Add Word internal hyperlinks/bookmarks to a DOCX rendered from SPS XML.

    The packtools PDF DOCX renderer preserves the visible text of
    ``xref[@ref-type='bibr']`` but not the link semantics. This restores the
    same ``xref_Bn`` bookmark convention used by ``mark_references``.
    """
    references = []
    for ref in xml_tree.xpath(".//ref[@id]"):
        mixed = " ".join(ref.xpath(".//mixed-citation//text()")).strip()
        if mixed:
            references.append({"rid": ref.get("id"), "text": _normalize_ws(mixed)})

    citations = []
    for xref in xml_tree.xpath(".//xref[@ref-type='bibr'][@rid]"):
        text = " ".join(xref.xpath(".//text()")).strip()
        if text:
            citations.append({"rid": xref.get("rid"), "text": _normalize_ws(text)})

    if not references or not citations:
        return doc

    next_id = _next_bookmark_id(doc)
    bookmarked = set(re.findall(rf'w:name="({BOOKMARK_PREFIX}\d+)"', doc.element.xml))
    ref_paragraphs = list(_iter_paragraphs(doc))
    for ref in references:
        anchor = _anchor_from_rid(ref["rid"])
        if not anchor or anchor in bookmarked:
            continue
        para = _find_paragraph_containing(ref_paragraphs, ref["text"])
        if para is None:
            continue
        _add_bookmark_to_para(para, anchor, next_id)
        bookmarked.add(anchor)
        next_id += 1

    for para in _iter_paragraphs(doc):
        spans = []
        para_text = para.text
        if not para_text:
            continue
        for citation in citations:
            anchor = _anchor_from_rid(citation["rid"])
            if not anchor or anchor not in bookmarked:
                continue
            start = para_text.find(citation["text"])
            if start < 0:
                continue
            end = start + len(citation["text"])
            spans.append((start, end, anchor, citation["text"]))
        if spans:
            _insert_hyperlinks_plain(para, spans)

    return doc


def mark_references(doc: Document) -> Document:
    """
    Auto-detect citations and add xref markup to *doc*.

    1. Adds ``xref_B{n}`` bookmarks to each reference entry.
    2. Detects the citation style (ABNT, Vancouver bracket, superscript).
    3. Wraps in-text citations in internal hyperlinks pointing to the
       corresponding bookmark.

    Returns the modified Document (same object, mutated in place).
    """
    refs = _find_references_section(doc)
    if not refs:
        return doc

    # Step 1 — bookmark each reference
    bk_id_start = _next_bookmark_id(doc)
    for offset, (_, para) in enumerate(refs):
        bk_name = f"{BOOKMARK_PREFIX}{offset + 1}"
        _add_bookmark_to_para(para, bk_name, bk_id_start + offset)

    # Build reference index for matching
    ref_index = _build_ref_index(refs)

    # Step 2 — detect style and find citations
    style = _detect_citation_style(doc)

    if style == "vancouver_bracket":
        citations = _find_citations_bracket(doc)
    elif style == "vancouver_superscript":
        citations = _find_citations_superscript(doc)
    else:
        citations = _find_citations_abnt(doc, ref_index)

    # Step 3 — insert hyperlinks
    for para, spans in citations.items():
        _insert_hyperlinks(para, spans)

    return doc


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize_match_text(text: str) -> str:
    text = _normalize_ws(text)
    text = re.sub(r"\s+([,.;:?!\)])", r"\1", text)
    text = re.sub(r"([\(\[])\s+", r"\1", text)
    return text.rstrip(".")


def _iter_paragraphs(doc: Document):
    for paragraph in doc.paragraphs:
        yield paragraph
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    yield paragraph


def _anchor_from_rid(rid: str) -> str | None:
    first = (rid or "").split()
    if not first:
        return None
    match = re.match(r"^B(\d+)$", first[0])
    if not match:
        return None
    return f"{BOOKMARK_PREFIX}{match.group(1)}"


def _find_paragraph_containing(paragraphs, target: str):
    target_norm = _normalize_match_text(target)
    if not target_norm:
        return None
    for para in paragraphs:
        para_norm = _normalize_match_text(para.text)
        if not para_norm:
            continue
        if target_norm in para_norm or para_norm in target_norm:
            return para
    target_prefix = target_norm[:80]
    for para in paragraphs:
        para_norm = _normalize_match_text(para.text)
        if target_prefix and para_norm and target_prefix in para_norm:
            return para
    return None


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _detect_citation_style(doc: Document) -> str:
    """Return 'abnt', 'vancouver_bracket', or 'vancouver_superscript'."""
    body_paras = _body_paragraphs(doc)
    full_text = " ".join(p.text for p in body_paras)

    # Bracket citations [1] or [1,2] are the most unambiguous signal.
    brackets = re.findall(r'\[\d+(?:[,\-]\d+)*\]', full_text)
    if len(brackets) >= 3:
        return "vancouver_bracket"

    # Superscript digit runs — require a high count to avoid mistaking
    # footnote markers or ordinals in ABNT documents.
    sup_count = sum(
        1
        for para in body_paras
        for run in para.runs
        if run.font.superscript and re.fullmatch(r'[\d,\s\-]+', run.text.strip())
    )
    abnt_count = len(re.findall(
        r'\([A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇ][^()]{2,80}\d{4}[^()]*\)', full_text
    ))
    # Declare superscript only when it clearly dominates over ABNT matches.
    if sup_count >= 10 and sup_count > abnt_count * 3:
        return "vancouver_superscript"

    return "abnt"


def _iter_all_paragraphs(doc: Document):
    """Yield all Paragraph objects in document order, including inside tables."""
    from docx.text.paragraph import Paragraph as _Para
    for p_elem in doc.element.body.iter(qn("w:p")):
        yield _Para(p_elem, doc)


_METADATA_RE = re.compile(
    r'^(?:received|accepted|published|available\s+at|doi\s*:|https?://)',
    re.IGNORECASE,
)

_YEAR_RE_SIMPLE = re.compile(r'\b(?:1[89]|20)\d{2}\b')

def _find_references_section(doc: Document) -> list:
    """Return list of (paragraph_index, paragraph) for reference entries."""
    in_refs = False
    refs = []
    for i, para in enumerate(_iter_all_paragraphs(doc)):
        text = para.text.strip()
        text_lower = text.lower().rstrip(":.")
        if text_lower in _REF_HEADINGS:
            in_refs = True
            continue
        if not in_refs:
            continue
        # Stop at known post-reference section headings
        if text_lower in _STOP_HEADINGS:
            break
        # Stop at Word heading styles (Heading 1/2/3/...)
        style_name = (para.style.name or '') if para.style else ''
        if re.match(r'heading\s*\d', style_name, re.IGNORECASE):
            break
        # Stop at ALL-CAPS short paragraphs without a year — section headings
        # like "CONTRIBUIÇÕES DOS AUTORES", "EDITOR ASSOCIADO", etc.
        if (text and len(text) <= 60
                and _ALLCAPS_STOP_RE.match(text)
                and not _YEAR_RE_SIMPLE.search(text)):
            break
        if text and not _METADATA_RE.match(text):
            refs.append((i, para))
    return refs


def _build_ref_index(refs: list) -> list:
    """Return list of (n, first_author_normalized, year, para) for ABNT matching."""
    index = []
    year_re = re.compile(r'\b((?:1[89]|20)\d{2}[a-z]?)\b')
    for n, (_, para) in enumerate(refs, start=1):
        text = para.text.strip()
        year_m = year_re.search(text)
        year = year_m.group(1) if year_m else ""
        first_author = _normalize(_first_surname(text))
        index.append((n, first_author, year, para))
    return index


def _first_surname(ref_text: str) -> str:
    """Extract the first author surname from a reference string."""
    # ABNT: SOBRENOME, Iniciais. → first word before comma
    # Vancouver: Sobrenome AB, ... → first word
    m = re.match(r'^([A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇÄÖÏËØÅÆŒ][A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇÄÖÏËØÅÆŒa-záéíóúàâêôãõüçäöïëøåæœ\-]+)', ref_text.strip())
    return m.group(1) if m else ref_text[:10]


def _normalize(text: str) -> str:
    """Lowercase + remove accents for fuzzy comparison."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _body_paragraphs(doc: Document) -> list:
    """Return paragraphs that belong to the article body (before references)."""
    body = []
    for para in _iter_all_paragraphs(doc):
        if para.text.strip().lower() in _REF_HEADINGS:
            break
        body.append(para)
    return body


# ---------------------------------------------------------------------------
# Citation finders — return {para: [(start, end, anchor), ...]}
# ---------------------------------------------------------------------------

def _find_citations_bracket(doc: Document) -> dict:
    """Find [n] and [n,m] citations and map them to xref_B* anchors."""
    result: dict = {}
    pattern = re.compile(r'\[(\d+(?:[,\-]\d+)*)\]')

    for para in _body_paragraphs(doc):
        text = para.text
        spans = []
        for m in pattern.finditer(text):
            numbers = _expand_range(m.group(1))
            for n in numbers:
                anchor = f"{BOOKMARK_PREFIX}{n}"
                spans.append((m.start(), m.end(), anchor, m.group(0)))
        if spans:
            result[para] = spans
    return result


def _find_citations_superscript(doc: Document) -> dict:
    """Find superscript-number citations and map them to xref_B* anchors."""
    result: dict = {}

    for para in _body_paragraphs(doc):
        spans = []
        pos = 0
        for run in para.runs:
            run_text = run.text
            run_end = pos + len(run_text)
            if run.font.superscript and re.fullmatch(r'[\d,\s\-]+', run_text.strip()):
                # Strip leading/trailing commas that Word sometimes includes
                # in the same superscript run as punctuation separators.
                clean = run_text.strip().strip(',').strip()
                numbers = _expand_range(clean.replace(" ", ""))
                for n in numbers:
                    anchor = f"{BOOKMARK_PREFIX}{n}"
                    spans.append((pos, run_end, anchor, clean))
            pos = run_end
        if spans:
            result[para] = spans
    return result


def _find_citations_abnt(doc: Document, ref_index: list) -> dict:
    """
    Find ABNT citations and match against ref_index:
      - Parenthetical: (Author, 2020) or (Author et al., 2020; Author2, 2021)
      - Narrative:     Author (2020) or Author et al. (2020) or Author and Author (2020)
      - Plain text:    Author Year (e.g. "see Bergstrom 1995")
    """
    result: dict = {}
    paren_re = re.compile(
        r'\(([A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇ][^\(\)]{2,100}\d{4}[^\(\)]*)\)',
        re.UNICODE,
    )
    year_re = re.compile(r'\b(1[89]\d{2}|20\d{2})\b')

    # Surname token: handles hyphen-compounds with optional space (e.g. "Ilkiu-Borges" or "Ilkiu -Borges")
    _sname = (
        r'[A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇÄÖÏËØÅÆŒ][A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇÄÖÏËØÅÆŒa-záéíóúàâêôãõüçäöïëøåæœ]+'
        r'(?:\s*-\s*[A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇÄÖÏËØÅÆŒa-záéíóúàâêôãõüçäöïëøåæœ]+)*'
    )
    narrative_re = re.compile(
        r'(' + _sname + r'(?:\s+(?:and|&)\s+' + _sname + r')*(?:\s+et\s+al\.)?)'
        r'\s*\((\d{4}[a-z]?(?:,\s*\d{4}[a-z]?)*)\)',
        re.UNICODE,
    )
    # Plain text: Surname (and Surname)* Year without parentheses (e.g. "Bergstrom 1995", "Boadway and Keen 1996")
    plain_text_re = re.compile(
        r'\b(' + _sname + r'(?:\s+(?:and|&)\s+' + _sname + r')*)\s+((?:1[89]|20)\d{2}[a-z]?)\b',
        re.UNICODE,
    )

    for para in _body_paragraphs(doc):
        text = para.text
        spans = []
        covered: set[tuple[int, int]] = set()

        # 1. Parenthetical citations: (Author, year) — split on ";" for multiple
        for m in paren_re.finditer(text):
            inner = m.group(1)
            parts = [p.strip() for p in inner.split(";")]
            for part in parts:
                year_m = year_re.search(part)
                if not year_m:
                    continue
                year = year_m.group(1)
                surname_m = re.match(r'([A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇ][^\s,]+)', part)
                if not surname_m:
                    continue
                surname = _normalize(surname_m.group(1))
                anchor = _match_abnt(surname, year, ref_index)
                if anchor and (m.start(), m.end()) not in covered:
                    spans.append((m.start(), m.end(), anchor, m.group(0)))
                    covered.add((m.start(), m.end()))

        # 2. Narrative citations: Author (year) — not already covered by parenthetical
        for m in narrative_re.finditer(text):
            if (m.start(), m.end()) in covered:
                continue
            author_part = m.group(1).strip()
            years_str = m.group(2)
            # Extract first surname (strip et al. first)
            author_clean = re.sub(r'\s+et\s+al\.', '', author_part)
            first_token = re.match(r'([^\s]+)', author_clean)
            if not first_token:
                continue
            surname = _normalize(first_token.group(1))
            # Try each year in the citation until one matches (handles "Author (1976, 1984, 1985)")
            anchor = None
            for yr in re.findall(r'\d{4}[a-z]?', years_str):
                anchor = _match_abnt(surname, yr, ref_index)
                if anchor:
                    break
            if anchor and (m.start(), m.end()) not in covered:
                spans.append((m.start(), m.end(), anchor, m.group(0)))
                covered.add((m.start(), m.end()))

        # 3. Plain text citations: Author (and Author)* Year — not already covered
        for m in plain_text_re.finditer(text):
            if any(m.start() >= s and m.end() <= e for s, e in covered):
                continue
            author_part = m.group(1).strip()
            year = m.group(2)
            first_token = re.match(r'([^\s]+)', author_part)
            if not first_token:
                continue
            surname = _normalize(first_token.group(1))
            anchor = _match_abnt(surname, year, ref_index)
            if anchor and (m.start(), m.end()) not in covered:
                spans.append((m.start(), m.end(), anchor, m.group(0)))
                covered.add((m.start(), m.end()))

        if spans:
            result[para] = spans
    return result


def _match_abnt(surname: str, year: str, ref_index: list) -> str | None:
    """Return xref_Bn for the best match, or None."""
    skey = surname[:5]
    year_plain = year[:4]
    # Exact match first (preserves 2004a vs 2004b disambiguation)
    for n, first_author, ref_year, _ in ref_index:
        if ref_year == year and first_author.startswith(skey):
            return f"{BOOKMARK_PREFIX}{n}"
    # Fallback: compare first 4 chars (handles refs stored without suffix)
    for n, first_author, ref_year, _ in ref_index:
        if ref_year[:4] == year_plain and first_author.startswith(skey):
            return f"{BOOKMARK_PREFIX}{n}"
    return None


def _expand_range(token: str) -> list[int]:
    """'3,5' → [3,5];  '7-9' → [7,8,9];  '2' → [2]."""
    numbers = []
    for part in token.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            try:
                numbers.extend(range(int(a), int(b) + 1))
            except ValueError:
                pass
        else:
            try:
                numbers.append(int(part))
            except ValueError:
                pass
    return numbers


# ---------------------------------------------------------------------------
# XML manipulation
# ---------------------------------------------------------------------------

def _next_bookmark_id(doc: Document) -> int:
    """Return an id value safe to use for new bookmarks."""
    existing = re.findall(r'w:id="(\d+)"', doc.element.xml)
    return max((int(i) for i in existing), default=0) + 1


def _add_bookmark_to_para(para, name: str, bk_id: int):
    """Wrap the paragraph content in a named bookmark."""
    p = para._p

    bk_start = OxmlElement("w:bookmarkStart")
    bk_start.set(qn("w:id"), str(bk_id))
    bk_start.set(qn("w:name"), name)

    bk_end = OxmlElement("w:bookmarkEnd")
    bk_end.set(qn("w:id"), str(bk_id))

    p.insert(0, bk_start)
    p.append(bk_end)


def _make_text_run(text: str, template_run=None):
    r = copy.deepcopy(template_run) if template_run is not None else OxmlElement("w:r")
    for child in list(r):
        if child.tag != qn("w:rPr"):
            r.remove(child)
    t = OxmlElement("w:t")
    t.text = text
    if text.startswith(" ") or text.endswith(" "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    r.append(t)
    return r


def _insert_hyperlinks_plain(para, spans: list):
    full_text = para.text
    if not full_text:
        return

    unique_spans = []
    last_end = -1
    seen = set()
    for start, end, anchor, text in sorted(spans, key=lambda s: (s[0], s[1])):
        key = (start, end, anchor)
        if key in seen or start < last_end:
            continue
        seen.add(key)
        unique_spans.append((start, end, anchor, text))
        last_end = end
    if not unique_spans:
        return

    p = para._p
    run_segments = []
    for child in p:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag in {"r", "hyperlink"}:
            run_segments.append(child)
    template_run = next(
        (elem for elem in run_segments if elem.tag.split("}")[-1] == "r"),
        None,
    )
    for elem in run_segments:
        if elem in p:
            p.remove(elem)

    ppr = p.find(qn("w:pPr"))
    insert_after = ppr if ppr is not None else None
    insert_pos = 0

    def insert(elem):
        nonlocal insert_after, insert_pos
        if insert_after is not None:
            insert_after.addnext(elem)
            insert_after = elem
        else:
            p.insert(insert_pos, elem)
            insert_pos += 1

    cursor = 0
    for start, end, anchor, text in unique_spans:
        if start > cursor:
            insert(_make_text_run(full_text[cursor:start], template_run))
        insert(_make_hyperlink(anchor, full_text[start:end], template_run))
        cursor = end
    if cursor < len(full_text):
        insert(_make_text_run(full_text[cursor:], template_run))


def _insert_hyperlinks(para, spans: list):
    """
    Replace citation text in *para* with internal hyperlinks.

    *spans* is a list of (start, end, anchor, original_text) tuples, where
    start/end are character offsets in ``para.text``.
    Multiple citations pointing to the same span are merged into separate
    hyperlinks inserted consecutively.
    """
    # Deduplicate spans on (start, end) keeping first match only
    seen = set()
    unique_spans = []
    for span in sorted(spans, key=lambda s: s[0]):
        key = (span[0], span[1])
        if key not in seen:
            seen.add(key)
            unique_spans.append(span)

    # Rebuild paragraph XML run-by-run, inserting hyperlinks at citation positions
    p = para._p
    full_text = para.text

    # Collect (run_element, run_start, run_end) from current runs
    run_segments = []
    pos = 0
    for child in p:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "r":
            t_elem = child.find(qn("w:t"))
            text = t_elem.text if t_elem is not None and t_elem.text else ""
            run_segments.append((child, pos, pos + len(text)))
            pos += len(text)
        elif tag == "hyperlink":
            # Already a hyperlink — count its text length
            inner_text = "".join(
                (t.text or "") for t in child.iter(qn("w:t"))
            )
            run_segments.append((child, pos, pos + len(inner_text)))
            pos += len(inner_text)

    if not run_segments:
        return

    # Build list of "what goes where" in character-offset order
    # Each item: ('run', elem) or ('hyperlink', anchor, text, template_run)
    events = []  # (char_offset, type, ...)

    # Mark citation zones
    citation_zones = {(s, e): (anchor, txt) for s, e, anchor, txt in unique_spans}

    offset = 0
    seg_idx = 0
    while seg_idx < len(run_segments) and offset < len(full_text):
        elem, seg_start, seg_end = run_segments[seg_idx]
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        # Check if a citation zone starts here
        matched_zone = None
        for (z_start, z_end), (anchor, cit_text) in citation_zones.items():
            if seg_start <= z_start < seg_end or (z_start <= seg_start < z_end):
                matched_zone = (z_start, z_end, anchor, cit_text)
                break

        if matched_zone is None or tag == "hyperlink":
            events.append(("keep", elem))
            seg_idx += 1
            continue

        z_start, z_end, anchor, cit_text = matched_zone

        # Split first run: extract text before the citation starts
        t_node = elem.find(qn("w:t"))
        run_text = t_node.text if t_node is not None and t_node.text else ""
        before = run_text[:max(0, z_start - seg_start)]
        if before:
            r_before = copy.deepcopy(elem)
            t = r_before.find(qn("w:t"))
            t.text = before
            if before.startswith(" ") or before.endswith(" "):
                t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            events.append(("keep", r_before))

        # Advance seg_idx to the last run that overlaps this zone.
        # Citations like "Costa <italic>et al.</italic> (2020)" span multiple runs;
        # without this loop only the first run portion would be hyperlinked.
        while seg_idx + 1 < len(run_segments) and run_segments[seg_idx + 1][1] < z_end:
            seg_idx += 1

        # Extract text after the citation ends from the last run in the zone
        last_elem, last_start, _ = run_segments[seg_idx]
        last_t = last_elem.find(qn("w:t"))
        last_text = last_t.text if last_t is not None and last_t.text else ""
        after = last_text[max(0, z_end - last_start):]

        # Emit hyperlink with full citation text (first run used as style template)
        events.append(("hyperlink", anchor, cit_text, elem))

        if after:
            r_after = copy.deepcopy(last_elem)
            t = r_after.find(qn("w:t"))
            if t is not None:
                t.text = after
                if after.startswith(" ") or after.endswith(" "):
                    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            events.append(("keep", r_after))

        del citation_zones[(z_start, z_end)]
        seg_idx += 1

    # Remaining segments
    for elem, _, _ in run_segments[seg_idx:]:
        events.append(("keep", elem))

    # Remove old run/hyperlink children from paragraph
    for elem, _, _ in run_segments:
        if elem in p:
            p.remove(elem)

    # Re-insert in order
    insert_pos = 0
    # Find insertion point (after pPr if present)
    ppr = p.find(qn("w:pPr"))
    insert_after = ppr if ppr is not None else None

    for event in events:
        if event[0] == "keep":
            elem = event[1]
            if insert_after is not None:
                insert_after.addnext(elem)
                insert_after = elem
            else:
                p.insert(insert_pos, elem)
                insert_pos += 1
        else:
            _, anchor, cit_text, template_run = event
            hl = _make_hyperlink(anchor, cit_text, template_run)
            if insert_after is not None:
                insert_after.addnext(hl)
                insert_after = hl
            else:
                p.insert(insert_pos, hl)
                insert_pos += 1


def build_text_xref_replacer(doc: Document):
    """
    Build a callable that tags 'Author (year)' narrative citations with <xref>.
    Builds the reference lookup directly from the reference list section in *doc*,
    assigning B1..Bn by position (consistent with read_marks / xml.py convention).
    Returns: apply(text: str) -> str
    """
    refs = _find_references_section(doc)
    ref_list = [
        {'rid': f'B{i + 1}', 'ref_text': para.text.strip()}
        for i, (_, para) in enumerate(refs)
    ]
    return _make_text_xref_fn(ref_list)


def make_text_xref_fn_from_refs(ref_items: list):
    """
    Build a narrative xref replacer from reference dicts with keys:
    {'rid'|'refid': 'Bn', 'ref_text'|'paragraph': '...'}.
    Returns: apply(text: str) -> str
    """
    return _make_text_xref_fn(ref_items)


def _make_text_xref_fn(ref_list: list):
    """Build the 'Author (year)' replacer function from a list of reference dicts."""
    # Year regex includes optional letter suffix (e.g. 2004a, 2004b)
    _year_re = re.compile(r'\b((?:1[89]|20)\d{2}[a-z]?)\b')
    # Tuples: (skey, year_with_suffix, rid, full_ref_text_normalized) for compound-author lookup
    ref_entries: list[tuple[str, str, str, str]] = []
    # Simple primary lookup: first match wins
    ref_lookup: dict[tuple[str, str], str] = {}

    for i, item in enumerate(ref_list):
        rid = item.get('rid') or item.get('refid') or f'B{i + 1}'
        text = item.get('ref_text') or item.get('paragraph') or ''
        if not text:
            continue
        skey = _normalize(_first_surname(text))[:5]
        norm_text = _normalize(text)
        for year in _year_re.findall(text)[:4]:
            ref_entries.append((skey, year, rid, norm_text))
            if (skey, year) not in ref_lookup:
                ref_lookup[(skey, year)] = rid

    if not ref_entries:
        return lambda t: t

    def _lookup(skey: str, year: str, extra_skeys: list[str]) -> str | None:
        """Find best rid: prefer entries containing all author surnames."""
        candidates = [(rid, norm) for s, y, rid, norm in ref_entries if s == skey and y == year]
        if not candidates:
            return None
        if len(candidates) == 1 or not extra_skeys:
            return candidates[0][0]
        # Prefer candidate whose text contains the extra authors
        for rid, norm in candidates:
            if all(sk in norm for sk in extra_skeys):
                return rid
        return candidates[0][0]

    # Reusable surname token: handles "Ilkiu-Borges" and "Ilkiu -Borges" (space before hyphen)
    _sname = (
        r'[A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇÄÖÏËØÅÆŒ][A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇÄÖÏËØÅÆŒa-záéíóúàâêôãõüçäöïëøåæœ]+'
        r'(?:\s*-\s*[A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇÄÖÏËØÅÆŒa-záéíóúàâêôãõüçäöïëøåæœ]+)*'
    )
    # et al. can appear as plain text or wrapped in <italic> tags
    _etal = r'(?:\s+(?:et\s+al\.|<italic>et\s+al\.?</italic>\.?))?'
    # Match: Surname [and/& Surname]* [et al.] (year[a-z]?[, year[a-z]?]*)
    _narrative_re = re.compile(
        r'(' + _sname + r'(?:\s+(?:and|&)\s+' + _sname + r')*' + _etal + r')'
        r'\s*\((\d{4}[a-z]?(?:,\s*\d{4}[a-z]?)*)\)',
        re.UNICODE,
    )
    _split_re = re.compile(r'(<xref[^>]*>.*?</xref>)', re.DOTALL)
    _etal_strip = re.compile(r'\s+(?:et\s+al\.|<italic>et\s+al\.?</italic>\.?)')

    def _replace(m: re.Match) -> str:
        full = m.group(0)
        author_part = m.group(1).strip()
        years_str = m.group(2)
        # Remove et al., then split on and/& to get individual author tokens
        author_clean = _etal_strip.sub('', author_part)
        author_tokens = re.split(r'\s+(?:and|&)\s+', author_clean)
        skeys = [_normalize(t.split()[0])[:5] for t in author_tokens if t.strip()]
        if not skeys:
            return full
        primary_skey = skeys[0]
        extra_skeys = skeys[1:]
        rids: list[str] = []
        for year in re.findall(r'\d{4}[a-z]?', years_str):
            rid = _lookup(primary_skey, year, extra_skeys)
            if rid and rid not in rids:
                rids.append(rid)
        if not rids:
            return full
        return f'<xref ref-type="bibr" rid="{" ".join(rids)}">{full}</xref>'

    _paren_inner_re = re.compile(
        r'\(([A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇÄÖÏËØÅÆŒ][^\(\)]{2,200}\d{4}[^\(\)]*)\)',
        re.UNICODE,
    )
    _paren_year_re = re.compile(r'\b(1[89]\d{2}|20\d{2})\b')
    _paren_author_re = re.compile(r'([A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇÄÖÏËØÅÆŒ][^\s,;]+)')

    def _replace_paren(m: re.Match) -> str:
        full = m.group(0)
        inner = m.group(1)
        parts = [p.strip() for p in re.split(r'[;,]\s*(?=[A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇÄÖÏËØÅÆŒ])', inner)]
        rids: list[str] = []
        for part in parts:
            yr_m = _paren_year_re.search(part)
            if not yr_m:
                continue
            au_m = _paren_author_re.match(part)
            if not au_m:
                continue
            skey = _normalize(au_m.group(1))[:5]
            rid = _lookup(skey, yr_m.group(1), [])
            if rid and rid not in rids:
                rids.append(rid)
        if not rids:
            return full
        return f'<xref ref-type="bibr" rid="{" ".join(rids)}">{full}</xref>'

    def apply(text: str) -> str:
        if not text:
            return text
        parts = _split_re.split(text)
        result = []
        for idx, part in enumerate(parts):
            if idx % 2 != 0:
                result.append(part)
                continue
            # Narrative first, then parenthetical on remaining non-xref text
            part = _narrative_re.sub(_replace, part)
            sub_parts = _split_re.split(part)
            out = []
            for i, sp in enumerate(sub_parts):
                if i % 2 != 0:
                    out.append(sp)
                else:
                    out.append(_paren_inner_re.sub(_replace_paren, sp))
            result.append(''.join(out))
        return ''.join(result)

    return apply


def _make_hyperlink(anchor: str, text: str, template_run) -> object:
    """Create a <w:hyperlink w:anchor="..."> element."""
    hl = OxmlElement("w:hyperlink")
    hl.set(qn("w:anchor"), anchor)

    r = _make_text_run(text, template_run)
    # Ensure rPr exists and add Hyperlink style
    rpr = r.find(qn("w:rPr"))
    if rpr is None:
        rpr = OxmlElement("w:rPr")
        r.insert(0, rpr)
    style_elem = OxmlElement("w:rStyle")
    style_elem.set(qn("w:val"), "Hyperlink")
    rpr.insert(0, style_elem)

    hl.append(r)
    return hl
