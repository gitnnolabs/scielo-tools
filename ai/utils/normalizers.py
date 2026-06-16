import re

DOI_RE = re.compile(r"\b10\.\d{4,}(?:\.\d+)*\/[^\s\"]+", re.I)
ORCID_RE = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[X\d]")


def stz_text(value):
    return str(value or "").strip()


def stz_norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def stz_language(code, fallback="en"):
    code = (code or "").strip()[:2].lower()
    return code if len(code) == 2 and code.isalpha() else fallback


def stz_country_code(value):
    code = (value or "").strip().upper()[:2]
    return code if len(code) == 2 and code.isalpha() else ""


def stz_affiliation_id(value):
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v]
    if value:
        return [str(value)]
    return []


def stz_first_number(value):
    match = re.search(r"\d+", str(value or ""))
    return match.group(0) if match else ""


def stz_date(value):
    text = stz_text(value)
    if not text:
        return ""
    match = re.match(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?", text)
    if not match:
        return ""
    year, month, day = match.group(1), match.group(2), match.group(3)
    if month:
        month = str(min(max(int(month), 1), 12)).zfill(2)
    if day:
        day = str(min(max(int(day), 1), 31)).zfill(2)
    parts = [year, month, day] if month else [year]
    return "-".join(p for p in parts if p)


def stz_year(value):
    text = stz_text(value)
    match = re.match(r"\d{4}", text)
    return match.group(0) if match else ""
