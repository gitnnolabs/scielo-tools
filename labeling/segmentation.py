import re

from labeling.citations import extract_apa_citations
from labeling.fragments import extract_label_and_title, is_number_parenthesis
from manuscripts.choices import order_labels

_FRONTMATTER_PATTERNS = [
    re.compile(r"\b10\.\d{4,}/[^\s]+", re.I),
    re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[X\d]\b"),
    re.compile(r"\bdoi\s*:\s*10\.", re.I),
    re.compile(r"\bhttps?://orcid\.org/", re.I),
    re.compile(r"@\S+\.\S+"),
    re.compile(r"^\s*(resumo|abstract|resumen|resumén)\s*$", re.I),
    re.compile(r"^\s*(palavras?\s*-?\s*chave|palabras?\s+clave|keywords?)\s*:?", re.I),
    re.compile(r"^\s*(recebido|recibido|received)\b", re.I),
    re.compile(r"^\s*(aceito|aceptado|accepted|aprovado)\b", re.I),
    re.compile(r"\b(recebido|recibido|received)\s+(em:|:)", re.I),
    re.compile(r"\b(aceito|aceptado|accepted)\s+(em:|:)", re.I),
    re.compile(r"\b\d{2}[./]\d{2}[./]\d{4}\b"),
    re.compile(r"^\s*(doutor|doctor|mestre|master|graduad|professor|profesora?|ingeniero?)\b", re.I),
    re.compile(r"^\s*(universidade|universidad|university|instituto|institute|faculdade|faculdad|faculty|colégio|colegio)\b", re.I),
]

_BODY_START_PATTERNS = [
    re.compile(r"^\s*(introdução|introducción|introduction)\b", re.I),
    re.compile(r"^\s*(metodologia|methodology|metodología|método|method|materials?\s+(and|e)\s+methods?)\b", re.I),
    re.compile(r"^\s*\d+[\.\)]\s+\w", re.I),
    re.compile(r"^\s*(resultados|results|discussão|discussión|discussion)\b", re.I),
    re.compile(r"^\s*(conclusão|conclusión|conclusion|considerações\s+finais|consideraciones\s+finales)\b", re.I),
    re.compile(r"^\s*(referências|referencias|references|bibliografia|bibliography)\b", re.I),
    re.compile(r"^\s*(agradecimentos|agradecimientos|acknowledg?ments?)\b", re.I),
]


def clean_labels(text):
    return re.sub(r"<[^>]+>", "", text)


def map_text(text):
    label_map = {}
    pattern = r"<[^>]+>.*?</[^>]+>|<[^/>]+/>"
    matches = re.findall(pattern, text, re.DOTALL)
    for match in matches:
        clean_content = clean_labels(match)
        if clean_content:
            label_map[clean_content] = match
    return label_map


def find_positions(text, substring):
    positions = []
    start = 0
    while True:
        pos = text.find(substring, start)
        if pos == -1:
            break
        positions.append((pos, pos + len(substring)))
        start = pos + 1
    return positions


def extract_labels(original_text, clean_text, start_pos, end_pos):
    clean_char_count = 0
    result = ""
    in_range = False

    i = 0
    while i < len(original_text) and clean_char_count <= end_pos:
        char = original_text[i]

        if char == "<":
            tag_end = original_text.find(">", i)
            if tag_end != -1:
                tag = original_text[i:tag_end + 1]
                if in_range:
                    result += tag
                i = tag_end + 1
                continue

        if clean_char_count == start_pos:
            in_range = True
        elif clean_char_count == end_pos:
            in_range = False
            break

        if in_range:
            result += char

        clean_char_count += 1
        i += 1

    return result


def restore_labels_ref(ref, label_map, original_text, clean_text):
    positions = find_positions(clean_text, ref)
    if not positions:
        return ref

    candidates = []
    for start_pos, end_pos in positions:
        original_fragment = extract_labels(original_text, clean_text, start_pos, end_pos)
        if original_fragment != ref:
            candidates.append(original_fragment)

    return candidates[0] if candidates else ref


