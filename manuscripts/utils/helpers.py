import hashlib
import json
import re
from pathlib import PurePosixPath

XREF_RE = re.compile(
    r'<xref\s+[^>]*ref-type=["\']bibr["\'][^>]*rid=["\']([^"\']+)["\'][^>]*>(.*?)</xref>',
    re.I | re.S,
)


def checksum_bytes(content):
    return hashlib.sha256(content).hexdigest()


def json_safe(value):
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            default=lambda item: sorted(item) if isinstance(item, set) else str(item),
        )
    )


def to_dict_list(stream_value):
    if not stream_value:
        return []
    if hasattr(stream_value, "stream_block"):
        return stream_value.stream_block.get_prep_value(stream_value)
    return stream_value


def _block(label, paragraph, block_type="paragraph"):
    return {"type": block_type, "value": {"label": label, "paragraph": paragraph}}


def _raw_reference(position, text):
    return {
        "type": "ref_paragraph",
        "value": {
            "label": "<p>",
            "refid": f"B{position}",
            "paragraph": text,
            "authors": [],
        },
    }


def safe_archive_members(archive):
    for info in archive.infolist():
        path = PurePosixPath(info.filename)
        if info.is_dir() or path.is_absolute() or ".." in path.parts:
            continue
        yield info
