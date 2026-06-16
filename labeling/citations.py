import re

_PREPOSITIONS = r"(?:de|del|la|los|las|da|do|dos|das|van|von)"

_SURNAME_RE = rf"[A-ZÁÉÍÓÚÑÇÃÕÂÊÎÔÛ][a-záéíóúñçãõâêîôû]+(?:[-‐\s]+(?:{_PREPOSITIONS})?\s*[A-ZÁÉÍÓÚÑÇÃÕÂÊÎÔÛ]?[a-záéíóúñçãõâêîôû]+)*"

_PREPOSITIONS_TO_AVOID = [
    "de", "del", "la", "los", "las",
    "da", "do", "dos", "das",
    "van", "von",
]


def find_refid_by_surname_and_date(data_back, searched_surname, searched_date):
    for block in data_back:
        if block["type"] != "ref_paragraph":
            continue
        data = block["value"]

        if str(data.get("date")) != str(searched_date[:4]):
            continue

        authors = data.get("authors", [])
        searched_surnames = searched_surname.split(",")

        for surname in searched_surnames:
            if " y " in surname or " and " in surname or " e " in surname or " & " in surname:
                if " y " in surname:
                    surname1 = surname.split(" y ")[0].strip().lower()
                    surname2 = surname.split(" y ")[1].strip().lower()
                if " and " in surname:
                    surname1 = surname.split(" and ")[0].strip().lower()
                    surname2 = surname.split(" and ")[1].strip().lower()
                if " & " in surname:
                    surname1 = surname.split(" & ")[0].strip().lower()
                    surname2 = surname.split(" & ")[1].strip().lower()
                if " e " in surname:
                    surname1 = surname.split(" e ")[0].strip().lower()
                    surname2 = surname.split(" e ")[1].strip().lower()

                for author_block in authors:
                    if author_block["type"] == "Author":
                        author_data = author_block["value"]
                        if (
                            surname1
                            in (author_data.get("surname") or "").lower()
                            + " "
                            + (author_data.get("given_names") or "").lower()
                        ):
                            for author_block2 in authors:
                                if author_block2["type"] == "Author":
                                    author_data = author_block2["value"]
                                    if (
                                        surname2
                                        in (author_data.get("surname") or "").lower()
                                        + " "
                                        + (author_data.get("given_names") or "").lower()
                                    ):
                                        return data.get("refid")

            for author_block in authors:
                if author_block["type"] == "Author":
                    author_data = author_block["value"]
                    if (
                        surname.strip().lower()
                        in (author_data.get("surname") or "").lower()
                        + " "
                        + (author_data.get("given_names") or "").lower()
                    ):
                        return data.get("refid")

            if surname.strip().lower() in (data.get("paragraph") or "").lower():
                return data.get("refid")

    return None


