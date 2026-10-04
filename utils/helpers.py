"""Pure, UI-agnostic helpers. Keep side effects out of here."""

import random
import string


def generate_ktp_number() -> str:
    """A 16-digit ID-card style number (Jakarta area code 3171 + 12 random digits). Test data only."""
    return "3171" + "".join(random.choices(string.digits, k=12))


def generate_unique_alphabetic_name(prefix: str) -> str:
    """`prefix` + 5 random lowercase letters (for fields that reject digits)."""
    return prefix + "".join(random.choices(string.ascii_lowercase, k=5))
