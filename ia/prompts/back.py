MESSAGES = [
    {
        "role": "system",
        "content": "You distinguish citation components and respond in JSON.",
    },
    {
        "role": "user",
        "content": "Bachman S et al. 2011. Supporting Red List threat assessments. ZooKeys 150:117-126. DOI: https://doi.org/10.3897/zookeys.150.2109",
    },
]

RESPONSE_FORMAT = {
    "type": "json_object",
    "schema": {
        "type": "object",
        "properties": {
            "reftype": {"type": "string"},
            "authors": {"type": "array", "items": {"type": "object"}},
            "full_text": {"type": "string"},
            "date": {"type": "integer"},
            "title": {"type": "string"},
            "source": {"type": "string"},
            "doi": {"type": "string"},
        },
    },
}
