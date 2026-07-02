import json
import re


def fix_unicode_escapes(text):
    result = []
    index = 0
    while index < len(text):
        if text[index : index + 2] == "\\u":
            after = text[index + 2 : index + 6]
            if len(after) == 4 and all(c in "0123456789abcdefABCDEF" for c in after):
                result.append(text[index : index + 6])
                index += 6
                continue
            result.append("\\\\u")
            index += 2
            continue
        result.append(text[index])
        index += 1
    return "".join(result)


def extract_balanced_json(text):
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(text)):
            char = text[index]
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : index + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def try_parse_json(text):
    text = str(text or "").strip()
    if not text:
        raise ValueError("empty_response")

    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    sanitized = fix_unicode_escapes(text)
    try:
        return json.loads(sanitized)
    except json.JSONDecodeError:
        pass

    for source in (text, sanitized):
        result = extract_balanced_json(source)
        if result is not None:
            return result

    raise ValueError("invalid_response")
