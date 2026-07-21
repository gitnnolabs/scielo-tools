MESSAGES = [
    {
        "role": "system",
        "content": (
            "You extract bibliographic citation components and respond ONLY with a "
            "JSON object. "
            "If the input is NOT a bibliographic reference — for example a figure or "
            "table caption (Figure 1, Figura 2, Fig. 3, Table 1, Tabela 1), a section "
            "heading (Figures, Figuras, List of figures, Acknowledgments, "
            "Agradecimentos, Appendix, Anexo), an ORCID URL (https://orcid.org/…), "
            "a standalone person name without year/source/DOI, an editorial role "
            "(SCIENTIFIC EDITOR, ASSOCIATE EDITOR, Editor Científico, Editor "
            "Associado), an authorship or CRediT contribution statement "
            "(Responsibility for…, Approval of…, Manuscript writing…, Data "
            "analysis…, Contribuição…, Aprovação…, Redação…, Análise…), or other "
            "non-citation text — respond "
            'ONLY with {"is_reference": false} and do not invent bibliographic fields. '
            "When the input IS a bibliographic reference, always include reftype with "
            "one of: book, confproc, data, database, journal, legal-doc, letter, "
            "newspaper, patent, preprint, report, software, thesis, webpage, other. "
            "Include when present: authors, title, source, date, doi, vol, num, "
            "pages, uri, organization, chapter_title, version, access_date, degree, "
            "conf_loc, conf_date, conf_num, country. "
            "Authors: person as {surname, fname}; institution as {collab}. "
            "journal: title is article title, source is periodical. "
            "book: whole work uses title or source; chapter uses chapter_title "
            "(maps to part-title) plus source for the book. "
            "data: title is dataset name, source is repository. "
            "confproc: title is conference name; add conf_loc, conf_date, conf_num "
            "when present. "
            "webpage and database: title or source, uri, access_date. "
            "software: R/Python packages and programs (title, version, uri). "
            "legal-doc: laws, decrees and similar norms. "
            "thesis: title, degree, organization. "
            "DOI as bare id without https://doi.org/. "
            "pages as range (117-126), single page, or elocation id "
            "(e240058 or long numeric article id). At most one uri."
        ),
    },
    {
        "role": "user",
        "content": (
            "Bachman S et al. 2011. Supporting Red List threat assessments. "
            "ZooKeys 150:117-126. DOI: https://doi.org/10.3897/zookeys.150.2109"
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"journal","authors":[{"surname":"Bachman","fname":"S"}],'
            '"date":2011,"title":"Supporting Red List threat assessments",'
            '"source":"ZooKeys","vol":150,"pages":"117-126",'
            '"doi":"10.3897/zookeys.150.2109"}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Hess, L. L. (2003). Mapping wetlands in the Amazon Basin using SAR "
            "data. In Proceedings of the IEEE International Geoscience and Remote "
            "Sensing Symposium (IGARSS ’03) (Vol. 2, pp. 1375–1377). IEEE."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"book","authors":[{"surname":"Hess","fname":"L. L."}],'
            '"date":2003,"chapter_title":"Mapping wetlands in the Amazon Basin '
            'using SAR data",'
            '"source":"Proceedings of the IEEE International Geoscience and '
            'Remote Sensing Symposium (IGARSS ’03)",'
            '"vol":2,"pages":"1375-1377","organization":"IEEE"}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Felix Ribeiro, K. A. (2025). Replication data for: Mauritia flexuosa "
            "(Buriti) forest description: Hydro-edaphic effects on tree species "
            "distribution in Western Amazon. SciELO Data. Draft version. "
            "https://doi.org/10.48331/SCIELODATA.RIVAW4"
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"data",'
            '"authors":[{"surname":"Felix Ribeiro","fname":"K. A."}],'
            '"date":2025,'
            '"title":"Replication data for: Mauritia flexuosa (Buriti) forest '
            "description: Hydro-edaphic effects on tree species distribution in "
            'Western Amazon",'
            '"source":"SciELO Data. Draft version",'
            '"doi":"10.48331/SCIELODATA.RIVAW4"}'
        ),
    },
    {
        "role": "user",
        "content": (
            'Augie, B. (2017). gridExtra: Miscellaneous functions for "Grid" '
            "graphics (Version 2.3) [R package]. "
            "https://CRAN.R-project.org/package=gridExtra"
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"software","authors":[{"surname":"Augie","fname":"B"}],'
            '"date":2017,'
            '"title":"gridExtra: Miscellaneous functions for \\"Grid\\" graphics",'
            '"version":"2.3",'
            '"uri":"https://CRAN.R-project.org/package=gridExtra"}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Brasil. (2024). Decreto nº 91.886, de 05 de novembro de 1985. "
            "Diário Oficial da União. "
            "https://www.planalto.gov.br/cCivil_03/Atos/decretos/1985/D91886"
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"legal-doc","authors":[{"collab":"Brasil"}],'
            '"date":2024,'
            '"title":"Decreto nº 91.886, de 05 de novembro de 1985. '
            'Diário Oficial da União",'
            '"uri":"https://www.planalto.gov.br/cCivil_03/Atos/decretos/1985/D91886"}'
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
        "content": "Figures",
    },
    {
        "role": "assistant",
        "content": '{"is_reference": false}',
    },
    {
        "role": "user",
        "content": "List of figures",
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
        "content": "Marcelle Miranda da Silva",
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

RESPONSE_FORMAT = {
    "type": "json_object",
    "schema": {
        "type": "object",
        "properties": {
            "is_reference": {"type": "boolean"},
            "reftype": {"type": "string"},
            "authors": {"type": "array", "items": {"type": "object"}},
            "full_text": {"type": "string"},
            "date": {"type": "integer"},
            "title": {"type": "string"},
            "source": {"type": "string"},
            "chapter_title": {"type": "string"},
            "doi": {"type": "string"},
            "vol": {"type": "integer"},
            "num": {"type": "integer"},
            "pages": {"type": "string"},
            "uri": {"type": "string"},
            "organization": {"type": "string"},
            "version": {"type": "string"},
            "access_date": {"type": "string"},
            "degree": {"type": "string"},
            "conf_loc": {"type": "string"},
            "conf_date": {"type": "string"},
            "conf_num": {"type": "string"},
            "country": {"type": "string"},
        },
    },
}
