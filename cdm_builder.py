"""
CDM Schema Builder - Dynamically generate CDM from client table data

This module automatically infers CDM schema structure from database tables
with dynamic fields, allowing the system to work with any client data model.
"""

import re


# Field type patterns for auto-categorization
FIELD_PATTERNS = {
    # Personal Information
    "person.full_name": [
        r"^(full_?name|name|full_?legal_?name)$",
        r"^(client_?name|customer_?name)$"
    ],
    "person.first_name": [
        r"^(first_?name|given_?name|fname)$"
    ],
    "person.middle_name": [
        r"^(middle_?name|middle_?initial|mname|mi)$"
    ],
    "person.last_name": [
        r"^(last_?name|surname|family_?name|lname)$"
    ],
    "person.suffix": [
        r"^(suffix|name_?suffix|jr_?sr)$"
    ],
    "person.ssn": [
        r"^(ssn|social_?security|tax_?id|ein|tin)$"
    ],
    "person.phone": [
        r"^(phone|mobile|cell|telephone|contact_?number)$",
        r"^(phone_?number|mobile_?number)$"
    ],
    "person.phone_extension": [
        r"^(ext|extension|phone_?ext)$"
    ],
    "person.email": [
        r"^(email|e_?mail|email_?address)$"
    ],
    "person.dob": [
        r"^(dob|date_?of_?birth|birth_?date|birthdate)$"
    ],
    "person.address": [
        r"^(address|full_?address|mailing_?address)$"
    ],
    "person.street": [
        r"^(street|street_?address|address_?line|addr)$",
        r"^(street_?1|address_?1)$"
    ],
    "person.city": [
        r"^(city)$"
    ],
    "person.state": [
        r"^(state|province)$"
    ],
    "person.zip": [
        r"^(zip|zip_?code|postal_?code|postcode)$"
    ],

    # Account Information
    "account.number": [
        r"^(account_?number|acct_?num|account_?no)$"
    ],
    "account.type": [
        r"^(account_?type|acct_?type)$"
    ],

    # Bank Information
    "bank.name": [
        r"^(bank_?name|institution_?name|financial_?institution)$"
    ],
    "bank.routing": [
        r"^(routing|routing_?number|aba|aba_?number)$"
    ],
}


def infer_cdm_key(field_name):
    """
    Infer CDM key from field name using pattern matching.

    Args:
        field_name (str): Database column name

    Returns:
        str: Inferred CDM key or None if no match

    Examples:
        >>> infer_cdm_key("first_name")
        "person.first_name"
        >>> infer_cdm_key("SSN")
        "person.ssn"
        >>> infer_cdm_key("mobile_number")
        "person.phone"
    """
    # Normalize field name for matching
    normalized = field_name.lower().strip().replace(" ", "_")

    # Try to match against patterns
    for cdm_key, patterns in FIELD_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, normalized, re.IGNORECASE):
                return cdm_key

    return None


def build_cdm_from_record(record, field_mapping=None):
    """
    Build CDM schema dynamically from a database record.

    Args:
        record (dict): Database record with field names as keys
        field_mapping (dict, optional): Custom field name mappings
                                       Format: {"db_field": "cdm_key"}

    Returns:
        dict: CDM schema with inferred structure

    Examples:
        >>> record = {
        ...     "first_name": "Jane",
        ...     "last_name": "Doe",
        ...     "ssn": "123-45-6789",
        ...     "mobile": "555-1234"
        ... }
        >>> cdm = build_cdm_from_record(record)
        >>> cdm
        {
            "person.first_name": "Jane",
            "person.last_name": "Doe",
            "person.ssn": "123-45-6789",
            "person.phone": "555-1234"
        }
    """
    cdm = {}
    field_mapping = field_mapping or {}

    for field_name, value in record.items():
        # Skip None/empty values
        if value is None or (isinstance(value, str) and not value.strip()):
            continue

        # Check custom mapping first
        if field_name in field_mapping:
            cdm_key = field_mapping[field_name]
        else:
            # Try to infer from field name
            cdm_key = infer_cdm_key(field_name)

        # Add to CDM if we found a mapping
        if cdm_key:
            cdm[cdm_key] = value

    return cdm


def build_cdm_from_table_schema(table_columns, get_value_func=None):
    """
    Build CDM schema template from table schema (column definitions).

    Useful when you want to know what CDM keys can be generated
    from a table before fetching actual data.

    Args:
        table_columns (list): List of column names
        get_value_func (callable, optional): Function to get value for each column
                                            If None, returns None for all values

    Returns:
        dict: CDM schema template with inferred keys

    Examples:
        >>> columns = ["first_name", "last_name", "ssn", "account_number"]
        >>> template = build_cdm_from_table_schema(columns)
        >>> template
        {
            "person.first_name": None,
            "person.last_name": None,
            "person.ssn": None,
            "account.number": None
        }
    """
    cdm_template = {}

    for column in table_columns:
        cdm_key = infer_cdm_key(column)
        if cdm_key:
            value = get_value_func(column) if get_value_func else None
            cdm_template[cdm_key] = value

    return cdm_template


def add_custom_field_pattern(cdm_key, patterns):
    """
    Add custom field pattern for domain-specific fields.

    Args:
        cdm_key (str): CDM key to map to
        patterns (list): List of regex patterns to match

    Example:
        >>> # Add medical domain fields
        >>> add_custom_field_pattern("patient.mrn", [r"^(mrn|medical_?record)$"])
        >>> add_custom_field_pattern("patient.blood_type", [r"^(blood_?type)$"])
    """
    if cdm_key not in FIELD_PATTERNS:
        FIELD_PATTERNS[cdm_key] = []
    FIELD_PATTERNS[cdm_key].extend(patterns)


# Example usage
if __name__ == "__main__":
    # Simulate database record with dynamic fields
    client_record = {
        "client_id": 12345,
        "first_name": "Jane",
        "middle_name": "Marie",
        "last_name": "Doe",
        "ssn": "123-45-6789",
        "mobile": "767-788-3272",
        "email": "jane.doe@example.com",
        "street_address": "123 Main Street",
        "city": "New York",
        "state": "NY",
        "zip_code": "10001",
        "account_number": "SCHW12345",
        "account_type": "Individual",
        "custom_field": "Some value",  # Will be ignored (no pattern match)
    }

    print("="*80)
    print("DYNAMIC CDM GENERATION EXAMPLE")
    print("="*80)

    print("\nClient Record (from database):")
    for k, v in client_record.items():
        print(f"  {k:<20} = {v}")

    print("\nAuto-Generated CDM Schema:")
    cdm = build_cdm_from_record(client_record)
    for k, v in cdm.items():
        print(f"  {k:<25} = {v}")

    print("\n" + "="*80)
    print("Custom Field Mapping Example")
    print("="*80)

    # Add custom mapping for fields that don't match patterns
    custom_mapping = {
        "custom_field": "person.notes"
    }

    cdm_with_custom = build_cdm_from_record(client_record, custom_mapping)
    print("\nWith custom mapping for 'custom_field':")
    print(f"  person.notes = {cdm_with_custom.get('person.notes')}")