def extract_apa_citations(text, data_back):
    results_list = []

    for paren in re.finditer(r"\(([^)]+)\)", text):
        full_content = paren.group(1)

        if ";" in full_content:
            parts = [part for part in full_content.split(";")]
        else:
            parts = [full_content]

        parenthetical_authors = []

        for part in parts:
            if not part:
                continue

            if re.match(r"^\s*\d{4}[a-z]?\s*$", part):
                if parenthetical_authors:
                    last_author = parenthetical_authors[-1]
                    refid = find_refid_by_surname_and_date(data_back, last_author, part)
                    results_list.append({
                        "cita": part,
                        "autor": last_author,
                        "anio": part,
                        "refid": refid,
                    })
                continue

            found = False

            pattern1 = rf"(?P<autores>{_SURNAME_RE}(?:\s*,\s*{_SURNAME_RE})*\s*,?\s*&\s*{_SURNAME_RE})\s*,\s*(?P<anio>\d{{4}}[a-z]?)"
            match = re.search(pattern1, part)
            if match:
                full_authors = match.group("autores")
                year = match.group("anio")
                first_author = re.split(r"\s*,\s*", full_authors)[0]
                parenthetical_authors.append(first_author)
                refid = find_refid_by_surname_and_date(data_back, first_author, year)
                results_list.append({"cita": part, "autor": first_author, "anio": year, "refid": refid})
                found = True

            if not found:
                pattern2 = rf"(?P<autores>{_SURNAME_RE}(?:\s*,\s*{_SURNAME_RE})*\s*,?\s*&\s*{_SURNAME_RE})\s+(?P<anio>\d{{4}}[a-z]?)"
                match = re.search(pattern2, part)
                if match:
                    full_authors = match.group("autores")
                    year = match.group("anio")
                    first_author = re.split(r"\s*,\s*", full_authors)[0]
                    parenthetical_authors.append(first_author)
                    refid = find_refid_by_surname_and_date(data_back, first_author, year)
                    results_list.append({"cita": part, "autor": first_author, "anio": year, "refid": refid})
                    found = True

            if not found:
                pattern3 = rf"(?P<autor1>{_SURNAME_RE})\s*&\s*(?P<autor2>{_SURNAME_RE})\s*,\s*(?P<anio>\d{{4}}[a-z]?)"
                match = re.search(pattern3, part)
                if match:
                    first_author = match.group("autor1")
                    year = match.group("anio")
                    parenthetical_authors.append(first_author)
                    refid = find_refid_by_surname_and_date(data_back, first_author, year)
                    results_list.append({"cita": part, "autor": first_author, "anio": year, "refid": refid})
                    found = True

            if not found:
                pattern4 = rf"(?P<autor>{_SURNAME_RE})\s+et\s+al\s*\.?\s*,\s*(?P<anio>\d{{4}}[a-z]?)"
                match = re.search(pattern4, part)
                if match:
                    author = match.group("autor")
                    year = match.group("anio")
                    parenthetical_authors.append(author)
                    refid = find_refid_by_surname_and_date(data_back, author, year)
                    results_list.append({"cita": part, "autor": author, "anio": year, "refid": refid})
                    found = True

            if not found:
                pattern5 = rf"(?P<autor>{_SURNAME_RE})\s+et\s+al\s*\.?\s+(?P<anio>\d{{4}}[a-z]?)"
                match = re.search(pattern5, part)
                if match:
                    author = match.group("autor")
                    year = match.group("anio")
                    parenthetical_authors.append(author)
                    refid = find_refid_by_surname_and_date(data_back, author, year)
                    results_list.append({"cita": part, "autor": author, "anio": year, "refid": refid})
                    found = True

            if not found:
                pattern6 = rf"(?P<autores>{_SURNAME_RE}(?:\s*,\s*{_SURNAME_RE}){{2,}})\s*,\s*(?P<anio>\d{{4}}[a-z]?)"
                match = re.search(pattern6, part)
                if match:
                    full_authors = match.group("autores")
                    year = match.group("anio")
                    first_author = re.split(r"\s*,\s*", full_authors)[0]
                    parenthetical_authors.append(first_author)
                    refid = find_refid_by_surname_and_date(data_back, first_author, year)
                    results_list.append({"cita": part, "autor": first_author, "anio": year, "refid": refid})
                    found = True

            if not found:
                pattern7 = rf"(?P<autor>{_SURNAME_RE})\s*,\s*(?P<anio>\d{{4}}[a-z]?)"
                match = re.search(pattern7, part)
                if match:
                    author = match.group("autor")
                    year = match.group("anio")
                    parenthetical_authors.append(author)
                    refid = find_refid_by_surname_and_date(data_back, author, year)
                    results_list.append({"cita": part, "autor": author, "anio": year, "refid": refid})
                    found = True

    pattern_multi_year = rf"(?P<autor>{_SURNAME_RE})(?:\s*[-‐]\s*{_SURNAME_RE})*(?:\s+et\s+al\s*\.?|\s+(?:y|and|&)\s+{_SURNAME_RE})?\s*\(\s*(?P<años>\d{{4}}[a-z]?(?:\s*,\s*\d{{4}}[a-z]?)+)\s*\)"

    for match in re.finditer(pattern_multi_year, text):
        match_start = match.start()
        previous_text = text[:match_start].split()
        if previous_text and previous_text[-1].lower() in _PREPOSITIONS_TO_AVOID:
            continue

        author = match.group("autor")
        years_str = match.group("años")
        years = [y for y in years_str.split(",")]

        for y in years:
            refid = find_refid_by_surname_and_date(data_back, author, y)
            results_list.append({
                "cita": f"{author} et al. ({y})" if "et al" in match.group(0) else f"{author} ({y})",
                "autor": author,
                "anio": y,
                "refid": refid,
            })

    pattern_outside = rf"(?P<autor>{_SURNAME_RE})(?:\s*[-‐]\s*{_SURNAME_RE})*(?:\s+et\s+al\s*\.?|\s+(?:y|and|&)\s+{_SURNAME_RE})?\s*\(\s*(?P<anio>\d{{4}}[a-z]?)\s*\)"

    for match in re.finditer(pattern_outside, text):
        match_start = match.start()
        previous_text = text[:match_start].split()
        if previous_text and previous_text[-1].lower() in _PREPOSITIONS_TO_AVOID:
            continue

        author = match.group("autor")
        year = match.group("anio")
        full_citation = match.group(0)

        is_multiple = False
        for result in results_list:
            if result["autor"] == author and result["anio"] == year and "," in full_citation:
                is_multiple = True
                break

        if not is_multiple:
            refid = find_refid_by_surname_and_date(data_back, author, year)
            results_list.append({"cita": full_citation, "autor": author, "anio": year, "refid": refid})

    return results_list
