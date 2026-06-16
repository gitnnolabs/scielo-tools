import json
import re


def fix_unicode_escapes(text):
    result = []
    i = 0
    while i < len(text):
        if text[i:i+2] == "\\u":
            after = text[i+2:i+6]
            if len(after) == 4 and all(c in "0123456789abcdefABCDEF" for c in after):
                result.append(text[i:i+6])
                i += 6
                continue
            result.append("\\\\u")
            i += 2
            continue
        result.append(text[i])
        i += 1
    return "".join(result)


def extract_balanced_json(text):
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == "\\":
                escape = True
                continue
            if c == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
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

    text = re.sub(r'^```(?:json)?\s*\n?', "", text)
    text = re.sub(r'\n?\s*```$', "", text)

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
