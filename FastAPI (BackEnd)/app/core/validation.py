"""Shared input normalization used by feature request schemas."""

import re

from app.core.config import EMAIL_PATTERN


def normalize_email(value):
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > 254 or not re.fullmatch(EMAIL_PATTERN, value):
        raise ValueError("Enter a valid email address.")
    return value


def normalize_required_text(value, label):
    value = value.strip()
    if not value:
        raise ValueError(f"{label} cannot be blank.")
    return value
