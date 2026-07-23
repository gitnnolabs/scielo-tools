MESSAGES = [
    {
        "role": "system",
        "content": (
            "You extract bibliographic citation components and respond ONLY with "
            "JSON. Single input → one JSON object. Numbered lines → "
            '{"results":[...]} with exactly one object per line in order. '
            "Non-citations (figure/table captions, section headings, ORCID URLs, "
            "standalone names, editorial roles such as SCIENTIFIC EDITOR, "
            "CRediT/authorship statements like Responsibility for…) → "
            '{"is_reference": false}. '
            "References always include reftype: book, confproc, data, database, "
            "journal, legal-doc, letter, newspaper, patent, preprint, report, "
            "software, thesis, webpage, other. "
            "Person authors/editors: {surname, fname}; institution: {collab}. "
            "DOI: bare id without https://doi.org/; do not emit uri when doi is "
            "present; never invent doi or uri. At most one uri. "
            "journal: title=article, source=periodical; use fpage and lpage for "
            "page ranges (do not use pages for journal page ranges); pages only "
            "for elocation-id. "
            "book: whole work uses source only (do not use title); chapter uses "
            "chapter + source; thesis: source=title (no title field). "
            "data: title=dataset, source=repository. "
            "confproc/webpage/software/legal-doc: use fields when present."
        ),
    },
    {
        "role": "user",
        "content": (
            "Bachman, S., J. Moat, A. W. Hill, J. de la Torre and B. Scott. 2011. "
            "Supporting Red List threat assessments with GeoCAT: geospatial "
            "conservation assessment tool. ZooKeys 150: 117-126. DOI: "
            "https://doi.org/10.3897/zookeys.150.2109"
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"journal","authors":[{"surname":"Bachman","fname":"S."},'
            '{"surname":"Moat","fname":"J."},{"surname":"Hill","fname":"A. W."},'
            '{"surname":"de la Torre","fname":"J."},'
            '{"surname":"Scott","fname":"B."}],"date":2011,'
            '"title":"Supporting Red List threat assessments with GeoCAT: '
            'geospatial conservation assessment tool","source":"ZooKeys",'
            '"vol":150,"fpage":"117","lpage":"126",'
            '"doi":"10.3897/zookeys.150.2109"}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Calkins BM, Mendeloff AI. The epidemiology of idiopathic inflammatory "
            "bowel disease. In: Kirsner JB, Shorter RG, eds. Inflammatory bowel "
            "disease, 4th ed. Baltimore: Williams & Wilkins. 1995:31-68."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"book","authors":[{"surname":"Calkins","fname":"BM"},'
            '{"surname":"Mendeloff","fname":"AI"}],'
            '"editors":[{"surname":"Kirsner","fname":"JB"},'
            '{"surname":"Shorter","fname":"RG"}],"date":1995,'
            '"source":"Inflammatory bowel disease",'
            '"chapter":"The epidemiology of idiopathic inflammatory bowel disease",'
            '"edition":"4th","organization":"Williams & Wilkins",'
            '"location":"Baltimore","fpage":"31","lpage":"68"}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Brunel, J. F. 1987. Sur le genre Phyllanthus L. Thèse de doctorat "
            "de l’Université L. Pasteur. Strasbourg, France. 760 pp."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"thesis","authors":[{"surname":"Brunel","fname":"J. F."}],'
            '"date":1987,"source":"Sur le genre Phyllanthus L.",'
            '"degree":"doctorat","organization":"l’Université L. Pasteur",'
            '"location":"Strasbourg, France","num_pages":760}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Felix Ribeiro, K. A. (2025). Replication data for: Mauritia flexuosa. "
            "SciELO Data. https://doi.org/10.48331/SCIELODATA.RIVAW4"
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"data",'
            '"authors":[{"surname":"Felix Ribeiro","fname":"K. A."}],'
            '"date":2025,"title":"Replication data for: Mauritia flexuosa",'
            '"source":"SciELO Data","doi":"10.48331/SCIELODATA.RIVAW4"}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Nikon Corporation. 1991-2006. NIS-Elements, version 2.33. Tokio, Japón."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"software","authors":[{"collab":"Nikon Corporation"}],'
            '"date":2006,"source":"NIS-Elements","version":"2.33",'
            '"location":"Tokio, Japón"}'
        ),
    },
    {
        "role": "user",
        "content": (
            "1. Bachman S et al. 2011. Supporting Red List. ZooKeys 150:117-126. "
            "DOI: 10.3897/zookeys.150.2109\n"
            "2. Figure 1. Map of the study area."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"results":['
            '{"reftype":"journal","authors":[{"surname":"Bachman","fname":"S"}],'
            '"date":2011,"title":"Supporting Red List","source":"ZooKeys",'
            '"vol":150,"fpage":"117","lpage":"126",'
            '"doi":"10.3897/zookeys.150.2109"},'
            '{"is_reference": false}'
            "]}"
        ),
    },
    {
        "role": "user",
        "content": "Figure 1. Map of the study area.",
    },
    {
        "role": "assistant",
        "content": '{"is_reference": false}',
    },
    {
        "role": "user",
        "content": "Figura 2. Densidade populacional na Amazônia.",
    },
    {
        "role": "assistant",
        "content": '{"is_reference": false}',
    },
    {
        "role": "user",
        "content": "https://orcid.org/0000-0003-4872-7252",
    },
    {
        "role": "assistant",
        "content": '{"is_reference": false}',
    },
    {
        "role": "user",
        "content": "SCIENTIFIC EDITOR",
    },
    {
        "role": "assistant",
        "content": '{"is_reference": false}',
    },
    {
        "role": "user",
        "content": (
            "Responsibility for all aspects of the content and the integrity of "
            "the published article. Camila Lima Ribeiro, Marcelle Miranda da Silva."
        ),
    },
    {
        "role": "assistant",
        "content": '{"is_reference": false}',
    },
]

ITEM_PROPERTIES = {
    "is_reference": {"type": "boolean"},
    "reftype": {"type": "string"},
    "authors": {"type": "array", "items": {"type": "object"}},
    "editors": {"type": "array", "items": {"type": "object"}},
    "full_text": {"type": "string"},
    "date": {"type": "integer"},
    "title": {"type": "string"},
    "source": {"type": "string"},
    "chapter": {"type": "string"},
    "chapter_title": {"type": "string"},
    "edition": {"type": "string"},
    "doi": {"type": "string"},
    "vol": {"type": "integer"},
    "num": {"type": "integer"},
    "pages": {"type": "string"},
    "fpage": {"type": "string"},
    "lpage": {"type": "string"},
    "uri": {"type": "string"},
    "organization": {"type": "string"},
    "location": {"type": "string"},
    "org_location": {"type": "string"},
    "num_pages": {"type": "integer"},
    "version": {"type": "string"},
    "access_id": {"type": "string"},
    "access_date": {"type": "string"},
    "degree": {"type": "string"},
    "conf_loc": {"type": "string"},
    "conf_date": {"type": "string"},
    "conf_num": {"type": "string"},
    "country": {"type": "string"},
}

RESPONSE_FORMAT = {
    "type": "json_object",
    "schema": {
        "type": "object",
        "properties": ITEM_PROPERTIES,
    },
}

BATCH_RESPONSE_FORMAT = {
    "type": "json_object",
    "schema": {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": ITEM_PROPERTIES,
                },
            },
        },
        "required": ["results"],
    },
}
