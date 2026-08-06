import re

from django.core.exceptions import ValidationError


def validate_number(value):
    if not re.match(r"^\+?[1-9]\d{6,14}$", value):
        raise ValidationError("Please enter a valid phone number (e.g. +998901234567)")
    return value
