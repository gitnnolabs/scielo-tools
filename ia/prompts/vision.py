VISION_TASKS = [
    (
        "titles",
        "Analyze the pages of this article and extract the main title and any translated titles, "
        'with their languages. Return a JSON object with a "titles" key containing a list of objects '
        'with "text", "language" (ISO 639-1: en, es, pt, fr), and "kind" ("main" or "translated"). '
        'Example: {"titles":[{"text":"The Title","language":"en","kind":"main"},'
        '{"text":"El Título","language":"es","kind":"translated"}]}. '
        "Do not include explanations, only the JSON.",
    ),
    (
        "authors",
        "Analyze the pages of this article and extract all author names, their ORCIDs "
        "(format 0000-0000-0000-0000), and affiliation symbols (*, **, etc). "
        'Return a JSON object with an "authors" key containing a list of objects with "given_names", '
        '"surname", "display", "orcid", and "affiliations" (list of IDs). '
        'Use empty string "" for ORCID if not found. NEVER invent ORCIDs. '
        'Also return "affiliations", a list of objects with "id" and "text". '
        'Example: {"authors":[{"given_names":"John","surname":"Smith",'
        '"display":"John Smith","orcid":"0000-0000-0000-0000","affiliations":["1"]}],'
        '"affiliations":[{"id":"1","text":"University of Example"}]}. '
        "Do not include explanations, only the JSON.",
    ),
    (
        "abstracts",
        "Analyze the pages of this article and extract all abstracts "
        "(Abstract, Resumo, Resumen, Résumé, etc.), with their respective languages. "
        'Return a JSON object with an "abstracts" key containing a list of objects with '
        '"title" (exact label: "Abstract", "Resumo", etc.), '
        '"text" (only the abstract body text, do NOT include keywords), '
        'and "language" (ISO 639-1). '
        'Example: {"abstracts":[{"title":"Abstract","text":"The full abstract text...","language":"en"}]}. '
        "Do not include explanations, only the JSON.",
    ),
    (
        "keywords",
        "Analyze the pages of this article and extract all keyword groups, "
        'with their respective languages. Return a JSON object with a "keywords" key containing a '
        'list of objects with "title" (label: "Keywords", "Palavras-chave", etc.), '
        '"terms" (list of terms), and "language" (ISO 639-1). '
        'Example: {"keywords":[{"title":"Keywords","terms":["term1","term2"],"language":"en"}]}. '
        "Do not include explanations, only the JSON.",
    ),
    (
        "dates",
        "Analyze the pages of this article and extract the received, accepted, and publication dates. "
        'Return a JSON object with a "dates" key containing a list of objects with "type" '
        '("received", "accepted", "published", "ahp"), "date" (format YYYY-MM-DD), '
        'and "raw" (original date text). '
        'Example: {"dates":[{"type":"received","date":"2023-01-15","raw":"Received: 15.01.2023"}]}. '
        "Do not include explanations, only the JSON.",
    ),
    (
        "meta",
        "Analyze the pages of this article and extract the DOI, journal name, ISSN, "
        'volume, number, and year. Return a JSON object with keys "doi", "journal" (with "title" and '
        '"issn"), and "issue" (with "volume", "number", "year"). '
        'Example: {"doi":"10.1234/example.2023","journal":{"title":"Journal Name","issn":"1234-5678"},'
        '"issue":{"volume":"15","number":"3","year":"2023"}}. '
        "Do not include explanations, only the JSON.",
    ),
]