def process_labeled_text(text, data_back):
    transform_map = map_text(text)
    clean_text = clean_labels(text)
    refs = extract_apa_citations(clean_text, data_back)

    labeled_refs = []
    for ref in refs:
        restored = dict(ref)
        restored["cita"] = restore_labels_ref(ref["cita"], transform_map, text, clean_text)
        labeled_refs.append(restored)

    return labeled_refs


def match_by_regex(text, order_labels):
    return next(
        (
            key_obj
            for key_obj in order_labels.items()
            if "regex" in key_obj[1] and re.search(key_obj[1]["regex"], text)
        ),
        None,
    )


def match_by_style_and_size(item, order_labels, style="bold"):
    return next(
        (
            key_obj
            for key_obj in order_labels.items()
            if "size" in key_obj[1]
            and style in key_obj[1]
            and key_obj[1]["size"] == item.get("font_size")
            and key_obj[1][style] == item.get(style)
        ),
        None,
    )


def match_next_label(item, label_next, order_labels):
    return next(
        (
            key_obj
            for key_obj in order_labels.items()
            if "size" in key_obj[1]
            and key_obj[1]["size"] == item.get("font_size")
            and key_obj[0] == label_next
        ),
        None,
    )


def match_paragraph(item, order_labels):
    return next(
        (
            key_obj
            for key_obj in order_labels.items()
            if "size" in key_obj[1]
            and "next" in key_obj[1]
            and key_obj[1]["size"] == item.get("font_size")
            and key_obj[1]["next"] == "<p>"
        ),
        None,
    )


def match_section(item, sections):
    return (
        {"label": "<sec>", "body": True}
        if (
            item.get("font_size") == sections[0].get("size")
            and item.get("bold") == sections[0].get("bold")
            and item.get("text", "").isupper() == sections[0].get("isupper")
        )
        else None
    )


def match_subsection(item, sections):
    return (
        {"label": "<sub-sec>", "body": True}
        if (
            item.get("font_size") == sections[1].get("size")
            and item.get("bold") == sections[1].get("bold")
            and item.get("text", "").isupper() == sections[1].get("isupper")
        )
        else None
    )


def _looks_like_frontmatter(text):
    if not text or not text.strip():
        return False
    for pattern in _BODY_START_PATTERNS:
        if pattern.search(text):
            return False
    for pattern in _FRONTMATTER_PATTERNS:
        if pattern.search(text):
            return True
    return False


