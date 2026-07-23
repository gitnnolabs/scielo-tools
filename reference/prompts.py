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
            "Include when present: authors, editors, title, source, chapter, edition, "
            "date, doi, vol, num, pages, fpage, lpage, uri, organization, location, "
            "org_location, num_pages, version, access_id, access_date, degree, "
            "conf_loc, conf_date, conf_num, country. "
            "Authors and editors: person as {surname, fname}; institution as {collab}. "
            "Prefer DOI when present: put the bare id (without https://doi.org/) in "
            "doi and do not emit uri. If there is no DOI but a persistent URL exists, "
            "put it in uri. If neither exists, omit both; never invent doi or uri. "
            "journal: title is article title, source is periodical; use fpage and "
            "lpage for page ranges (do not use pages for journal page ranges); use "
            "pages only for elocation-id or long numeric article id "
            "(e240058 or similar). "
            "book: whole work uses source only (do not use title); chapter uses "
            "chapter plus source for the book; edition, organization, location, "
            "num_pages, fpage, lpage, editors when present. "
            "thesis: source is thesis title (do not use title); degree, organization, "
            "location, num_pages when present. "
            "data: title is dataset name, source is repository; version, access_id, "
            "access_date when present. "
            "confproc: title is conference name or proceedings title; source for "
            "work title when distinct; conf_loc or location, conf_date, conf_num or "
            "num, organization, org_location when present. "
            "webpage and database: source (or title), uri, access_date, organization. "
            "software: source (or title), version, uri or location. "
            "legal-doc: laws, decrees and similar norms. "
            "At most one uri."
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
            "Brunel, J. F. 1987. Sur le genre Phyllanthus L. et quelques genres "
            "voisins de la Tribu des Phyllantheae Dumort. (Euphorbiaceae, "
            "Phyllantheae) en Afrique intertropicale et à Madagascar. Thèse de "
            "doctorat de l’Université L. Pasteur. Strasbourg, France. 760 pp."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"thesis","authors":[{"surname":"Brunel","fname":"J. F."}],'
            '"date":1987,"source":"Sur le genre Phyllanthus L. et quelques genres '
            "voisins de la Tribu des Phyllantheae Dumort. (Euphorbiaceae, "
            'Phyllantheae) en Afrique intertropicale et à Madagascar",'
            '"degree":"doctorat","organization":"l’Université L. Pasteur",'
            '"location":"Strasbourg, France","num_pages":760}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Hernández-López, L. 1995. The endemic flora of Jalisco, Mexico: "
            "Centers of endemism and implications for conservation. Tesis de "
            "maestría. Universidad de Wisconsin. Madison, USA. 74 pp."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"thesis","authors":[{"surname":"Hernández-López",'
            '"fname":"L."}],"date":1995,'
            '"source":"The endemic flora of Jalisco, Mexico: Centers of '
            'endemism and implications for conservation","degree":"maestría",'
            '"organization":"Universidad de Wisconsin",'
            '"location":"Madison, USA","num_pages":74}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Jones DL. The role of physical activity on the need for revision "
            "total knee arthroplasty in individuals with osteoarthritis of the "
            "knee [dissertation]. [Pittsburgh (PA)]: University of Pittsburgh; "
            "2001. 436 p."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"thesis","authors":[{"surname":"Jones","fname":"DL"}],'
            '"date":2001,"source":"The role of physical activity on the need '
            "for revision total knee arthroplasty in individuals with "
            'osteoarthritis of the knee","degree":"dissertation",'
            '"organization":"University of Pittsburgh",'
            '"location":"Pittsburgh (PA)","num_pages":436}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Schimper, A. F. W. 1903. Plant geography upon a physiological basis. "
            "Clarendon Press. Oxford, UK. 839 pp."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"book","authors":[{"surname":"Schimper",'
            '"fname":"A. F. W."}],"date":1903,'
            '"source":"Plant geography upon a physiological basis",'
            '"organization":"Clarendon Press","location":"Oxford, UK",'
            '"num_pages":839}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Correa, M. D., C. Galdames and M. Stapf. 2004. Catálogo de Plantas "
            "Vasculares de Panamá. Smithsonian Tropical Research Institute. "
            "Ciudad de Panamá, Panamá. 599 pp."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"book","authors":[{"surname":"Correa","fname":"M. D."},'
            '{"surname":"Galdames","fname":"C."},'
            '{"surname":"Stapf","fname":"M."}],"date":2004,'
            '"source":"Catálogo de Plantas Vasculares de Panamá",'
            '"organization":"Smithsonian Tropical Research Institute",'
            '"location":"Ciudad de Panamá, Panamá","num_pages":599}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Hernández-López, L. 2019. Las especies endémicas de plantas en el "
            "estado de Jalisco: su distribución y conservación. Comisión "
            "Nacional para el Conocimiento y Uso de la Biodiversidad (CONABIO). "
            "Cd. Mx., México. https://doi.org/10.15468/ktvqds "
            "(consultado diciembre de 2019)."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"data","authors":[{"surname":"Hernández-López",'
            '"fname":"L."}],"date":2019,'
            '"title":"Las especies endémicas de plantas en el estado de '
            'Jalisco: su distribución y conservación",'
            '"source":"Comisión Nacional para el Conocimiento y Uso de la '
            'Biodiversidad (CONABIO)","location":"Cd. Mx., México",'
            '"doi":"10.15468/ktvqds","access_date":"diciembre de 2019"}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Lucas Leão; Perobelli, Fernando Salgueiro; Ribeiro, Hilton Manoel "
            "Dias, 2024, Data for: Ação Coletiva Institucional e Consórcio "
            "Públicos Intermunicipais no Brasil, DOI: 10.48331/scielodata.5Z4TMP, "
            "SciELO Data, V1, UNF:6:Neyjad4du3rFprhupCXizA== [fileUNF]. "
            "Disponível em: https://doi.org/10.48331/scielodata"
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"data","authors":[{"surname":"Leão","fname":"Lucas"},'
            '{"surname":"Perobelli","fname":"Fernando Salgueiro"},'
            '{"surname":"Ribeiro","fname":"Hilton Manoel Dias"}],"date":2024,'
            '"version":"V1","title":"Data for: Ação Coletiva Institucional e '
            'Consórcio Públicos Intermunicipais no Brasil",'
            '"source":"SciELO Data","doi":"10.48331/scielodata.5Z4TMP",'
            '"access_id":"UNF:6:Neyjad4du3rFprhupCXizA== [fileUNF]"}'
        ),
    },
    {
        "role": "user",
        "content": (
            "INAFED. 2010. Enciclopedia de los Municipios y Delegaciones de "
            "México: Jalisco. Instituto Nacional para el Federalismo y el "
            "Desarrollo Municipal. "
            "http://www.inafed.gob.mx/work/enciclopedia/EMM21puebla/index.html "
            "(consultado diciembre de 2018)."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"webpage","authors":[{"collab":"INAFED"}],"date":2010,'
            '"source":"Enciclopedia de los Municipios y Delegaciones de México: '
            'Jalisco","organization":"Instituto Nacional para el Federalismo y '
            'el Desarrollo Municipal",'
            '"uri":"http://www.inafed.gob.mx/work/enciclopedia/EMM21puebla/'
            'index.html","access_date":"diciembre de 2018"}'
        ),
    },
    {
        "role": "user",
        "content": (
            "COB - Comitê Olímpico Brasileiro. Desafio para o corpo. Disponível "
            "em: http://www.cob.org.br/esportes/esporte.asp?id=39. "
            "(Acesso em 10 abr 2010)"
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"webpage","authors":[{"collab":"COB - Comitê Olímpico '
            'Brasileiro"}],"date":2010,"source":"Desafio para o corpo",'
            '"uri":"http://www.cob.org.br/esportes/esporte.asp?id=39",'
            '"access_date":"10 abr 2010"}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Nikon Corporation. 1991-2006. NIS-Elements, version 2.33. " "Tokio, Japón."
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
            "Hamric, Ann B.; Spross, Judith A.; Hanson, Charlene M. Advanced "
            "practice nursing: an integrative approach. 3rd ed. St. Louis (MO): "
            "Elsevier Saunders; c2005. 979 p."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"book","authors":[{"surname":"Hamric","fname":"Ann B."},'
            '{"surname":"Spross","fname":"Judith A."},'
            '{"surname":"Hanson","fname":"Charlene M."}],"date":2005,'
            '"source":"Advanced practice nursing: an integrative approach",'
            '"edition":"3rd ed","organization":"Elsevier Saunders",'
            '"location":"St. Louis (MO)","num_pages":979}'
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
            "Furton EJ, Dort V, editors. Addiction and compulsive behaviors. "
            "Proceedings of the 17th Workshop for Bishops; 1999; Dallas, TX. "
            "Boston: National Catholic Bioethics Center (US); 2000. 258 p."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"reftype":"confproc","authors":[{"surname":"Furton","fname":"EJ"},'
            '{"surname":"Dort","fname":"V"}],"date":2000,'
            '"source":"Addiction and compulsive behaviors",'
            '"title":"Proceedings of the 17th Workshop for Bishops",'
            '"location":"Dallas, TX","num":17,'
            '"organization":"National Catholic Bioethics Center (US)",'
            '"org_location":"Boston","num_pages":258}'
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
