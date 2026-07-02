JSON_INSTRUCTION = (
    "Output ONLY a JSON object, never text before or after. "
    "Start with {, end with }. "
    "CRITICAL: never invent names, ORCIDs, dates, or any data. "
    'Use empty string "" for missing fields. '
    "Use empty array [] for missing lists. "
    "Only extract what is explicitly written in the content."
)
