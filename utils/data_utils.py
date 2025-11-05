def fetch_from_cdm(mapping, cdm):
    """Fetch field values from CDM with graceful fallback."""
    result = {}
    for field, cdm_path in mapping.items():
        result[field] = cdm.get(cdm_path, "")
    print("📦 Fetched data from CDM:", result)
    return result
