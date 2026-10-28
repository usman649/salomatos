from rest_framework import serializers

from apps.authentication.models import User
from apps.finance.api.v1.serializers.common import (
    AMOUNT_MAX,
    NOTE_MAX,
    PAYEE_MAX,
    AmountField,
    MonthField,
    blank_to_none,
    validate_not_future,
)
from apps.finance.models import (
    DoctorCompensation,
    Expense,
    ExpenseCategory,
    ExpenseMethod,
    RecurringExpense,
)

# Categories an expense may name a doctor in: a doctor's share must, and a lab
# bill may, so it can be taken off that doctor's base before the percent.
DOCTOR_REQUIRED_CATEGORIES = {ExpenseCategory.DOCTOR_SHARE}
DOCTOR_ALLOWED_CATEGORIES = {ExpenseCategory.DOCTOR_SHARE, ExpenseCategory.LAB}


class ExpenseListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    date = serializers.DateField()
    category = serializers.CharField()
    amount = serializers.IntegerField()
    method = serializers.CharField()
    payee = serializers.CharField()
    note = serializers.CharField()
    doctor_id = serializers.IntegerField()
    doctor = serializers.CharField(source="doctor.full_name", default=None)
    is_void = serializers.BooleanField()
    void_reason = serializers.CharField()
    created_by = serializers.CharField(source="created_by.full_name", default=None)
    recurring_id = serializers.IntegerField()


def _clinic_doctors(context):
    return User.objects.filter(role=User.Roles.DOCTOR, clinic=context.get("clinic"))


class ExpenseCreateUpdateSerializer(serializers.ModelSerializer):
    date = serializers.DateField(validators=[validate_not_future])
    amount = AmountField()
    payee = serializers.CharField(
        max_length=PAYEE_MAX, required=False, allow_null=True, allow_blank=True
    )
    note = serializers.CharField(
        max_length=NOTE_MAX, required=False, allow_null=True, allow_blank=True
    )
    doctor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.none(), required=False, allow_null=True
    )

    class Meta:
        model = Expense
        fields = ["date", "category", "amount", "method", "payee", "note", "doctor"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["doctor"].queryset = _clinic_doctors(self.context)

    def validate_payee(self, value):
        return blank_to_none(value)

    def validate_note(self, value):
        return blank_to_none(value)

    def validate(self, attrs):
        category = attrs.get("category", getattr(self.instance, "category", None))
        doctor = attrs.get("doctor", getattr(self.instance, "doctor", None))
        if category in DOCTOR_REQUIRED_CATEGORIES and doctor is None:
            raise serializers.ValidationError(
                {"doctor": "A doctor's share needs the doctor."}, code="required"
            )
        if category not in DOCTOR_ALLOWED_CATEGORIES:
            # A doctor left over from switching category away is dropped, not an error.
            attrs["doctor"] = None
        return attrs


class RecurringExpenseListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    category = serializers.CharField()
    amount = serializers.IntegerField()
    method = serializers.CharField()
    payee = serializers.CharField()
    day_of_month = serializers.IntegerField()
    is_active = serializers.BooleanField()


class RecurringExpenseCreateUpdateSerializer(serializers.ModelSerializer):
    name = serializers.CharField(min_length=2, max_length=120)
    category = serializers.ChoiceField(
        choices=[
            choice for choice in ExpenseCategory.choices
            if choice[0] != ExpenseCategory.DOCTOR_SHARE
        ]
    )
    amount = AmountField()
    payee = serializers.CharField(
        max_length=PAYEE_MAX, required=False, allow_null=True, allow_blank=True
    )
    day_of_month = serializers.IntegerField(min_value=1, max_value=28)

    class Meta:
        model = RecurringExpense
        fields = ["name", "category", "amount", "method", "payee", "day_of_month", "is_active"]
        extra_kwargs = {"is_active": {"required": False}}

    def validate_payee(self, value):
        return blank_to_none(value)


class PayDueSerializer(serializers.Serializer):
    month = MonthField()
    date = serializers.DateField(validators=[validate_not_future])
    amount = AmountField()
    method = serializers.ChoiceField(choices=ExpenseMethod.choices)
    note = serializers.CharField(
        max_length=NOTE_MAX, required=False, allow_null=True, allow_blank=True
    )

    def validate_note(self, value):
        return blank_to_none(value)


class SkipDueSerializer(serializers.Serializer):
    month = MonthField()


class DueItemSerializer(serializers.Serializer):
    recurring_id = serializers.IntegerField()
    name = serializers.CharField()
    category = serializers.CharField()
    amount = serializers.IntegerField()
    method = serializers.CharField()
    payee = serializers.CharField(allow_null=True)
    due_date = serializers.DateField()
    status = serializers.CharField()
    expense_id = serializers.IntegerField(allow_null=True)
    paid_amount = serializers.IntegerField(allow_null=True)
    paid_date = serializers.DateField(allow_null=True)


class DueTotalsSerializer(serializers.Serializer):
    expected = serializers.IntegerField()
    paid = serializers.IntegerField()
    remaining = serializers.IntegerField()


class DueMonthSerializer(serializers.Serializer):
    month = MonthField()
    totals = DueTotalsSerializer()
    items = DueItemSerializer(many=True)


class ExpenseTotalsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    count = serializers.IntegerField()
    payroll = serializers.IntegerField()
    fixed = serializers.IntegerField()
    variable = serializers.IntegerField()


class CategoryAmountSerializer(serializers.Serializer):
    category = serializers.CharField()
    amount = serializers.IntegerField()


class AmountPointSerializer(serializers.Serializer):
    start = serializers.DateField()
    amount = serializers.IntegerField()


class ExpenseSummarySerializer(serializers.Serializer):
    # `from` is a Python keyword, so the field is declared below.
    to = serializers.DateField()
    bucket = serializers.CharField()
    totals = ExpenseTotalsSerializer()
    previous_totals = ExpenseTotalsSerializer(allow_null=True)
    by_category = CategoryAmountSerializer(many=True)
    series = AmountPointSerializer(many=True)

    def get_fields(self):
        fields = super().get_fields()
        return {"from": serializers.DateField(), **fields}


class CompensationListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    doctor_id = serializers.IntegerField()
    percent = serializers.FloatField()
    fixed = serializers.IntegerField()
    base = serializers.CharField()
    deduct_lab = serializers.BooleanField()
    effective_from = MonthField()
    created_by = serializers.CharField(source="created_by.full_name", default=None)


class CompensationCreateSerializer(serializers.ModelSerializer):
    percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, coerce_to_string=False
    )
    fixed = serializers.IntegerField(min_value=0, max_value=AMOUNT_MAX, default=0)
    effective_from = MonthField()

    class Meta:
        model = DoctorCompensation
        fields = ["percent", "fixed", "base", "deduct_lab", "effective_from"]

    def validate(self, attrs):
        if attrs["percent"] <= 0 and attrs.get("fixed", 0) <= 0:
            raise serializers.ValidationError(
                {"percent": "Set a percent, a fixed salary, or both."}, code="required"
            )
        return attrs
