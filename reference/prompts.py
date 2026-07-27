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
            "Preserve surname/fname spelling and capitalization as in the citation; "
            "keep initial clusters compact when the citation has no spaces (C.A not "
            "C. A.) but do not invent missing initials. "
            "date: string; keep letter suffixes (2013a, 2013b). "
            "If the text has DOI: or doi.org/…, ALWAYS set doi to the bare id "
            "(no https://doi.org/); do not emit uri when doi is present; never "
            "invent doi or uri. At most one uri. "
            "journal: title=article, source=periodical. Patterns like "
            "Source, vol(num), pages or Source vol(num):pages or Source, vol, "
            "pages → journal with vol, num when parentheses present, and "
            "fpage/lpage (do not use pages for journal page ranges); pages only "
            "for elocation-id. Volume+pages after a periodical name means "
            "journal, not book. "
            "book: whole work uses source only (do not use title); chapter uses "
            "chapter + source; publisher → organization; thesis: source=title "
            "(no title field). "
            "data: title=dataset, source=repository. "
            "R/CRAN packages and similar download pages → software (or webpage) "
            "with uri when present. "
            "Copy title/source wording verbatim (keep hyphens like Above-ground). "
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
            '{"surname":"Scott","fname":"B."}],"date":"2011",'
            '"title":"Supporting Red List threat assessments with GeoCAT: '
            'geospatial conservation assessment tool","source":"ZooKeys",'
            '"vol":150,"fpage":"117","lpage":"126",'
            '"doi":"10.3897/zookeys.150.2109"}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Alvares, C. A., Stape, J. L., Sentelhas, P. C., Gonçalves, J. L. M., "
            "& Sparovek, G. (2013b). Köppen’s climate classification map for "
            "Brazil. Meteorologische Zeitschrift, 22(6), 711–728. "
            "https://doi.org/10.1127/0941-2948/2013/0507"
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"journal",'
            '"authors":[{"surname":"Alvares","fname":"C. A."},'
            '{"surname":"Stape","fname":"J. L."},'
            '{"surname":"Sentelhas","fname":"P. C."},'
            '{"surname":"Gonçalves","fname":"J. L. M."},'
            '{"surname":"Sparovek","fname":"G."}],'
            '"date":"2013b",'
            '"title":"Köppen’s climate classification map for Brazil",'
            '"source":"Meteorologische Zeitschrift",'
            '"vol":22,"num":6,"fpage":"711","lpage":"728",'
            '"doi":"10.1127/0941-2948/2013/0507"}'
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
            '{"surname":"Shorter","fname":"RG"}],"date":"1995",'
            '"source":"Inflammatory bowel disease",'
            '"chapter":"The epidemiology of idiopathic inflammatory bowel disease",'
            '"edition":"4th","organization":"Williams & Wilkins",'
            '"location":"Baltimore","fpage":"31","lpage":"68"}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Anderson, J. M., & Ingram, J. S. I. (1993). Tropical soil biology and "
            "fertility: A handbook of methods (2nd ed.). CAB International."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"book",'
            '"authors":[{"surname":"Anderson","fname":"J. M."},'
            '{"surname":"Ingram","fname":"J. S. I."}],'
            '"date":"1993",'
            '"source":"Tropical soil biology and fertility: A handbook of methods",'
            '"edition":"2nd","organization":"CAB International"}'
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
            '"date":"1987","source":"Sur le genre Phyllanthus L.",'
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
            '"date":"2025","title":"Replication data for: Mauritia flexuosa",'
            '"source":"SciELO Data","doi":"10.48331/SCIELODATA.RIVAW4"}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Augie, B. (2017). gridExtra: Miscellaneous functions for “Grid” "
            "graphics (Version 2.3) [R package]. "
            "https://CRAN.R-project.org/package=gridExtra"
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"software","authors":[{"surname":"Augie","fname":"B."}],'
            '"date":"2017","source":"gridExtra",'
            '"version":"2.3",'
            '"uri":"https://CRAN.R-project.org/package=gridExtra"}'
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
            '"date":"2011","title":"Supporting Red List","source":"ZooKeys",'
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
    "date": {"type": "string"},
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