def create_labeled_object(i, item, state, sections):
    obj = {}
    result = None

    if match_section(item, sections):
        result = match_section(item, sections)
        state["label"] = result.get("label")
        state["body"] = result.get("body")

    if match_subsection(item, sections):
        result = match_subsection(item, sections)
        state["label"] = result.get("label")
        state["body"] = result.get("body")

    if (
        state.get("body")
        and re.search(r"^(refer)", item.get("text").lower())
        and match_section(item, sections)
    ):
        state["label"] = "<sec>"
        state["body"] = False
        state["back"] = True
        obj["type"] = "paragraph"
        obj["value"] = {"label": state["label"], "paragraph": item.get("text")}

    if state.get("body") and re.search(
        r"^(refer[eê]nci|references?)\s*$", item.get("text").strip().lower()
    ):
        state["label"] = "<sec>"
        state["body"] = False
        state["back"] = True
        result = {"label": "<sec>", "body": False, "back": True}
        obj["type"] = "paragraph"
        obj["value"] = {"label": state["label"], "paragraph": item.get("text")}

    if not result:
        result = {"label": "<p>", "body": state["body"], "back": state["back"]}
        state["label"] = result.get("label")
        state["body"] = result.get("body")
        state["back"] = result.get("back")

    if not result:
        if state.get("label_next"):
            if state.get("repeat"):
                result = match_by_regex(item.get("text"), order_labels)
                if result:
                    state["label"] = result[0]
                else:
                    result = match_by_style_and_size(item, order_labels, style="bold")
                    if result:
                        state["label"] = result[0]
                        state["repeat"] = None
                        state["reset"] = None
                        state["label_next"] = result[1].get("next")
                        state["body"] = result[1].get("size") == 16
                        if state["body"] and re.search(r"^(refer)", item.get("text").lower()):
                            state["body"] = False
                            state["back"] = True
            if not result:
                result = match_next_label(item, state["label_next"], order_labels)
                if result:
                    state["label"] = result[0]
                    state["label_next_reset"] = result[1].get("next")
                    state["reset"] = result[1].get("reset", False)
                    state["repeat"] = result[1].get("repeat", False)
        else:
            result = match_by_style_and_size(item, order_labels, style="bold")
            if result:
                state["label"] = result[0]
                state["label_next"] = result[1].get("next")
                if state.get("body") and re.search(r"^(refer)", item.get("text").lower()):
                    state["body"] = False
                    state["back"] = True
            else:
                result = match_by_style_and_size(item, order_labels, style="italic")
                if result:
                    state["label"] = re.sub(r"-\d+", "", result[0])
                    state["label_next"] = result[1].get("next")
                else:
                    result = match_by_regex(item.get("text"), order_labels)
                    if result:
                        state["label"] = result[0]
                    else:
                        result = match_paragraph(item, order_labels)
                        if result:
                            state["label"] = result[0]

    if result:
        obj["type"] = "paragraph"
        obj["value"] = {"label": state["label"], "paragraph": item.get("text")}

        if state["label"] == "<contrib>":
            obj["type"] = "author_paragraph"
        elif state["label"] == "<aff>":
            obj["type"] = "aff_paragraph"

    if re.search(r"^(translation)", item.get("text").lower()):
        state["label"] = "<translate-fron>"
        state["body"] = False
        state["back"] = False
        obj["type"] = "paragraph_with_language"
        obj["value"] = {"label": state["label"], "paragraph": item.get("text")}

    if state.get("body") and _looks_like_frontmatter(item.get("text", "")):
        state["body"] = False
        state["back"] = False

    return obj, result, state


def create_special_content_object(item, stream_data_body, counts):
    obj = {}

    if item.get("type") == "image":
        obj = {}
        counts["numfig"] += 1
        obj["type"] = "image"
        obj["value"] = {
            "figid": f"f{counts['numfig']}",
            "label": "<fig>",
            "image": item.get("image"),
        }

        try:
            prev_element = stream_data_body[-1]
            label_title = extract_label_and_title(prev_element["value"]["paragraph"])
            obj["value"]["figlabel"] = label_title["label"]
            obj["value"]["title"] = label_title["title"]
            stream_data_body.pop(-1)
        except Exception:
            pass

    elif item.get("type") == "table":
        obj = {}
        counts["numtab"] += 1
        obj["type"] = "table"
        obj["value"] = {
            "tabid": f"t{counts['numtab']}",
            "label": "<table>",
            "content": item.get("table"),
        }

        try:
            prev_element = stream_data_body[-1]
            label_title = extract_label_and_title(prev_element["value"]["paragraph"])
            obj["value"]["tablabel"] = label_title["label"]
            obj["value"]["title"] = label_title["title"]
            stream_data_body.pop(-1)
        except Exception:
            pass

    elif item.get("type") == "list":
        obj = {}
        obj["type"] = "paragraph"
        obj["value"] = {"label": "<list>", "paragraph": item.get("list")}

    elif item.get("type") == "compound":
        obj = {}
        counts["numeq"] += 1
        obj["type"] = "compound_paragraph"
        obj["value"] = {
            "eid": f"e{counts['numeq']}",
            "content": item.get("text"),
        }
        text_count = sum(1 for c in obj["value"]["content"] if c["type"] == "text")

        if text_count > 1:
            obj["value"]["label"] = "<inline-formula>"
            return obj, counts

        if text_count == 0:
            obj["value"]["label"] = "<disp-formula>"
            return obj, counts

        text_value = next(
            item["value"] for item in obj["value"]["content"] if item["type"] == "text"
        )
        text = is_number_parenthesis(text_value)
        if text:
            obj["value"]["label"] = "<disp-formula>"
            next(item for item in obj["value"]["content"] if item["type"] == "text")["value"] = text
        else:
            obj["value"]["label"] = "<inline-formula>"

    return obj, counts
