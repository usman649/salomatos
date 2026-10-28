from rest_framework import serializers

from apps.core.exceptions import ValidationError as ApiValidationError
from apps.core.reporting import clinic_today, format_month, parse_month

# Above this a typo is far likelier than a real payment (an extra zero on rent).
AMOUNT_MAX = 10_000_000_000

NOTE_MAX = 500
PAYEE_MAX = 120


def validate_not_future(value):
    if value > clinic_today():
        raise serializers.ValidationError(
            "A payment that has not happened yet cannot be recorded.", code="future_date"
        )
    return value


def blank_to_none(value):
    if value is None:
        return None
    value = value.strip()
    return value or None


class MonthField(serializers.Field):
    """`YYYY-MM` on the wire, the first day of that month in the database."""

    default_error_messages = {"invalid": "Enter a month in YYYY-MM format."}

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        try:
            return parse_month(data, self.field_name)
        except ApiValidationError:
            self.fail("invalid")

    def to_representation(self, value):
        return format_month(value)


class AmountField(serializers.IntegerField):
    def __init__(self, **kwargs):
        kwargs.setdefault("min_value", 1)
        kwargs.setdefault("max_value", AMOUNT_MAX)
        super().__init__(**kwargs)


class VoidSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=200, trim_whitespace=True)
