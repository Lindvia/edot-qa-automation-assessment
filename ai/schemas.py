"""Schemas and fixed catalogs for generated test data.

The model only invents free-text business details (name, email, phone, street,
industry / company type). Anything the UI constrains by a dependent dropdown
(country > province > city > district > sub district > postal code) comes from
LOCATIONS below, because a model cannot know which cascade values exist.
"""

INDUSTRY_TYPES = [
    "Retail", "Real Estate", "Nonprofit and Social Services", "Manufacturing", "Hospitality",
    "Food & Beverage", "Finance and Banking", "Transportation and Logistics", "Telecommunications",
    "Technology", "Construction", "Mining and Metals", "Automotive",
    "Fast Moving Customer Goods (FMCG)", "Entertainment and Media", "Energy", "Agriculture",
    "Healthcare", "Education",
]

COMPANY_TYPES = [
    "Importer/Exporter", "Consignor/Consignee", "Marketplace", "Retailer", "Service Aggregator",
    "Third-Party Logistics (3PL) Provider", "Holding Company", "Cooperative (Co-op)",
    "Franchisee/Franchisor", "Manufacturer", "Principal", "Agent", "Dropshipper",
    "Freight Forwarder", "Distributor", "Service", "Service Provider",
]

# Verified against the live eSuite cascade (values are upper-case in the UI;
# the postal code is auto-filled by the app after the sub district is chosen).
LOCATIONS = [
    {
        "country": "Indonesia",
        "province": "DKI JAKARTA",
        "city": "JAKARTA SELATAN",
        "district": "SETIABUDI",
        "sub_district": "KARET KUNINGAN",
        "postal_code": "12940",
    },
]

# Dropdown options of the eWork SFA "New Customer Registration" form, read from a real device.
# The model never picks these: a value that is not in the dropdown would make the flow fail.
CUSTOMER_OPTIONS = {
    "channel": "General Trade (GT)",       # choices: Modern Trade (MT), General Trade (GT)
    "customer_type": "Retailer Small",     # choices: Semi Grosir, Grosir, Retailer Small/Medium/Large, Big Grosir
    "address_type": "Delivery Address",    # choices: Others, Delivery Address, Invoice Address
}

_NAME = r"^(PT|CV|UD) [A-Za-z][A-Za-z .&-]{2,50}$"
_EMAIL = r"^[a-z0-9._-]{3,40}@example\.co\.id$"  # reserved-style domain: never a real mailbox
_PHONE = r"^8[0-9]{8,11}$"                       # typed after the +62 country code, no leading 0
_STREET = r"^[A-Za-z0-9 .,/-]{10,80}$"
_PERSON = r"^[A-Za-z][A-Za-z .'-]{2,40}$"

COMPANY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "email", "phone", "street_address", "industry_type", "company_type"],
    "properties": {
        "name": {"type": "string", "pattern": _NAME},
        "email": {"type": "string", "pattern": _EMAIL},
        "phone": {"type": "string", "pattern": _PHONE},
        "street_address": {"type": "string", "pattern": _STREET},
        "industry_type": {"type": "string", "enum": INDUSTRY_TYPES},
        "company_type": {"type": "string", "enum": COMPANY_TYPES},
    },
}

CUSTOMER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["outlet_name", "phone", "email", "contact_person", "street_address"],
    "properties": {
        "outlet_name": {"type": "string", "pattern": r"^[A-Za-z][A-Za-z .&-]{2,50}$"},
        "phone": {"type": "string", "pattern": _PHONE},
        "email": {"type": "string", "pattern": _EMAIL},
        "contact_person": {"type": "string", "pattern": _PERSON},
        "street_address": {"type": "string", "pattern": _STREET},
    },
}
