from pathlib import Path

from reference.utils.references import parse_reference_list

_FIXTURES_DIR = Path(__file__).resolve().parent

REFERENCES = parse_reference_list(
    (_FIXTURES_DIR / "references.txt").read_text(encoding="utf-8")
)
REF_LIST_XML = (_FIXTURES_DIR / "references.xml").read_text(encoding="utf-8")
